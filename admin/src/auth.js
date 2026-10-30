// 로그인·세션·비밀번호.
//
// 비밀번호: PBKDF2-SHA256, 16바이트 소금. 반복 횟수는 wrangler.toml 의 PASSWORD_ITERATIONS
// (기본 20,000). Workers 무료 요금제는 요청 하나에 CPU 10ms 까지라, 100,000회(약 18ms)면
// 로그인이 1102 오류로 끊긴다 — 20,000회는 약 5ms. 유료 요금제로 옮기면 100,000(WebCrypto 최대)
// 으로 올린다. 저장 꼴에 횟수를 같이 적어 두어 옛 비밀번호도 맞고, 로그인할 때 지금 설정과
// 다르면 그 자리에서 새 횟수로 다시 저장한다.
// 세션: 32바이트 난수 토큰을 쿠키로 주고, D1 에는 그 SHA-256 만 둔다.

import {
  ApiError, json, now, randomBytes, b64encode, b64decode, b64url, sha256hex, timingSafeEqual, utf8,
  readJson, logChange, checkPassword, checkUsername, checkName,
} from './util.js';

const DEFAULT_ITERATIONS = 20000;

function iterationsOf(env) {
  const n = Number(env && env.PASSWORD_ITERATIONS);
  return Number.isInteger(n) && n >= 10000 && n <= 100000 ? n : DEFAULT_ITERATIONS;
}
const SESSION_MS = 30 * 24 * 3600 * 1000;
export const COOKIE = 'pr_session';

const MAX_FAILURES = 5;
const WINDOW_MS = 15 * 60 * 1000;
const LOCK_MS = 15 * 60 * 1000;

async function pbkdf2(password, salt, iterations) {
  const key = await crypto.subtle.importKey('raw', utf8.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations }, key, 256);
  return new Uint8Array(bits);
}

export async function hashPassword(password, env) {
  const iterations = iterationsOf(env);
  const salt = randomBytes(16);
  const h = await pbkdf2(password, salt, iterations);
  return { pw_hash: `pbkdf2-sha256$${iterations}$${b64encode(h)}`, pw_salt: b64encode(salt) };
}

function storedIterations(pw_hash) {
  const m = /^pbkdf2-sha256\$(\d+)\$/.exec(pw_hash || '');
  return m ? Number(m[1]) : 0;
}

export async function verifyPassword(password, pw_hash, pw_salt) {
  const m = /^pbkdf2-sha256\$(\d+)\$(.+)$/.exec(pw_hash || '');
  if (!m) return false;
  // 저장값이 망가져 터무니없는 횟수가 들어 있으면 CPU 를 다 쓰기 전에 거절한다
  if (Number(m[1]) < 1000 || Number(m[1]) > 100000) return false;
  const want = b64decode(m[2]);
  const got = await pbkdf2(String(password), b64decode(pw_salt), Number(m[1]));
  return timingSafeEqual(got, want);
}

// 없는 아이디로 로그인할 때도 같은 시간이 걸리게 하려는 가짜 해시
function dummy(env) {
  return { pw_hash: `pbkdf2-sha256$${iterationsOf(env)}$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=`, pw_salt: 'AAAAAAAAAAAAAAAAAAAAAA==' };
}

// ── 세션 ────────────────────────────────────────────────────────────────

function cookieHeader(token, maxAgeSec) {
  return `${COOKIE}=${token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=${maxAgeSec}`;
}

export function clearCookieHeader() {
  return cookieHeader('', 0);
}

export async function createSession(env, username) {
  const token = b64url(randomBytes(32));
  const t = now();
  await env.DB.prepare('INSERT INTO sessions (token_hash, username, expires_at, created_at) VALUES (?, ?, ?, ?)')
    .bind(await sha256hex(token), username, t + SESSION_MS, t).run();
  return cookieHeader(token, SESSION_MS / 1000);
}

function readCookie(request) {
  const raw = request.headers.get('Cookie') || '';
  for (const part of raw.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === COOKIE) return v.join('=');
  }
  return '';
}

/** 쿠키의 세션 → {username, name, role, tokenHash} 또는 null. 중지된 계정은 null. */
export async function getSession(env, request) {
  const token = readCookie(request);
  if (!token || token.length > 100) return null;
  const tokenHash = await sha256hex(token);
  const row = await env.DB.prepare(
    `SELECT u.username, u.name, u.role, u.disabled, s.expires_at
       FROM sessions s JOIN users u ON u.username = s.username
      WHERE s.token_hash = ?`,
  ).bind(tokenHash).first();
  if (!row || row.disabled || row.expires_at < now()) return null;
  // 가끔 만료된 세션을 치운다(따로 예약 작업을 두지 않으려고)
  if (Math.random() < 0.02) {
    await env.DB.prepare('DELETE FROM sessions WHERE expires_at < ?').bind(now()).run();
  }
  return { username: row.username, name: row.name, role: row.role, tokenHash };
}

// ── 로그인 실패 잠금 ─────────────────────────────────────────────────────

async function lockedUntil(env, keys) {
  let until = 0;
  for (const key of keys) {
    const row = await env.DB.prepare('SELECT locked_until FROM login_attempts WHERE key = ?').bind(key).first();
    if (row && row.locked_until > until) until = row.locked_until;
  }
  return until > now() ? until : 0;
}

/** 실패 한 번을 센다. 돌려주는 값: 이번에 잠겼으면 true, 아니면 남은 횟수 중 작은 값. */
async function recordFailure(env, keys) {
  const t = now();
  let remaining = MAX_FAILURES;
  let locked = false;
  for (const key of keys) {
    // 한 문장으로 올려 세어 동시에 들어온 시도도 빠짐없이 센다
    const row = await env.DB.prepare(
      `INSERT INTO login_attempts (key, failures, first_at, locked_until) VALUES (?1, 1, ?2, 0)
       ON CONFLICT(key) DO UPDATE SET
         failures = CASE WHEN first_at < ?2 - ?3 THEN 1 ELSE failures + 1 END,
         first_at = CASE WHEN first_at < ?2 - ?3 THEN ?2 ELSE first_at END
       RETURNING failures`,
    ).bind(key, t, WINDOW_MS).first();
    const failures = row ? row.failures : 1;
    if (failures >= MAX_FAILURES) {
      await env.DB.prepare('UPDATE login_attempts SET failures = 0, first_at = ?, locked_until = ? WHERE key = ?')
        .bind(t, t + LOCK_MS, key).run();
      locked = true;
    }
    remaining = Math.min(remaining, MAX_FAILURES - failures);
  }
  return { locked, remaining: Math.max(0, remaining) };
}

function lockError(until) {
  const min = Math.max(1, Math.ceil((until - now()) / 60000));
  return new ApiError(429, `로그인을 ${MAX_FAILURES}번 틀려 잠겼습니다. ${min}분 뒤에 다시 하세요.`, { locked_until: until });
}

function clientIp(request) {
  // Cloudflare 가 붙이는 값이다. 바깥에서 보낸 같은 이름의 헤더는 Cloudflare 가 덮어쓴다.
  return request.headers.get('CF-Connecting-IP') || 'unknown';
}

// ── API ─────────────────────────────────────────────────────────────────

export async function handleLogin(request, env) {
  const body = await readJson(request, 10000);
  const username = String(body.username || '').trim().toLowerCase();
  const password = String(body.password || '');
  if (!username || !password) throw new ApiError(400, '아이디와 비밀번호를 넣으세요');
  const keys = [`user:${username.slice(0, 40)}`, `ip:${clientIp(request)}`];
  const until = await lockedUntil(env, keys);
  if (until) throw lockError(until);

  const user = await env.DB.prepare('SELECT * FROM users WHERE username = ?').bind(username).first();
  const stored = user || dummy(env);
  const ok = await verifyPassword(password, stored.pw_hash, stored.pw_salt);
  if (!user || !ok) {
    const r = await recordFailure(env, keys);
    if (r.locked) throw lockError(now() + LOCK_MS);
    throw new ApiError(401, `아이디나 비밀번호가 틀렸습니다. ${r.remaining}번 더 틀리면 15분 동안 잠깁니다.`);
  }
  if (user.disabled) throw new ApiError(403, '사용이 중지된 계정입니다. 관리자에게 물어보세요.');
  await env.DB.prepare('DELETE FROM login_attempts WHERE key = ?').bind(keys[0]).run();
  if (storedIterations(user.pw_hash) !== iterationsOf(env)) {
    const h = await hashPassword(password, env);
    await env.DB.prepare('UPDATE users SET pw_hash = ?, pw_salt = ? WHERE username = ?')
      .bind(h.pw_hash, h.pw_salt, user.username).run();
  }
  const cookie = await createSession(env, user.username);
  return json({ username: user.username, name: user.name, role: user.role }, 200, { 'Set-Cookie': cookie });
}

export async function handleLogout(request, env, me) {
  await env.DB.prepare('DELETE FROM sessions WHERE token_hash = ?').bind(me.tokenHash).run();
  return json({ ok: true }, 200, { 'Set-Cookie': clearCookieHeader() });
}

export async function handleChangeOwnPassword(request, env, me) {
  const body = await readJson(request, 10000);
  const user = await env.DB.prepare('SELECT * FROM users WHERE username = ?').bind(me.username).first();
  if (!user || !(await verifyPassword(String(body.current || ''), user.pw_hash, user.pw_salt))) {
    throw new ApiError(400, '지금 비밀번호가 틀렸습니다');
  }
  checkPassword(body.next);
  if (body.next === body.current) throw new ApiError(400, '새 비밀번호가 지금 것과 같습니다');
  const h = await hashPassword(body.next, env);
  // 다른 기기의 세션은 끊고 지금 세션만 남긴다
  await env.DB.batch([
    env.DB.prepare('UPDATE users SET pw_hash = ?, pw_salt = ? WHERE username = ?').bind(h.pw_hash, h.pw_salt, me.username),
    env.DB.prepare('DELETE FROM sessions WHERE username = ? AND token_hash != ?').bind(me.username, me.tokenHash),
  ]);
  await logChange(env, me.username, '비밀번호 바꿈', me.username);
  return json({ ok: true });
}

export async function handleSetupStatus(request, env) {
  const row = await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first();
  return json({ needed: row.n === 0, configured: !!env.ADMIN_SETUP_CODE });
}

export async function handleSetup(request, env) {
  const row = await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first();
  if (row.n > 0) throw new ApiError(409, '이미 설치되었습니다. 로그인하세요.');
  if (!env.ADMIN_SETUP_CODE) throw new ApiError(503, '서버에 설치 코드(ADMIN_SETUP_CODE)가 설정되지 않았습니다');
  const keys = [`setup:${clientIp(request)}`];
  const until = await lockedUntil(env, keys);
  if (until) throw lockError(until);

  const body = await readJson(request, 10000);
  const a = utf8.encode(await sha256hex(String(body.code || '')));
  const b = utf8.encode(await sha256hex(String(env.ADMIN_SETUP_CODE)));
  if (!timingSafeEqual(a, b)) {
    const r = await recordFailure(env, keys);
    if (r.locked) throw lockError(now() + LOCK_MS);
    throw new ApiError(403, '설치 코드가 틀렸습니다');
  }
  const username = String(body.username || '').trim().toLowerCase();
  checkUsername(username);
  const name = checkName(body.name);
  checkPassword(body.password);
  const h = await hashPassword(body.password, env);
  // 동시에 두 번 눌러도 첫 관리자는 하나만 생기게 '비어 있을 때만' 넣는다
  const res = await env.DB.prepare(
    `INSERT INTO users (username, name, role, pw_hash, pw_salt, disabled, created_at)
     SELECT ?, ?, 'admin', ?, ?, 0, ? WHERE NOT EXISTS (SELECT 1 FROM users)`,
  ).bind(username, name, h.pw_hash, h.pw_salt, now()).run();
  if (!res.meta || res.meta.changes !== 1) throw new ApiError(409, '이미 설치되었습니다. 로그인하세요.');
  await logChange(env, username, '첫 관리자 만듦', username);
  const cookie = await createSession(env, username);
  return json({ username, name, role: 'admin' }, 200, { 'Set-Cookie': cookie });
}
