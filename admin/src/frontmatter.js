// 기사 원고(content/review/*.md)의 YAML 앞머리를 읽고 쓴다.
//
// 원칙: 고치지 않은 칸은 글자 하나 바꾸지 않는다.
// 파이프라인(PyYAML)이 쓴 앞머리를 통째로 다시 쓰면 따옴표·줄바꿈 모양이 달라져
// 저장소 이력이 지저분해지고, 파이프라인 칸(published_id·sources …)이 조금이라도
// 바뀌면 지면 동기화(src/sync_edits.py)가 어긋난다. 그래서 앞머리를 맨 윗단계 칸
// 단위로 잘라 두고, 값이 바뀐 칸만 새로 쓴다.
//
// 읽기는 검증된 `yaml` 패키지를 YAML 1.1 모드로 쓴다 — 파이프라인의 PyYAML 이 1.1 이라
// 'yes'·'on' 같은 낱말을 같은 뜻으로 읽어야 한다. 쓰기는 아래의 작은 출력기가 하는데,
// 애매하면 언제나 따옴표를 친다(PyYAML 과 yaml 패키지가 둘 다 같은 문자열로 읽게).

import { parse as yamlParse } from 'yaml';

const PARSE_OPTS = { version: '1.1', prettyErrors: false, maxAliasCount: 20 };

/** 원고를 앞머리 글자와 본문으로 나눈다. 본문은 닫는 `---` 줄 다음부터 그대로. */
export function splitDoc(raw) {
  let text = String(raw);
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const open = /^---[ \t]*\r?\n/.exec(text);
  if (!open) return { hasFront: false, frontText: '', body: text };
  let pos = open[0].length;
  const start = pos;
  while (pos <= text.length) {
    const nl = text.indexOf('\n', pos);
    const end = nl === -1 ? text.length : nl + 1;
    const line = text.slice(pos, nl === -1 ? text.length : nl).replace(/\r$/, '');
    if (/^---[ \t]*$/.test(line)) {
      return { hasFront: true, frontText: text.slice(start, pos), body: text.slice(end) };
    }
    if (nl === -1) break;
    pos = end;
  }
  // 닫는 줄이 없으면 앞머리가 아니다(파이프라인도 같은 판단을 한다)
  return { hasFront: false, frontText: '', body: text };
}

/** 앞머리 글자 → 객체. 날짜(1.1 timestamp)는 'YYYY-MM-DD' 문자열로 바꾼다. */
export function parseFront(frontText) {
  if (!frontText.trim()) return {};
  const data = yamlParse(frontText, PARSE_OPTS);
  if (data === null || data === undefined) return {};
  if (typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('앞머리가 "칸: 값" 꼴이 아닙니다');
  }
  return normalize(data);
}

function normalize(v) {
  if (v instanceof Date) {
    const iso = v.toISOString();
    return iso.endsWith('T00:00:00.000Z') ? iso.slice(0, 10) : iso;
  }
  if (Array.isArray(v)) return v.map(normalize);
  if (v instanceof Map) return normalize(Object.fromEntries(v));
  if (v && typeof v === 'object') {
    const out = {};
    for (const [k, x] of Object.entries(v)) out[k] = normalize(x);
    return out;
  }
  if (typeof v === 'bigint') return Number(v);
  return v;
}

export function parseArticle(raw) {
  const { hasFront, frontText, body } = splitDoc(raw);
  return { hasFront, frontText, front: hasFront ? parseFront(frontText) : {}, body };
}

// ── 맨 윗단계 칸 단위로 자르기 ──────────────────────────────────────────

function lines(text) {
  return text.match(/[^\n]*\n|[^\n]+$/g) || [];
}

/**
 * 앞머리를 [{key, text}] 로 자른다. 칸 줄은 0열에서 시작하고 '-'·'#'·공백이 아니다.
 * 그 밖의 줄(들여쓴 이어지는 줄, 0열의 '- 항목', 주석, 빈 줄)은 앞 칸에 붙는다.
 * 각 조각을 따로 읽어 전체를 읽은 것과 같은지 확인하고, 다르면 ok:false.
 */
export function segment(frontText) {
  const pre = [];
  const blocks = [];
  for (const line of lines(frontText)) {
    if (/^[^\s#\-]/.test(line) && !/^\.\.\.\s*$/.test(line) && !/^\?\s/.test(line)) {
      blocks.push({ key: null, text: line });
    } else if (blocks.length) {
      blocks[blocks.length - 1].text += line;
    } else {
      pre.push(line);
    }
  }
  let whole;
  try {
    whole = parseFront(frontText);
  } catch {
    return { ok: false, pre: pre.join(''), blocks };
  }
  const seen = {};
  for (const b of blocks) {
    let one;
    try {
      one = parseFront(b.text);
    } catch {
      return { ok: false, pre: pre.join(''), blocks };
    }
    const keys = Object.keys(one);
    if (keys.length !== 1 || keys[0] in seen) return { ok: false, pre: pre.join(''), blocks };
    b.key = keys[0];
    seen[b.key] = one[b.key];
  }
  const ok = deepEqual(seen, whole) && Object.keys(seen).length === Object.keys(whole).length;
  return { ok, pre: pre.join(''), blocks };
}

/**
 * 고친 앞머리 글자를 만든다. oldData 는 frontText 를 읽은 값, newData 는 저장할 값.
 * 값이 같은 칸은 원래 글자를 그대로, 바뀐 칸만 새로 쓴다. 새 칸은 끝에 붙인다.
 */
export function updateFrontText(frontText, oldData, newData) {
  const seg = segment(frontText);
  if (!seg.ok) return serializeFront(newData);
  let out = seg.pre;
  const done = new Set();
  for (const b of seg.blocks) {
    if (!Object.prototype.hasOwnProperty.call(newData, b.key)) continue; // 지운 칸
    done.add(b.key);
    if (deepEqual(oldData[b.key], newData[b.key])) {
      out += b.text.endsWith('\n') ? b.text : b.text + '\n';
    } else {
      out += emitEntry(b.key, newData[b.key], 0);
    }
  }
  for (const [k, v] of Object.entries(newData)) {
    if (!done.has(k) && v !== undefined) out += emitEntry(k, v, 0);
  }
  return out;
}

/** 새 원고의 앞머리. 객체 순서대로 쓴다. */
export function serializeFront(data) {
  let out = '';
  for (const [k, v] of Object.entries(data)) if (v !== undefined) out += emitEntry(k, v, 0);
  return out;
}

export function joinDoc(frontText, body) {
  return '---\n' + frontText + '---\n' + body;
}

// ── 출력기 ──────────────────────────────────────────────────────────────

function emitEntry(key, value, indent) {
  const pad = ' '.repeat(indent);
  const k = emitString(String(key));
  if (Array.isArray(value)) {
    if (!value.length) return `${pad}${k}: []\n`;
    // PyYAML 처럼 목록은 칸과 같은 들여쓰기로 '- ' 를 단다
    return `${pad}${k}:\n` + emitSeq(value, indent);
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value).filter(([, v]) => v !== undefined);
    if (!entries.length) return `${pad}${k}: {}\n`;
    return `${pad}${k}:\n` + entries.map(([kk, vv]) => emitEntry(kk, vv, indent + 2)).join('');
  }
  return `${pad}${k}: ${emitScalar(value)}\n`;
}

function emitSeq(arr, indent) {
  const pad = ' '.repeat(indent);
  let out = '';
  for (const item of arr) {
    if (Array.isArray(item)) {
      if (!item.length) out += `${pad}- []\n`;
      else out += `${pad}-\n` + emitSeq(item, indent + 2);
    } else if (item && typeof item === 'object') {
      const entries = Object.entries(item).filter(([, v]) => v !== undefined);
      if (!entries.length) {
        out += `${pad}- {}\n`;
        continue;
      }
      const body = entries.map(([kk, vv]) => emitEntry(kk, vv, indent + 2)).join('');
      // 첫 줄의 들여쓰기 자리에 '- ' 를 넣는다
      out += `${pad}- ` + body.slice(indent + 2);
    } else {
      out += `${pad}- ${emitScalar(item)}\n`;
    }
  }
  return out;
}

export function emitScalar(v) {
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') {
    if (Number.isNaN(v)) return '.nan';
    if (v === Infinity) return '.inf';
    if (v === -Infinity) return '-.inf';
    let s = String(v);
    // PyYAML 의 실수 규칙은 점이 있어야 한다('1e+21' 은 문자열로 읽는다)
    if (/e/i.test(s) && !s.includes('.')) s = s.replace(/e/i, '.0e');
    return s;
  }
  return emitString(String(v));
}

// PyYAML(1.1) 이 문자열이 아닌 것으로 읽는 꼴. 걸리면 따옴표를 친다.
const YAML11_NON_STRING = [
  /^(?:yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF|y|Y|n|N)$/,
  /^(?:~|null|Null|NULL)$/,
  /^[-+]?(?:[0-9][0-9_]*)?\.[0-9_]*(?:[eE][-+]?[0-9]+)?$/,
  /^[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+(?:\.[0-9_]*)?$/,
  /^[-+]?\.(?:inf|Inf|INF)$|^\.(?:nan|NaN|NAN)$/,
  /^[-+]?(?:0b[0-1_]+|0[0-7_]+|0|[1-9][0-9_]*|0x[0-9a-fA-F_]+|0o[0-7]+)$/,
  /^[-+]?[0-9]+(?:[eE][-+]?[0-9]+)?$/,
  /^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}/,
  /^(?:<<|=)$/,
];

// 줄바꿈으로 읽히거나 PyYAML 이 받지 않는 글자 → 큰따옴표 + 이스케이프
const NEEDS_DOUBLE = /[\x00-\x1f\x7f-\x9f\u2028\u2029\ufeff\ufffe\uffff]|---/;

export function emitString(s) {
  if (s === '') return "''";
  if (NEEDS_DOUBLE.test(s)) return doubleQuote(s);
  if (isPlainSafe(s)) return s;
  return "'" + s.replace(/'/g, "''") + "'";
}

function isPlainSafe(s) {
  if (/^\s|\s$/.test(s)) return false;
  if (/^[-?:,[\]{}#&*!|>'"%@`.]/.test(s)) return false;
  if (/: |:$| #|\t/.test(s)) return false;
  if (YAML11_NON_STRING.some((re) => re.test(s))) return false;
  // 마지막 확인: 두 해석(1.1·1.2) 모두 같은 문자열로 읽는지
  try {
    for (const version of ['1.1', '1.2']) {
      const got = yamlParse(`k: ${s}\n`, { version });
      if (!got || got.k !== s) return false;
    }
  } catch {
    return false;
  }
  return true;
}

function doubleQuote(s) {
  let out = '"';
  let dashRun = 0;
  for (const ch of s) {
    const c = ch.codePointAt(0);
    if (ch === '-') {
      dashRun++;
      // '---' 가 글자 그대로 남으면 파이프라인의 split("---") 이 앞머리를 거기서 자른다
      out += dashRun >= 3 ? '\\x2D' : '-';
      if (dashRun >= 3) dashRun = 0;
      continue;
    }
    dashRun = 0;
    if (ch === '"') out += '\\"';
    else if (ch === '\\') out += '\\\\';
    else if (ch === '\n') out += '\\n';
    else if (ch === '\t') out += '\\t';
    else if (ch === '\r') out += '\\r';
    else if (c < 0x20 || (c >= 0x7f && c <= 0x9f) || c === 0x2028 || c === 0x2029 || c === 0xfeff || c === 0xfffe || c === 0xffff) {
      out += '\\u' + c.toString(16).padStart(4, '0');
    } else out += ch;
  }
  return out + '"';
}

/** 화면에서 온 글자를 정리한다: 줄바꿈 통일, 제어 문자 제거, 깨진 서로게이트 제거. */
export function cleanText(s) {
  let t = String(s ?? '').replace(/\r\n?/g, '\n');
  t = t.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffe\uffff]/g, '');
  return typeof t.toWellFormed === 'function' ? t.toWellFormed() : t;
}

export function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null) return false;
  if (Array.isArray(a)) {
    if (!Array.isArray(b) || a.length !== b.length) return false;
    return a.every((x, i) => deepEqual(x, b[i]));
  }
  if (typeof a === 'object') {
    if (Array.isArray(b)) return false;
    const ka = Object.keys(a);
    const kb = Object.keys(b);
    if (ka.length !== kb.length) return false;
    return ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && deepEqual(a[k], b[k]));
  }
  return Number.isNaN(a) && Number.isNaN(b);
}

// ── 목록용 요약 ─────────────────────────────────────────────────────────

const LIST_KEYS = ['title', 'status', 'channel', 'region', 'category', 'topic', 'published_on',
  'published_id', 'author', 'source_name', 'kind', 'id'];

/** 목록 한 줄에 필요한 칸만. 앞머리를 못 읽으면 status:'error' 로 표시한다. */
export function articleMeta(name, raw) {
  try {
    const { front } = parseArticle(raw);
    const m = { path: name };
    for (const k of LIST_KEYS) {
      const v = front[k];
      m[k] = v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v);
    }
    if (!m.title) m.title = name;
    return m;
  } catch (e) {
    return { path: name, title: name, status: 'error', error: '앞머리를 읽을 수 없습니다: ' + String(e.message || e).slice(0, 200) };
  }
}
