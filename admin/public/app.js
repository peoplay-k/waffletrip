// 피플로드 편집실 — 화면 진입점. 빌드 없이 브라우저가 ES 모듈로 그대로 읽는다.
// 주소는 #/기사 처럼 해시로 나눈다(서버에 화면 주소를 따로 두지 않으려고).

import { h, clear, api, toast, store, ROLE, setUnauthorizedHandler, banner, confirmBox } from './js/core.js';
import { renderArticleList } from './js/view-articles.js';
import { renderEditor } from './js/view-editor.js';
import { renderStructure } from './js/view-structure.js';
import { renderAccounts, renderLog } from './js/view-accounts.js';
import { renderDeploys } from './js/view-deploys.js';

const app = document.getElementById('app');
let current = null; // 지금 화면 {isDirty?, destroy?}
let lastHash = location.hash;
let ignoreHash = false;

/** 화면을 다시 그리지 않고 주소만 바꾼다(바로 뒤에 직접 그릴 때). */
function setHashSilently(hash) {
  if (location.hash !== hash) {
    ignoreHash = true;
    location.replace(hash);
  }
  lastHash = hash;
}

// ── 밝기(밝게·어둡게·기기 설정) ──
function applyTheme() {
  let t = null;
  try {
    t = localStorage.getItem('theme');
  } catch { /* 저장 안 됨 */ }
  if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t;
  else delete document.documentElement.dataset.theme;
}
function cycleTheme() {
  let t = null;
  try {
    t = localStorage.getItem('theme');
  } catch { /* */ }
  const next = t === 'light' ? 'dark' : t === 'dark' ? null : 'light';
  try {
    if (next) localStorage.setItem('theme', next);
    else localStorage.removeItem('theme');
  } catch { /* */ }
  applyTheme();
  toast(next === 'light' ? '밝은 화면' : next === 'dark' ? '어두운 화면' : '기기 설정을 따릅니다', { ms: 1500 });
}
applyTheme();

// ── 로그인 전 화면 ──

function authShell(...children) {
  clear(app).append(h('div', { class: 'auth-wrap' }, h('div', { class: 'card auth-card' },
    h('a', { class: 'brand', href: '#/' }, '피플로드 편집실', h('span', {}, '.')), ...children)));
}

function renderLogin(notice) {
  const err = h('div', { role: 'alert' });
  const user = h('input', { type: 'text', id: 'login-username', name: 'username', autocomplete: 'username', autocapitalize: 'none', spellcheck: 'false', required: true });
  const pw = h('input', { type: 'password', id: 'login-password', name: 'password', autocomplete: 'current-password', required: true });
  const btn = h('button', { type: 'submit', class: 'primary' }, '로그인');
  const form = h('form', {
    on: {
      submit: async (e) => {
        e.preventDefault();
        clear(err);
        btn.disabled = true;
        btn.textContent = '확인 중…';
        try {
          store.me = await api('POST', '/api/login', { username: user.value, password: pw.value });
          startShell();
        } catch (ex) {
          err.append(banner('bad', ex.message));
          pw.value = '';
          pw.focus();
        } finally {
          btn.disabled = false;
          btn.textContent = '로그인';
        }
      },
    },
  },
  h('p', { class: 'muted small' }, '아이디와 비밀번호로 들어갑니다.'),
  notice ? banner('info', notice) : null,
  err,
  h('div', { class: 'field' }, h('label', { for: 'login-username' }, '아이디'), user),
  h('div', { class: 'field' }, h('label', { for: 'login-password' }, '비밀번호'), pw),
  btn,
  h('p', { class: 'muted small' }, '비밀번호를 잊었으면 관리자(사장님)에게 새로 정해 달라고 하세요.'));
  authShell(form);
  user.focus();
}

function renderSetup(status) {
  if (!status.configured) {
    authShell(h('h1', {}, '첫 설치'), banner('warn', '서버에 설치 코드(ADMIN_SETUP_CODE)가 아직 없습니다. README 의 "비밀값 넣기"를 먼저 하세요.'));
    return;
  }
  const err = h('div', { role: 'alert' });
  const code = h('input', { type: 'password', id: 'setup-code', autocomplete: 'off', required: true });
  const user = h('input', { type: 'text', id: 'setup-username', autocomplete: 'username', autocapitalize: 'none', spellcheck: 'false', required: true, placeholder: '예: boss' });
  const name = h('input', { type: 'text', id: 'setup-name', required: true, placeholder: '예: 신창면' });
  const pw = h('input', { type: 'password', id: 'setup-password', autocomplete: 'new-password', required: true, minlength: '8' });
  const pw2 = h('input', { type: 'password', id: 'setup-password2', autocomplete: 'new-password', required: true, minlength: '8' });
  const btn = h('button', { type: 'submit', class: 'primary' }, '첫 관리자 만들기');
  const form = h('form', {
    on: {
      submit: async (e) => {
        e.preventDefault();
        clear(err);
        if (pw.value !== pw2.value) return err.append(banner('bad', '비밀번호 두 칸이 서로 다릅니다'));
        if (pw.value.length < 10) return err.append(banner('bad', '비밀번호는 10자 이상이어야 합니다'));
        btn.disabled = true;
        try {
          store.me = await api('POST', '/api/setup', { code: code.value, username: user.value, name: name.value, password: pw.value });
          toast('첫 관리자 계정을 만들었습니다. 이제 기자 계정을 만드세요.');
          setHashSilently('#/accounts');
          startShell();
        } catch (ex) {
          err.append(banner('bad', ex.message));
        } finally {
          btn.disabled = false;
        }
      },
    },
  },
  h('h1', {}, '첫 설치'),
  h('p', { class: 'muted small' }, '계정이 아직 하나도 없습니다. 설치 코드를 넣고 첫 관리자(사장님) 계정을 만듭니다. 이 화면은 처음 한 번만 나옵니다.'),
  err,
  h('div', { class: 'field' }, h('label', { for: 'setup-code' }, '설치 코드'), code, h('div', { class: 'hint' }, '서버 비밀값 ADMIN_SETUP_CODE 에 넣은 문구')),
  h('div', { class: 'field' }, h('label', { for: 'setup-username' }, '아이디'), user, h('div', { class: 'hint' }, '영문 소문자·숫자 2~24자')),
  h('div', { class: 'field' }, h('label', { for: 'setup-name' }, '이름'), name),
  h('div', { class: 'field' }, h('label', { for: 'setup-password' }, '비밀번호'), pw, h('div', { class: 'hint' }, '10자 이상')),
  h('div', { class: 'field' }, h('label', { for: 'setup-password2' }, '비밀번호 확인'), pw2),
  btn);
  authShell(form);
  code.focus();
}

// ── 로그인 뒤 화면 ──

const NAV = [
  { hash: '#/articles', label: '기사', match: /^#\/(articles|edit|new)/ },
  { hash: '#/review', label: '검토요청', admin: true, match: /^#\/review/, count: true },
  { hash: '#/structure', label: '구조', admin: true, match: /^#\/structure/ },
  { hash: '#/accounts', label: '계정', match: /^#\/accounts/ },
  { hash: '#/log', label: '기록', admin: true, match: /^#\/log/ },
  { hash: '#/deploys', label: '발행 상태', match: /^#\/deploys/ },
];

let navEl;
let mainEl;
let reviewCountEl;

function startShell() {
  const me = store.me;
  const isAdmin = me.role === 'admin';
  navEl = h('nav', { class: 'nav', 'aria-label': '메뉴' });
  for (const n of NAV) {
    if (n.admin && !isAdmin) continue;
    const a = h('a', { href: n.hash, dataset: { match: n.match.source } }, n.label);
    if (n.count) {
      reviewCountEl = h('span', { class: 'count', hidden: true });
      a.append(reviewCountEl);
    }
    navEl.append(a);
  }
  const logout = h('button', {
    type: 'button', class: 'small', id: 'logout',
    on: {
      click: async () => {
        if (current && current.isDirty && current.isDirty() && !(await confirmBox('로그아웃', '저장하지 않은 내용이 있습니다. 그래도 나갈까요?', { ok: '나가기', kind: 'danger' }))) return;
        try {
          await api('POST', '/api/logout');
        } catch { /* 이미 끊긴 세션이어도 로그인 화면으로 */ }
        store.me = null;
        store.dropArticles();
        store.dropSite();
        current = null;
        renderLogin('로그아웃했습니다.');
      },
    },
  }, '로그아웃');
  const top = h('header', { class: 'topbar' }, h('div', { class: 'topbar-inner' },
    h('a', { class: 'brand', href: '#/articles' }, '피플로드 편집실', h('span', {}, '.')),
    navEl,
    h('div', { class: 'who' },
      h('span', { id: 'who-name' }, h('strong', {}, me.name), ' ', h('span', { class: 'role' }, `(${ROLE[me.role] || me.role} · ${me.username})`)),
      h('button', { type: 'button', class: 'ghost icon theme', title: '밝게·어둡게', 'aria-label': '밝게·어둡게 바꾸기', on: { click: cycleTheme } }, '◐'),
      logout)));
  mainEl = h('main', { id: 'main' });
  clear(app).append(top, mainEl);
  if (!location.hash || location.hash === '#/' || location.hash === '#') setHashSilently('#/articles');
  lastHash = location.hash;
  route();
  refreshReviewCount();
}

export async function refreshReviewCount() {
  if (!reviewCountEl) return;
  try {
    const list = await store.loadArticles();
    const n = list.filter((a) => a.status === 'review').length;
    reviewCountEl.textContent = String(n);
    reviewCountEl.hidden = n === 0;
  } catch { /* 목록 화면이 오류를 보여 준다 */ }
}

function parseHash() {
  const raw = location.hash.replace(/^#/, '') || '/articles';
  const [path, query = ''] = raw.split('?');
  const parts = path.split('/').filter(Boolean).map((p) => {
    try {
      return decodeURIComponent(p);
    } catch {
      return p;
    }
  });
  return { parts, query: new URLSearchParams(query) };
}

async function route() {
  if (!store.me) return;
  if (current && current.destroy) current.destroy();
  current = null;
  for (const a of navEl.querySelectorAll('a')) a.classList.toggle('active', new RegExp(a.dataset.match).test(location.hash));
  const { parts, query } = parseHash();
  const isAdmin = store.me.role === 'admin';
  // 화면마다 새 그릇을 쓴다 — 앞 화면의 늦게 끝난 불러오기가 새 화면에 끼어들지 않게
  const view = h('div', { class: 'view' });
  mainEl.replaceChildren(view);
  window.scrollTo(0, 0);
  const ctx = { main: view, me: store.me, query, onChange: refreshReviewCount };
  const [first, ...rest] = parts;
  try {
    if (first === 'articles') current = await renderArticleList(ctx, {});
    else if (first === 'review' && isAdmin) current = await renderArticleList(ctx, { reviewQueue: true });
    else if (first === 'edit' && rest[0]) current = await renderEditor(ctx, rest.join('/'));
    else if (first === 'new') current = await renderEditor(ctx, null);
    else if (first === 'structure' && isAdmin) current = await renderStructure(ctx, rest[0]);
    else if (first === 'accounts') current = await renderAccounts(ctx);
    else if (first === 'log' && isAdmin) current = await renderLog(ctx);
    else if (first === 'deploys') current = await renderDeploys(ctx);
    else if (['review', 'structure', 'log'].includes(first)) view.append(banner('bad', '관리자만 볼 수 있는 화면입니다.'));
    else view.append(banner('warn', '없는 화면입니다.'), h('a', { href: '#/articles' }, '기사 목록으로'));
  } catch (e) {
    console.error(e);
    view.append(banner('bad', e.message || '화면을 그리지 못했습니다'));
  }
}

// 저장하지 않은 내용이 있으면 다른 화면으로 가기 전에 묻는다
window.addEventListener('hashchange', async () => {
  if (ignoreHash) {
    ignoreHash = false;
    lastHash = location.hash;
    return;
  }
  if (current && current.isDirty && current.isDirty()) {
    const target = location.hash;
    ignoreHash = true;
    history.replaceState(null, '', lastHash);
    ignoreHash = false;
    const ok = await confirmBox('저장하지 않았습니다', '고친 내용을 저장하지 않았습니다. 버리고 다른 화면으로 갈까요?', { ok: '버리고 가기', kind: 'danger' });
    if (!ok) return;
    current.isDirty = () => false;
    setHashSilently(target);
    route();
    return;
  }
  lastHash = location.hash;
  route();
});

window.addEventListener('beforeunload', (e) => {
  if (current && current.isDirty && current.isDirty()) {
    e.preventDefault();
    e.returnValue = '';
  }
});

setUnauthorizedHandler(() => {
  if (!store.me) return;
  store.me = null;
  current = null;
  renderLogin('로그인이 풀렸습니다. 다시 로그인하세요.');
});

async function boot() {
  try {
    store.me = await api('GET', '/api/me');
    startShell();
  } catch (e) {
    if (e.status !== 401) {
      authShell(banner('bad', e.message), h('button', { type: 'button', on: { click: boot } }, '다시 시도'));
      return;
    }
    try {
      const st = await api('GET', '/api/setup');
      if (st.needed) renderSetup(st);
      else renderLogin();
    } catch (e2) {
      authShell(banner('bad', e2.message), h('button', { type: 'button', on: { click: boot } }, '다시 시도'));
    }
  }
}

boot();
