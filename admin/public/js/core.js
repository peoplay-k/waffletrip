// 화면 공용 도구: 요소 만들기, API 부르기, 알림·확인 창, 날짜 표시, 이름표.

/**
 * 요소를 만든다. 글자는 늘 textContent 로 넣는다(기사 제목에 든 <, & 가 HTML 로 해석되지 않게).
 * attrs: { class, on: {click}, dataset, ...속성 } / children: 문자열·요소·배열·null
 */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'on') for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k === 'value') el.value = v;
    else if (k === 'checked' || k === 'disabled' || k === 'selected' || k === 'readOnly' || k === 'required' || k === 'open') el[k] = !!v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    if (Array.isArray(c)) append(el, c);
    else el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}

// ── API ─────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.status = status;
    this.data = data || {};
  }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export async function api(method, path, body) {
  const opts = { method, headers: { 'X-Requested-With': 'peopleroad' }, credentials: 'same-origin' };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw new ApiError(0, '편집실 서버에 연결하지 못했습니다. 인터넷 연결을 확인하고 다시 하세요.');
  }
  let data = null;
  try {
    data = await res.json();
  } catch { /* 본문 없음 */ }
  if (res.status === 401 && !['/api/login', '/api/me', '/api/setup'].includes(path)) {
    onUnauthorized();
  }
  if (!res.ok) throw new ApiError(res.status, (data && data.error) || `오류가 났습니다(${res.status})`, data);
  return data;
}

// ── 알림 ────────────────────────────────────────────────────────────────

export function toast(message, { bad = false, ms = 4500 } = {}) {
  const box = document.getElementById('toasts');
  const t = h('div', { class: 'toast' + (bad ? ' bad' : ''), role: bad ? 'alert' : 'status' }, message);
  box.append(t);
  setTimeout(() => t.remove(), ms);
}

/**
 * 모달 창. buttons: [{label, kind:'primary'|'danger'|'', value}] — 누른 단추의 value 로 끝난다.
 * onButton(value, ctl) 이 있으면 그것이 false 를 돌려줄 때 창을 닫지 않는다(비동기 저장 등).
 */
export function modal({ title, body, buttons = [{ label: '닫기', value: null }], onButton }) {
  return new Promise((resolve) => {
    const prevFocus = document.activeElement;
    const content = h('div', { class: 'content' }, body);
    const footer = h('footer');
    const back = h('div', { class: 'modal-back' });
    const box = h('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      h('header', {}, h('h2', {}, title)), content, footer);
    back.append(box);
    const close = (v) => {
      back.remove();
      document.removeEventListener('keydown', onKey);
      if (prevFocus && prevFocus.focus) prevFocus.focus();
      resolve(v);
    };
    const ctl = { close, content, footer, setBusy(b) { footer.querySelectorAll('button').forEach((x) => { x.disabled = b; }); } };
    for (const b of buttons) {
      footer.append(h('button', {
        type: 'button', class: b.kind || '',
        on: {
          click: async () => {
            if (onButton) {
              const keep = await onButton(b.value, ctl);
              if (keep === false) return;
            }
            close(b.value);
          },
        },
      }, b.label));
    }
    const onKey = (e) => {
      if (e.key === 'Escape') close(null);
    };
    document.addEventListener('keydown', onKey);
    back.addEventListener('click', (e) => {
      if (e.target === back) close(null);
    });
    document.body.append(back);
    const first = box.querySelector('input, textarea, select') || footer.querySelector('button.primary, button.danger') || footer.querySelector('button');
    if (first) first.focus();
  });
}

export async function confirmBox(title, message, { ok = '확인', kind = 'primary' } = {}) {
  const v = await modal({
    title,
    body: typeof message === 'string' ? h('p', {}, message) : message,
    buttons: [{ label: '취소', value: false }, { label: ok, kind, value: true }],
  });
  return v === true;
}

export function banner(kind, message, ...extra) {
  return h('div', { class: `banner ${kind}`, role: kind === 'bad' ? 'alert' : 'status' }, h('div', { class: 'msg' }, message), ...extra);
}

// ── 표시 ────────────────────────────────────────────────────────────────

export const STATUS = {
  draft: { label: '작성중', hint: '지면에 나가지 않습니다.' },
  review: { label: '검토요청', hint: '기자가 다 썼다는 표시입니다. 관리자가 보고 발행대기로 바꿉니다.' },
  approved: { label: '발행대기', hint: '다음 발행 때 지면에 나갑니다. 저장하면 10분 안팎에 나갑니다.' },
  published: { label: '발행됨', hint: '지면에 나가 있습니다. 고쳐 저장하면 10분 안팎에 지면도 바뀝니다.' },
  hidden: { label: '내림', hint: '지면·목록·검색·RSS·사이트맵에서 빠집니다. 다시 발행됨으로 바꾸면 돌아옵니다.' },
  duplicate: { label: '중복', hint: '파이프라인이 같은 소식의 다른 원고와 겹친다고 본 원고입니다.' },
  error: { label: '읽기 오류', hint: '앞머리를 읽지 못한 파일입니다.' },
};

export function statusBadge(s) {
  const known = STATUS[s];
  const cls = known ? `s-${s}` : 's-other';
  return h('span', { class: `badge ${cls}` }, known ? known.label : (s || '없음'));
}

export const ROLE = { admin: '관리자', reporter: '기자' };

const fmt = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
const fmtFull = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });

export function when(ts, full = false) {
  if (!ts) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts);
  return (full ? fmtFull : fmt).format(d);
}

export function ago(ts) {
  const d = new Date(ts).getTime();
  if (!d) return '';
  const s = Math.round((Date.now() - d) / 1000);
  if (s < 60) return '방금';
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return `${Math.floor(s / 86400)}일 전`;
}

export function debounce(fn, ms) {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
}

/** 사람이 옮겨 적기 쉬운 임시 비밀번호(헷갈리는 0/O, 1/l 은 뺐다). */
export function randomPassword(n = 12) {
  const chars = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const b = new Uint8Array(n);
  crypto.getRandomValues(b);
  return [...b].map((x) => chars[x % chars.length]).join('');
}

export function field(labelText, control, { hint, id, error } = {}) {
  if (id && control && !control.id) control.id = id;
  return h('div', { class: 'field' },
    h('label', { for: control && control.id ? control.id : null }, labelText),
    control,
    hint ? h('div', { class: 'hint' }, hint) : null,
    error ? h('div', { class: 'err' }, error) : null);
}

export function select(options, value, attrs = {}) {
  const el = h('select', attrs);
  for (const o of options) {
    el.append(h('option', { value: o.value, disabled: o.disabled }, o.label));
  }
  el.value = value;
  return el;
}

/** 공용 데이터(기사 목록·구조)를 잠깐 기억한다. 저장하면 비운다. */
export const store = {
  me: null,
  articles: null,
  articlesAt: 0,
  site: null,
  siteSha: null,
  siteAt: 0,
  async loadArticles(force = false) {
    if (!force && this.articles && Date.now() - this.articlesAt < 60000) return this.articles;
    const d = await api('GET', '/api/articles');
    this.articles = d.articles;
    this.articlesAt = Date.now();
    return this.articles;
  },
  async loadSite(force = false) {
    if (!force && this.site && Date.now() - this.siteAt < 60000) return this.site;
    const d = await api('GET', '/api/site');
    this.site = d.config;
    this.siteSha = d.sha;
    this.siteAt = Date.now();
    return this.site;
  },
  dropArticles() {
    this.articles = null;
  },
  dropSite() {
    this.site = null;
  },
};

export function regionName(config, id) {
  const r = (config && config.regions || []).find((x) => x.id === id);
  return r ? r.name : id;
}

export function cultureName(config, id) {
  const s = (config && config.culture_sections || []).find((x) => x.id === id);
  if (s) return s.name;
  const alias = config && config.culture_aliases && config.culture_aliases[id];
  if (alias) return cultureName(config, alias);
  return id;
}
