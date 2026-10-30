// 본문 미리보기. 지면의 src/render/md.py 를 그대로 옮겼다 — 미리보기와 지면이 달라 보이면 안 된다.
// 이스케이프를 먼저 하고 구조를 나중에 넣는다(본문에 든 <script> 가 살아나지 않게).
// 다른 점: <!-- 메모 --> 는 지면에 안 나가는 안내라 회색 상자로 보여 주고,
// 유튜브·바깥 사진은 편집실에서 띄우지 않고 자리만 보여 준다.

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
const unesc = (s) => String(s).replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');

const LINK = /\[([^\]]+)\]\(([^)\s]+)\)/g;
const BOLD = /\*\*([^*]+)\*\*/g;
const CODE = /`([^`]+)`/g;
const HEAD = /^(#{2,4})\s+(.*)$/;
const LIST = /^([-*·]|\d+\.)\s+/;
const YOUTUBE = /^@youtube\s+([\w-]{11})$/;
const IMAGE = /^!\[([^\]]*)\]\((https:\/\/[^)\s]+)\)$/;
const CREDIT_END = /^이 기사는 .*(?:정리|작성)했다\.?$/;

function inline(text) {
  let out = esc(text);
  out = out.replace(LINK, (m, label, href) => {
    const u = unesc(href);
    if (!/^(https?:\/\/|\/)/i.test(u)) return label;
    return `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });
  out = out.replace(BOLD, '<strong>$1</strong>');
  out = out.replace(CODE, '<code>$1</code>');
  return out;
}

function stripCredits(src) {
  const out = [];
  let skipping = false;
  for (const line of src.split('\n')) {
    const s = line.trim();
    if (s.startsWith('**출처**')) {
      skipping = true;
      continue;
    }
    if (skipping && s) continue;
    skipping = false;
    if (CREDIT_END.test(s)) continue;
    out.push(line);
  }
  while (out.length && !out[out.length - 1].trim()) out.pop();
  return out.join('\n');
}

export function renderMarkdown(src) {
  if (!src || !src.trim()) return '<p class="empty-preview">본문을 쓰면 여기에 지면 모양으로 보입니다.</p>';
  const lines = stripCredits(src.replace(/\r\n?/g, '\n')).split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const stripped = lines[i].trim();
    if (!stripped) {
      i++;
      continue;
    }
    // 안내 메모(지면에 안 나감)
    if (stripped.startsWith('<!--')) {
      const buf = [];
      while (i < lines.length) {
        buf.push(lines[i]);
        if (lines[i].includes('-->')) break;
        i++;
      }
      i++;
      const text = buf.join('\n').replace(/^\s*<!--\s?/, '').replace(/\s?-->\s*$/, '');
      out.push(`<div class="note">메모(지면에 안 나감): ${esc(text)}</div>`);
      continue;
    }
    if (/^-{3,}$/.test(stripped)) {
      out.push('<hr>');
      i++;
      continue;
    }
    const yt = YOUTUBE.exec(stripped);
    if (yt) {
      out.push(`<div class="embed">▶ 유튜브 영상 (${esc(yt[1])}) — 지면에서는 영상이 들어갑니다</div>`);
      i++;
      continue;
    }
    const image = IMAGE.exec(stripped);
    if (image) {
      out.push(`<div class="embed">사진: ${esc(image[1])}<br><span class="small">${esc(image[2])}</span></div>`);
      i++;
      continue;
    }
    const head = HEAD.exec(stripped);
    if (head) {
      const level = Math.min(head[1].length, 4);
      out.push(`<h${level}>${inline(head[2])}</h${level}>`);
      i++;
      continue;
    }
    if (stripped.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      const cells = (row) => row.trim().replace(/^\|+|\|+$/g, '').split('|').map((c) => c.trim());
      const header = cells(stripped);
      i += 2;
      const body = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        body.push(cells(lines[i]));
        i++;
      }
      out.push('<div class="tw"><table><thead><tr>' + header.map((c) => `<th>${inline(c)}</th>`).join('')
        + '</tr></thead><tbody>' + body.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('')
        + '</tbody></table></div>');
      continue;
    }
    if (stripped.startsWith('>')) {
      const buf = [];
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        buf.push(lines[i].trim().slice(1).trim());
        i++;
      }
      out.push(`<blockquote>${buf.map(inline).join('<br>')}</blockquote>`);
      continue;
    }
    if (LIST.test(stripped)) {
      const tag = /^\d+\./.test(stripped) ? 'ol' : 'ul';
      const buf = [];
      while (i < lines.length && LIST.test(lines[i].trim())) {
        buf.push(lines[i].trim().replace(LIST, ''));
        i++;
      }
      out.push(`<${tag}>${buf.map((b) => `<li>${inline(b)}</li>`).join('')}</${tag}>`);
      continue;
    }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !HEAD.test(lines[i].trim()) && !LIST.test(lines[i].trim())
      && !lines[i].trim().startsWith('>') && !lines[i].includes('|') && !lines[i].trim().startsWith('<!--')) {
      buf.push(lines[i].trim());
      i++;
    }
    if (buf.length) out.push(`<p>${inline(buf.join(' '))}</p>`);
    else {
      out.push(`<p>${inline(stripped)}</p>`);
      i++;
    }
  }
  return out.join('\n');
}

/** 글자 수(빈칸·메모 빼고) — 기사 길이를 가늠하려고. */
export function countChars(src) {
  return String(src || '').replace(/<!--[\s\S]*?-->/g, '').replace(/\s+/g, '').length;
}
