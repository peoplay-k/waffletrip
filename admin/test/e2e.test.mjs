// 끝에서 끝까지 테스트: 가짜 GitHub + `wrangler dev --local`(D1 로컬) + Playwright(크로뮴).
// 테스트는 위에서부터 차례로 돈다 — 앞 테스트가 만든 계정·기사를 뒤 테스트가 쓴다.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { startStage } from './harness.mjs';
import { parseArticle, segment } from '../src/frontmatter.js';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const PNG_1x1 = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64');
const PUBLISHED = '20261030_tv_kbs-sound-track-teaser.md'; // sources·published_id 가 있는 발행 기사
const PUBLISHED2 = '20261030_saipan_pic-saipan-academic-fun-schooling.md';
const PIPELINE_DRAFT = '2026-10-28_150c04a404bc144d1cf5036a60c01a8b1dfde888.md'; // author 없는 파이프라인 원고

let stage;
let browser;
let adminCtx;
let admin; // 관리자 화면(page)
let repCtx;
let rep; // 기자 화면(page)
const state = {}; // 테스트 사이에 넘기는 값

/** 쿠키를 들고 다니는 API 손님. ip 를 주면 CF-Connecting-IP 로 보낸다(로컬 개발에서만 통한다). */
class Client {
  constructor(ip) {
    this.ip = ip;
    this.cookie = '';
  }

  async req(method, p, body, { headers = {}, noCsrf = false } = {}) {
    const h = { ...headers };
    if (!noCsrf) h['X-Requested-With'] = 'peopleroad';
    if (this.cookie) h.Cookie = this.cookie;
    if (this.ip) h['CF-Connecting-IP'] = this.ip;
    let payload;
    if (body instanceof FormData || Buffer.isBuffer(body)) payload = body;
    else if (body !== undefined) {
      h['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }
    const r = await fetch(stage.base + p, { method, headers: h, body: payload });
    const sc = r.headers.get('set-cookie');
    if (sc) this.cookie = sc.split(';')[0];
    let data = null;
    try {
      data = await r.json();
    } catch { /* 본문 없음 */ }
    return { status: r.status, data, headers: r.headers };
  }

  login(username, password) {
    return this.req('POST', '/api/login', { username, password });
  }
}

const commits = async () => (await fetch(`${stage.mockBase}/__commits`)).json();
const repo = (p) => stage.readRepo(p);

async function uiLogin(page, username, password) {
  await page.goto(`${stage.base}/#/articles`);
  await page.waitForSelector('#login-username');
  await page.fill('#login-username', username);
  await page.fill('#login-password', password);
  await page.click('form button[type=submit]');
  await page.waitForSelector('#logout');
}

async function clickModal(page, label) {
  await page.click(`.modal footer button:text-is("${label}")`);
}

before(async () => {
  stage = await startStage();
  browser = await chromium.launch();
  adminCtx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  admin = await adminCtx.newPage();
  repCtx = await browser.newContext({ viewport: { width: 1200, height: 900 } });
  rep = await repCtx.newPage();
  for (const p of [admin, rep]) {
    p.on('pageerror', (e) => {
      state.pageErrors = (state.pageErrors || []).concat(e.message);
    });
  }
});

after(async () => {
  if (browser) await browser.close();
  if (stage) await stage.stop();
});

test('첫 설치: 계정이 없을 때만, 설치 코드가 맞아야 첫 관리자가 생긴다', async () => {
  const c = new Client('10.0.0.1');
  assert.deepEqual((await c.req('GET', '/api/setup')).data, { needed: true, configured: true });
  const wrong = await c.req('POST', '/api/setup', { code: 'nope', username: 'boss', name: '사장님', password: 'password123' });
  assert.equal(wrong.status, 403);
  assert.match(wrong.data.error, /설치 코드가 틀렸습니다/);

  await admin.goto(stage.base + '/');
  await admin.waitForSelector('#setup-code');
  await admin.fill('#setup-code', 'test');
  await admin.fill('#setup-username', 'boss');
  await admin.fill('#setup-name', '사장님');
  await admin.fill('#setup-password', 'password123');
  await admin.fill('#setup-password2', 'password999');
  await admin.click('form button[type=submit]');
  await admin.waitForSelector('text=비밀번호 두 칸이 서로 다릅니다');
  await admin.fill('#setup-password2', 'password123');
  await admin.click('form button[type=submit]');
  await admin.waitForSelector('#create-user-form');
  assert.match(await admin.textContent('#who-name'), /사장님.*관리자.*boss/);

  const again = await c.req('POST', '/api/setup', { code: 'test', username: 'evil', name: 'x', password: 'password123' });
  assert.equal(again.status, 409);
  assert.equal((await c.req('GET', '/api/setup')).data.needed, false);
});

test('로그인 쿠키: HttpOnly·Secure·SameSite=Strict·Path=/·30일, 토큰 원문은 D1 에 없다', async () => {
  const c = new Client('10.0.0.2');
  const r = await c.login('boss', 'password123');
  assert.equal(r.status, 200);
  const sc = r.headers.get('set-cookie');
  for (const part of ['HttpOnly', 'Secure', 'SameSite=Strict', 'Path=/', 'Max-Age=2592000']) assert.ok(sc.includes(part), `${part} 없음: ${sc}`);
  const token = c.cookie.split('=')[1];
  assert.ok(token.length >= 43, '토큰은 32바이트 이상');
  assert.deepEqual((await c.req('GET', '/api/me')).data, { username: 'boss', name: '사장님', role: 'admin', site_url: 'https://waffletrip.com' });
  state.bossApi = c;
  // D1 에는 토큰의 SHA-256 만 있다
  const sessions = stage.d1('SELECT token_hash, expires_at - created_at AS life FROM sessions');
  const want = createHash('sha256').update(token).digest('hex');
  assert.ok(sessions.some((s) => s.token_hash === want), '토큰 해시가 D1 에 있어야');
  assert.ok(!sessions.some((s) => s.token_hash === token), '토큰 원문은 없어야');
  assert.ok(sessions.every((s) => s.life === 30 * 24 * 3600 * 1000), '세션 30일');
  const users = stage.d1('SELECT username, role, pw_hash, pw_salt FROM users');
  assert.deepEqual(users.map((u) => [u.username, u.role]), [['boss', 'admin']]);
  assert.match(users[0].pw_hash, /^pbkdf2-sha256\$20000\$[A-Za-z0-9+/]{43}=$/);
  assert.equal(Buffer.from(users[0].pw_salt, 'base64').length, 16);
  assert.ok(!JSON.stringify(users).includes('password123'), '비밀번호 원문은 어디에도 없다');
});

test('CSRF: 확인 헤더가 없거나 다른 사이트에서 온 쓰기 요청은 403', async () => {
  const c = new Client('10.0.0.3');
  const r = await c.req('POST', '/api/login', { username: 'boss', password: 'password123' }, { noCsrf: true });
  assert.equal(r.status, 403);
  const r2 = await c.req('POST', '/api/login', { username: 'boss', password: 'password123' }, { headers: { Origin: 'https://evil.example' } });
  assert.equal(r2.status, 403);
  const r3 = await state.bossApi.req('PUT', '/api/site', {}, { noCsrf: true });
  assert.equal(r3.status, 403);
});

test('보안 헤더가 화면과 API 에 붙는다', async () => {
  const page = await fetch(stage.base + '/');
  assert.match(page.headers.get('content-security-policy'), /default-src 'self'/);
  assert.equal(page.headers.get('x-frame-options'), 'DENY');
  const apiRes = await fetch(stage.base + '/api/me');
  assert.equal(apiRes.status, 401);
  assert.equal(apiRes.headers.get('cache-control'), 'no-store');
  assert.equal(apiRes.headers.get('x-content-type-options'), 'nosniff');
});

test('로그인·로그아웃(화면): 틀리면 남은 횟수, 로그아웃하면 세션이 서버에서 지워진다', async () => {
  const cookieBefore = (await adminCtx.cookies()).find((k) => k.name === 'pr_session');
  assert.ok(cookieBefore && cookieBefore.httpOnly && cookieBefore.secure && cookieBefore.sameSite === 'Strict');
  await admin.click('#logout');
  await admin.waitForSelector('text=로그아웃했습니다.');
  const stale = new Client('10.0.0.4');
  stale.cookie = `pr_session=${cookieBefore.value}`;
  assert.equal((await stale.req('GET', '/api/me')).status, 401, '로그아웃한 쿠키로는 못 들어온다');

  await admin.fill('#login-username', 'boss');
  await admin.fill('#login-password', 'wrong-password');
  await admin.click('form button[type=submit]');
  await admin.waitForSelector('text=/아이디나 비밀번호가 틀렸습니다\\. 4번 더 틀리면/');
  await admin.fill('#login-password', 'password123');
  await admin.click('form button[type=submit]');
  await admin.waitForSelector('#logout');
  // 다시 들어오면 보던 화면(계정)으로 돌아간다
  await admin.waitForSelector('#users-table');
});

test('관리자: 기자 계정 만들기(화면)', async () => {
  await admin.goto(`${stage.base}/#/accounts`);
  await admin.waitForSelector('#users-table');
  await admin.fill('#new-username', 'kim');
  await admin.fill('#new-name', '김기자');
  await admin.selectOption('#new-role', 'reporter');
  await admin.fill('#new-password', 'short');
  await admin.click('#create-user');
  await admin.waitForSelector('text=비밀번호는 10자 이상이어야 합니다');
  await admin.fill('#new-password', 'reporter-pw-1');
  await admin.click('#create-user');
  await admin.waitForSelector('#users-table tr[data-user="kim"]');
  assert.match(await admin.textContent('#users-table tr[data-user="kim"]'), /김기자/);
  // 두 번째 기자는 API 로(남의 기사 테스트용)
  const r = await state.bossApi.req('POST', '/api/users', { username: 'lee', name: '이기자', role: 'reporter', password: 'reporter-pw-2' });
  assert.equal(r.status, 201);
  const dup = await state.bossApi.req('POST', '/api/users', { username: 'lee', name: '또', role: 'reporter', password: 'reporter-pw-2' });
  assert.equal(dup.status, 409);
});

test('기자: 새 기사를 만든다 — 상태는 작성중·검토요청만, 미리보기는 이스케이프', async () => {
  await uiLogin(rep, 'kim', 'reporter-pw-1');
  const navText = await rep.textContent('nav');
  assert.ok(!navText.includes('구조') && !navText.includes('검토요청'), '기자 메뉴에 관리자 화면이 없다');
  await rep.click('#new-article');
  await rep.waitForSelector('#f-title');
  assert.deepEqual(await rep.$$eval('#f-status option', (os) => os.map((o) => o.value)), ['draft', 'review']);
  await rep.click('#save');
  await rep.waitForSelector('text=제목을 넣으세요');
  await rep.fill('#f-title', '괌 투몬 해변 새 산책로 개통: "걷기 좋은" 2km');
  await rep.selectOption('#f-region', 'guam');
  await rep.fill('#f-summary', '괌 투몬 해변에 산책로가 생겼다.');
  await rep.fill('#f-body', '괌관광청은 30일 **새 산책로**를 열었다고 밝혔다.\n\n<script>alert(1)</script>\n\n<!-- 메모 -->');
  await rep.waitForSelector('#preview strong:text("새 산책로")');
  assert.ok((await rep.innerHTML('#preview')).includes('&lt;script&gt;'), '본문의 <script> 는 글자로만');
  await rep.selectOption('#f-status', 'review');
  await rep.click('#save');
  await rep.waitForURL(/#\/edit\//);
  await rep.waitForSelector('text=검토요청으로 저장했습니다');
  const name = decodeURIComponent(rep.url().split('#/edit/')[1]);
  assert.match(name, /^\d{8}_괌-투몬-해변-새-산책로-개통-걷기-좋은-2km\.md$/);
  state.repArticle = name;
  const { front, body } = parseArticle(repo(`content/review/${name}`));
  assert.equal(front.author, 'kim');
  assert.equal(front.status, 'review');
  assert.equal(front.channel, 'travel');
  assert.equal(front.region, 'guam');
  assert.equal(front.title, '괌 투몬 해변 새 산책로 개통: "걷기 좋은" 2km');
  assert.match(front.id, /^art-guam-\d{8}-[0-9a-f]{6}$/);
  assert.ok(body.includes('**새 산책로**'));
  const last = (await commits()).at(-1);
  assert.equal(last.message, '편집실(kim): 새 기사 — 괌 투몬 해변 새 산책로 개통: "걷기 좋은" 2km');
});

test('기자 권한: 발행·남의 기사·구조·계정은 서버가 403 으로 막는다', async () => {
  const kim = new Client('10.0.1.1');
  assert.equal((await kim.login('kim', 'reporter-pw-1')).status, 200);
  state.kimApi = kim;
  const own = await kim.req('GET', `/api/articles/${encodeURIComponent(state.repArticle)}`);
  assert.equal(own.data.can.edit, true);
  assert.deepEqual(own.data.can.statuses, ['draft', 'review']);

  const publish = await kim.req('PUT', `/api/articles/${encodeURIComponent(state.repArticle)}`, { front: { ...own.data.front, status: 'approved' }, body: own.data.body, sha: own.data.sha });
  assert.equal(publish.status, 403, '기자는 발행대기로 못 바꾼다');
  const publish2 = await kim.req('PUT', `/api/articles/${encodeURIComponent(state.repArticle)}`, { front: { ...own.data.front, status: 'published' }, body: own.data.body, sha: own.data.sha });
  assert.equal(publish2.status, 403);
  const created = await kim.req('POST', '/api/articles', { front: { title: '바로 발행', channel: 'travel', region: 'guam', status: 'approved' }, body: '' });
  assert.equal(created.status, 403, '기자는 새 기사를 발행대기로 못 만든다');

  for (const other of [PUBLISHED, PIPELINE_DRAFT]) {
    const g = await kim.req('GET', `/api/articles/${encodeURIComponent(other)}`);
    assert.equal(g.status, 200, '읽기는 된다');
    assert.equal(g.data.can.edit, false);
    const p = await kim.req('PUT', `/api/articles/${encodeURIComponent(other)}`, { front: { ...g.data.front, title: '남의 기사 고침' }, body: g.data.body, sha: g.data.sha });
    assert.equal(p.status, 403, `${other}: 남의 기사`);
  }
  // 이기자가 만든 기사도 김기자는 못 고친다
  const lee = new Client('10.0.1.2');
  await lee.login('lee', 'reporter-pw-2');
  const leeNew = await lee.req('POST', '/api/articles', { front: { title: '이기자 기사', channel: 'ent', category: 'movie', status: 'draft' }, body: '본문' });
  assert.equal(leeNew.status, 201);
  const leeArt = await kim.req('GET', `/api/articles/${encodeURIComponent(leeNew.data.name)}`);
  const leeEdit = await kim.req('PUT', `/api/articles/${encodeURIComponent(leeNew.data.name)}`, { front: { ...leeArt.data.front, title: '가로채기' }, body: '', sha: leeArt.data.sha });
  assert.equal(leeEdit.status, 403);

  const site = await kim.req('GET', '/api/site');
  assert.equal(site.status, 200, '구조 읽기는 된다(편집 화면의 선택지)');
  assert.equal((await kim.req('PUT', '/api/site', { config: site.data.config, sha: site.data.sha })).status, 403);
  assert.equal((await kim.req('GET', '/api/users')).status, 403);
  assert.equal((await kim.req('POST', '/api/users', { username: 'x1', name: 'x', role: 'admin', password: 'password123' })).status, 403);
  assert.equal((await kim.req('PUT', '/api/users/kim', { role: 'admin' })).status, 403);
  assert.equal((await kim.req('GET', '/api/log')).status, 403);
  assert.equal((await kim.req('POST', '/api/deploys')).status, 403);
  assert.equal((await kim.req('GET', '/api/deploys')).status, 200);

  // 화면: 남의 발행 기사는 읽기 전용, 구조 화면은 막힘
  await rep.goto(`${stage.base}/#/edit/${encodeURIComponent(PUBLISHED)}`);
  await rep.waitForSelector('text=읽기만 할 수 있습니다');
  assert.equal(await rep.isVisible('#save'), false);
  assert.equal(await rep.isDisabled('#f-title'), true);
  await rep.goto(`${stage.base}/#/structure`);
  await rep.waitForSelector('text=관리자만 볼 수 있는 화면입니다');
});

test('관리자: 검토요청 대기열에서 열어 발행대기로 승인한다', async () => {
  await admin.goto(`${stage.base}/#/review`);
  await admin.waitForSelector(`.list-row[data-path="${state.repArticle}"]`);
  await admin.waitForSelector('nav .count:text-is("1")');
  await admin.click(`.list-row[data-path="${state.repArticle}"]`);
  await admin.waitForSelector('[data-quick="approved"]');
  await admin.click('[data-quick="approved"]');
  await admin.waitForSelector('text=10분 안팎에 지면에 반영됩니다');
  const { front } = parseArticle(repo(`content/review/${state.repArticle}`));
  assert.equal(front.status, 'approved');
  assert.equal(front.author, 'kim', '승인해도 만든 사람은 그대로');
  assert.match((await commits()).at(-1).message, /^편집실\(boss\): 발행대기\(으\)로 — 괌 투몬/);
  // 승인된 기사는 이제 기자가 못 고친다
  const g = await state.kimApi.req('GET', `/api/articles/${encodeURIComponent(state.repArticle)}`);
  assert.equal(g.data.can.edit, false);
  const p = await state.kimApi.req('PUT', `/api/articles/${encodeURIComponent(state.repArticle)}`, { front: { ...g.data.front, status: 'draft' }, body: g.data.body, sha: g.data.sha });
  assert.equal(p.status, 403);
});

test('관리자: 기사 내리기 — 바뀌는 것은 status 한 줄뿐(파이프라인 칸 글자 그대로)', async () => {
  const before = repo(`content/review/${PUBLISHED}`);
  await admin.goto(`${stage.base}/#/edit/${encodeURIComponent(PUBLISHED)}`);
  await admin.waitForSelector('[data-quick="hidden"]');
  await admin.click('[data-quick="hidden"]');
  await clickModal(admin, '내리기');
  await admin.waitForSelector('text=기사를 내렸습니다');
  const after = repo(`content/review/${PUBLISHED}`);
  assert.equal(after, before.replace('\nstatus: published\n', '\nstatus: hidden\n'), '파일 전체가 status 한 줄만 달라야 한다');
  assert.match((await commits()).at(-1).message, /^편집실\(boss\): 기사 내림 — KBS 드라마스페셜/);
  // 다시 올리기
  await admin.waitForSelector('[data-quick="published"]');
  await admin.click('[data-quick="published"]');
  await admin.waitForSelector('text=10분 안팎에 지면에 반영됩니다');
  assert.equal(repo(`content/review/${PUBLISHED}`), before, '다시 올리면 원래 글자 그대로');
});

test('관리자: 제목·요약을 고쳐도 다른 칸·본문은 글자 그대로', async () => {
  const before = repo(`content/review/${PUBLISHED2}`);
  const a = parseArticle(before);
  await admin.goto(`${stage.base}/#/edit/${encodeURIComponent(PUBLISHED2)}`);
  await admin.waitForSelector('#f-title');
  // 발행된 기사에는 지면으로 가는 '기사 보기' — /지역/발행id 앞 8자/
  assert.equal(await admin.getAttribute('#site-link', 'href'), `https://waffletrip.com/saipan/${a.front.published_id.slice(0, 8)}/`);
  await admin.fill('#f-title', "이랜드파크 PIC 사이판: '아카데믹 펀 스쿨링' 운영 #겨울방학");
  await admin.fill('#f-summary', '요약을 바꿨다.\n두 줄로.');
  await admin.keyboard.press('Control+s');
  await admin.waitForSelector('text=저장했습니다. 10분 안팎에 지면에 반영됩니다.');
  const after = repo(`content/review/${PUBLISHED2}`);
  const b = parseArticle(after);
  assert.equal(b.front.title, "이랜드파크 PIC 사이판: '아카데믹 펀 스쿨링' 운영 #겨울방학");
  assert.equal(b.front.summary, '요약을 바꿨다.\n두 줄로.');
  assert.equal(b.body, a.body, '본문 그대로');
  for (const blk of segment(a.frontText).blocks) {
    if (blk.key === 'title' || blk.key === 'summary') continue;
    assert.ok(b.frontText.includes(blk.text), `'${blk.key}' 칸이 글자 그대로가 아님`);
  }
  assert.deepEqual(Object.keys(b.front), Object.keys(a.front), '칸 순서 그대로');
  // 아무것도 안 고치고 저장하면 커밋하지 않는다
  const n = (await commits()).length;
  await admin.click('#save');
  await admin.waitForSelector('text=바뀐 것이 없어 저장하지 않았습니다');
  assert.equal((await commits()).length, n);
});

test('저장 안 한 내용이 있으면 다른 화면으로 가기 전에 묻는다', async () => {
  await admin.goto(`${stage.base}/#/edit/${encodeURIComponent(PIPELINE_DRAFT)}`);
  await admin.waitForSelector('#f-title');
  await admin.fill('#f-title', '고치는 중');
  await admin.waitForSelector('.dirty:visible');
  await admin.click('nav a[href="#/articles"]');
  await admin.waitForSelector('.modal >> text=고친 내용을 저장하지 않았습니다');
  await clickModal(admin, '취소');
  assert.match(admin.url(), /#\/edit\//);
  assert.equal(await admin.inputValue('#f-title'), '고치는 중');
});

test('그사이 바뀐 기사(오래된 sha)를 저장하면 409 — 화면은 알려 주고 새로 불러온다', async () => {
  // 바로 앞 테스트에서 연 원고를 바깥에서 몰래 고친다
  const path = `content/review/${PIPELINE_DRAFT}`;
  const text = repo(path).replace(/^title: .*$/m, 'title: 바깥에서 고친 제목');
  await fetch(`${stage.mockBase}/__write`, { method: 'POST', body: JSON.stringify({ path, text }) });
  await admin.click('#save');
  await admin.waitForSelector('text=그사이 다른 사람이 고쳤습니다');
  assert.equal(parseArticle(repo(path)).front.title, '바깥에서 고친 제목', '덮어쓰지 않았다');
  await admin.click('#conflict-reload');
  await clickModal(admin, '불러오기');
  await admin.waitForFunction(() => document.querySelector('#f-title') && document.querySelector('#f-title').value === '바깥에서 고친 제목');
  // API 로도 409
  const g = await state.bossApi.req('GET', `/api/articles/${encodeURIComponent(PIPELINE_DRAFT)}`);
  const stale = await state.bossApi.req('PUT', `/api/articles/${encodeURIComponent(PIPELINE_DRAFT)}`, { front: { ...g.data.front, title: 'A' }, body: g.data.body, sha: 'a'.repeat(40) });
  assert.equal(stale.status, 409);
  assert.equal(stale.data.conflict, true);
  assert.match(stale.data.error, /그사이 다른 사람이 고쳤습니다/);
});

test('사진 올리기: 화면에서 올려 대표 사진으로, 이상한 파일은 거절', async () => {
  await admin.goto(`${stage.base}/#/edit/${encodeURIComponent(PIPELINE_DRAFT)}`);
  await admin.waitForSelector('#photo-upload');
  await admin.setInputFiles('#f-photo-file', { name: '현장.png', mimeType: 'image/png', buffer: PNG_1x1 });
  await admin.waitForSelector('#photo-box .path');
  const p = (await admin.textContent('#photo-box .path')).trim();
  assert.match(p, /^\/content\/uploads\/\d{8}_[0-9a-f]{12}\.png$/);
  await admin.waitForFunction(() => {
    const img = document.querySelector('#photo-box img');
    return img && img.complete && img.naturalWidth === 1;
  });
  const stored = Buffer.from(await (await fetch(`${stage.mockBase}/__read?path=${encodeURIComponent(p.slice(1))}`)).arrayBuffer());
  assert.ok(stored.equals(PNG_1x1), '올린 바이트 그대로 저장소에');
  await admin.click('#save');
  await admin.waitForSelector('text=저장했습니다');
  assert.equal(parseArticle(repo(`content/review/${PIPELINE_DRAFT}`)).front.photo, p);
  assert.match((await commits()).find((c) => c.path === p.slice(1)).message, /^편집실\(boss\): 사진 올림 /);

  const fd = new FormData();
  fd.append('file', new Blob(['<svg></svg>'], { type: 'image/png' }), 'x.png');
  assert.equal((await state.kimApi.req('POST', '/api/upload', fd)).status, 415, '머리 바이트가 사진이 아니면 거절');
  const big = Buffer.alloc(10 * 1024 * 1024 + 10, 0);
  PNG_1x1.copy(big);
  assert.equal((await state.kimApi.req('POST', '/api/upload', big, { headers: { 'Content-Type': 'image/png' } })).status, 413);
});

test('구조 편집 왕복: 문화 부문 이름 바꾸기·여행 부문 추가·지역 순서·지역 낱말·홈 숫자', async () => {
  const before = JSON.parse(repo('config/site.json'));
  await admin.goto(`${stage.base}/#/structure/culture`);
  await admin.waitForSelector('.item[data-id="movie"] .sec-name');
  await admin.fill('.item[data-id="movie"] .sec-name', '시네마');

  await admin.click('[data-tab="travel"]');
  await admin.click('#add-travel_sections');
  await admin.fill('.item.new .new-id', 'food');
  await admin.fill('.item.new .sec-name', '미식');

  await admin.click('[data-tab="regions"]');
  assert.equal(await admin.$$eval('details.region button:text-is("지우기")', (b) => b.length), 0, '지역에는 지우기 단추가 없다');
  await admin.click('details.region[data-id="guam"] [aria-label="아래로"]');
  await admin.click('details.region[data-id="guam"] summary .name');
  await admin.fill('#region-guam-kw', '타무닝');
  await admin.press('#region-guam-kw', 'Enter');

  await admin.click('[data-tab="home"]');
  await admin.fill('#home-hero_count', '6');

  await admin.click('#structure-save');
  await admin.waitForSelector('#save-changes');
  const summary = await admin.textContent('#save-changes');
  for (const want of ["문화 부문 이름: '영화' → '시네마'", '여행 부문 추가: 미식 (food)', '지역 순서: 사이판 · 괌', "지역 괌: 낱말 추가 '타무닝'", '홈 넘기는 큰 기사 수: 4 → 6']) {
    assert.ok(summary.includes(want), `요약에 '${want}' 없음:\n${summary}`);
  }
  await clickModal(admin, '저장');
  await admin.waitForSelector('#structure-msg .banner.ok');

  const raw = repo('config/site.json');
  const c = JSON.parse(raw);
  assert.equal(raw, JSON.stringify(c, null, 2) + '\n', '파이썬 json.dump(indent=2) 와 같은 모양');
  assert.equal(c.culture_sections.find((s) => s.id === 'movie').name, '시네마');
  assert.deepEqual(c.travel_sections.at(-1), { id: 'food', name: '미식', desc: '', visible: true });
  assert.deepEqual(c.regions.slice(0, 2).map((r) => r.id), ['saipan', 'guam']);
  assert.ok(c.regions.find((r) => r.id === 'guam').keywords.includes('타무닝'));
  assert.equal(c.home.hero_count, 6);
  for (const k of ['_about', 'culture_rules_note', 'culture_aliases', 'korea_travel_words', 'culture_rules', 'reporters', 'channels']) {
    assert.deepEqual(c[k], before[k], `손대지 않은 '${k}' 가 바뀜`);
  }
  assert.deepEqual(c.regions.find((r) => r.id === 'guam').weather, before.regions.find((r) => r.id === 'guam').weather);
  const msg = (await commits()).at(-1).message;
  assert.match(msg, /^편집실\(boss\): 사이트 구조 — /);
  assert.ok(msg.includes('- 홈 넘기는 큰 기사 수: 4 → 6'), '커밋 본문에 바뀐 점 목록');

  // 새 여행 부문을 기사에서 바로 고를 수 있다
  await admin.goto(`${stage.base}/#/new`);
  await admin.waitForSelector('#f-topic');
  assert.ok((await admin.$$eval('#f-topic option', (os) => os.map((o) => o.value))).includes('food'));
});

test('구조 검증: 겹치는 id 는 화면이 막고, 지역 지우기·id 바꾸기·오래된 sha 는 서버가 막는다', async () => {
  const n = (await commits()).length;
  await admin.goto(`${stage.base}/#/structure/culture`);
  await admin.waitForSelector('#add-culture_sections');
  await admin.click('#add-culture_sections');
  await admin.fill('.item.new .new-id', 'tv');
  await admin.waitForSelector('.item.new .err:text("이미 있는 id")');
  await admin.fill('.item.new .sec-name', '중복');
  await admin.click('#structure-save');
  await admin.waitForSelector('#save-errors');
  assert.match(await admin.textContent('#save-errors'), /'tv' 가 겹칩니다/);
  await clickModal(admin, '닫기');
  await admin.waitForSelector('#structure-errors .banner.bad');
  await admin.click('#structure-reset');
  await clickModal(admin, '되돌리기');
  await admin.waitForSelector('.item.new', { state: 'detached' });
  assert.equal((await commits()).length, n, '오류가 있으면 커밋하지 않는다');

  const site = await state.bossApi.req('GET', '/api/site');
  const noRegion = structuredClone(site.data.config);
  noRegion.regions = noRegion.regions.filter((r) => r.id !== 'laos');
  noRegion.reporters.forEach((p) => { p.beats = p.beats.filter((b) => b !== 'laos'); });
  const r1 = await state.bossApi.req('PUT', '/api/site', { config: noRegion, sha: site.data.sha });
  assert.equal(r1.status, 400);
  assert.ok(r1.data.errors.some((e) => /지역 'laos' 은 지울 수 없습니다/.test(e.msg)), JSON.stringify(r1.data));

  const renamed = structuredClone(site.data.config);
  renamed.culture_sections.find((s) => s.id === 'stage').id = 'stages';
  const r2 = await state.bossApi.req('PUT', '/api/site', { config: renamed, sha: site.data.sha });
  assert.equal(r2.status, 400);
  assert.ok(r2.data.errors.some((e) => /'stage' 가 사라졌습니다/.test(e.msg)));

  const badHome = structuredClone(site.data.config);
  badHome.home.hero_count = 99;
  badHome.home.order = ['travel', 'nope'];
  badHome.home.pinned_lead = 'c-nothing';
  const r3 = await state.bossApi.req('PUT', '/api/site', { config: badHome, sha: site.data.sha });
  assert.equal(r3.status, 400);
  const all = r3.data.errors.map((e) => e.msg).join('\n');
  assert.match(all, /1~8/);
  assert.match(all, /모르는 묶음 'nope'/);
  assert.match(all, /c-nothing/);

  const ok = structuredClone(site.data.config);
  ok.home.latest_count = 12;
  const r4 = await state.bossApi.req('PUT', '/api/site', { config: ok, sha: 'f'.repeat(40) });
  assert.equal(r4.status, 409);
  assert.equal((await commits()).length, n);
});

test('구조: 부문 지우기는 확인하고, 그 부문 규칙도 같이 빠진다. 고정 머리기사 고르기', async () => {
  await admin.goto(`${stage.base}/#/structure/culture`);
  await admin.waitForSelector('.item[data-id="music"]');
  assert.equal(await admin.isDisabled('.item[data-id="startrip"] button:text-is("지우기")'), true, '기본 부문은 못 지움');
  await admin.click('.item[data-id="music"] button:text-is("지우기")');
  await clickModal(admin, '지우기');
  await admin.click('[data-tab="home"]');
  await admin.fill('#pin-search', '사운드');
  await admin.click('.picker-results button:has-text("사운드:트랙")');
  await admin.waitForSelector('#pin-current:has-text("사운드:트랙")');
  await admin.click('#structure-save');
  await admin.waitForSelector('#save-changes');
  const summary = await admin.textContent('#save-changes');
  assert.ok(summary.includes('문화 부문 삭제: 음악 (music)'), summary);
  assert.ok(summary.includes('문화 분류 규칙 삭제'), summary);
  assert.ok(summary.includes('홈 고정 머리기사: c-'), summary);
  await clickModal(admin, '저장');
  await admin.waitForSelector('#structure-msg .banner.ok');
  const c = JSON.parse(repo('config/site.json'));
  assert.ok(!c.culture_sections.some((s) => s.id === 'music'));
  assert.ok(!c.culture_rules.some((r) => r.section === 'music'));
  assert.equal(c.home.pinned_lead, parseArticle(repo(`content/review/${PUBLISHED}`)).front.published_id);
});

test('발행 상태: 최근 실행을 보이고, 관리자는 지금 발행을 누를 수 있다', async () => {
  await admin.goto(`${stage.base}/#/deploys`);
  await admin.waitForSelector('#deploy-state');
  assert.match(await admin.textContent('#deploy-state'), /발행 완료/);
  // DOM append 에 null 이 들어가면 'null' 글자가 찍힌다 — 한 번 났던 일
  assert.ok(!/\bnull\b/.test(await admin.textContent('#main')), '발행 상태 화면에 null 글자가 보인다');
  // 발행된 기사를 고쳐서 돈 실행에는 지면 링크가 붙는다(사장님: "오픈이 되면 기사 링크로 가야지")
  const d0 = await state.bossApi.req('GET', '/api/deploys');
  const linked = d0.data.runs.filter((r) => r.article_url);
  assert.ok(linked.length >= 1, '기사 링크가 붙은 실행이 없다');
  for (const r of linked) assert.match(r.article_url, /^https:\/\/waffletrip\.com\/(saipan|ent)\/[A-Za-z0-9_-]{1,8}\/$/);
  // 내린 기사·작성중 원고의 실행에는 안 붙는다
  assert.ok(d0.data.runs.some((r) => r.event === 'push' && !r.article_url), '지면에 없는 기사의 실행에 링크가 붙었다');
  assert.ok(await admin.$('#runs a:has-text("기사 보기")'), '발행 상태 표에 기사 보기 링크가 없다');
  // 목록에서도
  await admin.goto(`${stage.base}/#/articles`);
  await admin.waitForSelector('.list-row');
  assert.ok(await admin.$(`.list-row[data-path="${PUBLISHED2}"] .site-link`), '목록 줄에 기사 보기가 없다');
  await admin.goto(`${stage.base}/#/deploys`);
  await admin.waitForSelector('#deploy-state');
  await admin.click('#dispatch');
  await clickModal(admin, '발행 시작');
  await admin.waitForSelector('#deploy-state:has-text("발행 중")', { timeout: 15000 });
  const d = await state.kimApi.req('GET', '/api/deploys');
  assert.equal(d.data.runs[0].event, 'workflow_dispatch');
});

test('계정: 내 비밀번호 바꾸기, 관리자 재설정은 그 사람 세션을 끊고, 중지하면 로그인 불가', async () => {
  await rep.goto(`${stage.base}/#/accounts`);
  await rep.waitForSelector('#my-password');
  assert.equal(await rep.$('#users-table'), null, '기자는 계정 목록을 못 본다');
  await rep.fill('#pw-current', 'wrong-pw-000');
  await rep.fill('#pw-next', 'reporter-pw-new');
  await rep.fill('#pw-next2', 'reporter-pw-new');
  await rep.click('#my-password button[type=submit]');
  await rep.waitForSelector('text=지금 비밀번호가 틀렸습니다');
  await rep.fill('#pw-current', 'reporter-pw-1');
  await rep.click('#my-password button[type=submit]');
  await rep.waitForSelector('text=비밀번호를 바꿨습니다');
  assert.equal((await state.kimApi.req('GET', '/api/me')).status, 401, '다른 기기(세션)는 끊긴다');
  assert.equal((await new Client('10.0.2.1').login('kim', 'reporter-pw-new')).status, 200);

  // 관리자가 재설정 → 기자의 화면 세션도 끊긴다
  await admin.goto(`${stage.base}/#/accounts`);
  await admin.waitForSelector('#users-table tr[data-user="kim"]');
  await admin.click('#users-table tr[data-user="kim"] button:text-is("비밀번호 재설정")');
  await admin.fill('#reset-password', 'reset-pw-1234');
  await clickModal(admin, '재설정');
  await admin.waitForSelector('text=비밀번호를 새로 정했습니다');
  await rep.goto(`${stage.base}/?reload=1#/articles`);
  await rep.waitForSelector('#login-username');

  // 사용 중지
  await admin.click('#users-table tr[data-user="lee"] button:text-is("사용 중지")');
  await clickModal(admin, '중지');
  await admin.waitForSelector('#users-table tr[data-user="lee"] .badge:text("중지")');
  const lee = await new Client('10.0.2.2').login('lee', 'reporter-pw-2');
  assert.equal(lee.status, 403);
  assert.match(lee.data.error, /사용이 중지된 계정/);
  // 자기 자신은 중지·강등 못 함
  assert.equal((await state.bossApi.req('PUT', '/api/users/boss', { role: 'reporter' })).status, 400);
  assert.equal((await state.bossApi.req('PUT', '/api/users/boss', { disabled: true })).status, 400);
});

test('변경 기록: 바꾼 일이 모두 남는다', async () => {
  const { data } = await state.bossApi.req('GET', '/api/log?limit=200');
  const actions = data.log.map((r) => r.action);
  for (const want of ['첫 관리자 만듦', '계정 만듦', '사이트 구조 바꿈', '기사 내림', '사진 올림', '발행 시작', '비밀번호 바꿈', '계정 고침']) {
    assert.ok(actions.some((a) => a.startsWith(want)), `기록에 '${want}' 없음`);
  }
  assert.ok(actions.some((a) => a.startsWith('새 기사')));
  assert.ok(actions.some((a) => a.startsWith('발행대기')));
  await admin.goto(`${stage.base}/#/log`);
  await admin.waitForSelector('#log-table tbody tr');
});

test('기사 목록: 한 번 읽으면 폴더가 안 바뀐 동안 캐시로 낸다', async () => {
  const before = await (await fetch(`${stage.mockBase}/__stats`)).json();
  const a = await state.bossApi.req('GET', '/api/articles');
  const b = await state.bossApi.req('GET', '/api/articles');
  assert.equal(a.status, 200);
  assert.ok(a.data.articles.length >= 451);
  assert.deepEqual(a.data, b.data);
  const after = await (await fetch(`${stage.mockBase}/__stats`)).json();
  assert.equal(after.graphqlTreeText, before.graphqlTreeText, '내용까지 읽는 큰 질의는 처음 한 번뿐');
  assert.ok(after.graphqlTreeText <= 1);
  // 최신이 위: 첫 줄의 날짜가 가장 크다
  const key = (x) => x.published_on || (/^(\d{4})-?(\d{2})-?(\d{2})_/.exec(x.path) || []).slice(1).join('-');
  const keys = a.data.articles.map(key);
  assert.deepEqual([...keys].sort().reverse(), keys);
});

test('로그인 잠금: 5번 틀리면 아이디도 주소(IP)도 15분 잠긴다', async () => {
  const ip = '10.9.9.9';
  const c = new Client(ip);
  for (let i = 1; i <= 4; i++) {
    const r = await c.login('kim', `wrong-${i}-xxxx`);
    assert.equal(r.status, 401);
    assert.match(r.data.error, new RegExp(`${5 - i}번 더 틀리면`));
  }
  const fifth = await c.login('kim', 'wrong-5-xxxx');
  assert.equal(fifth.status, 429);
  assert.match(fifth.data.error, /5번 틀려 잠겼습니다\. 15분 뒤/);
  // 맞는 비밀번호도 잠긴 동안은 안 된다 — 다른 주소에서도(아이디 잠금)
  assert.equal((await new Client('10.9.9.10').login('kim', 'reset-pw-1234')).status, 429);
  // 같은 주소에서 다른 아이디도 안 된다(주소 잠금)
  assert.equal((await new Client(ip).login('boss', 'password123')).status, 429);
  // 다른 주소·다른 아이디는 된다
  assert.equal((await new Client('10.9.9.11').login('boss', 'password123')).status, 200);
  // 이미 들어와 있던 세션은 그대로
  assert.equal((await state.bossApi.req('GET', '/api/me')).status, 200);

  // 화면에서도 잠금 문구가 보인다
  const ctx = await browser.newContext({ extraHTTPHeaders: { 'CF-Connecting-IP': '10.8.8.8' } });
  const page = await ctx.newPage();
  await page.goto(`${stage.base}/`);
  await page.waitForSelector('#login-username');
  for (let i = 0; i < 5; i++) {
    await page.fill('#login-username', 'lee');
    await page.fill('#login-password', `nope-${i}-xxxx`);
    await page.click('form button[type=submit]');
    await page.waitForSelector(i < 4 ? `text=${4 - i}번 더 틀리면` : 'text=잠겼습니다');
  }
  await ctx.close();
});

test('화면 오류 없음', () => {
  assert.deepEqual(state.pageErrors || [], []);
});
