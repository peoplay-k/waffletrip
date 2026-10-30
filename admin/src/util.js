// 공용 도구: 응답, 오류, 인코딩, 날짜.

export class ApiError extends Error {
  /** status: HTTP 상태, message: 화면에 그대로 보일 한국어 문장, extra: 응답에 덧붙일 값 */
  constructor(status, message, extra = {}) {
    super(message);
    this.status = status;
    this.extra = extra;
  }
}

export function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...headers },
  });
}

/** 요청 본문 JSON. 너무 크거나 형식이 틀리면 400. */
export async function readJson(request, limit = 2 * 1024 * 1024) {
  const len = Number(request.headers.get('content-length') || 0);
  if (len > limit) throw new ApiError(413, '보낸 내용이 너무 큽니다');
  let text;
  try {
    text = await request.text();
  } catch {
    throw new ApiError(400, '요청을 읽지 못했습니다');
  }
  if (text.length > limit) throw new ApiError(413, '보낸 내용이 너무 큽니다');
  try {
    const v = JSON.parse(text || '{}');
    if (v === null || typeof v !== 'object' || Array.isArray(v)) throw new Error();
    return v;
  } catch {
    throw new ApiError(400, '요청 형식이 틀렸습니다(JSON 아님)');
  }
}

export const now = () => Date.now();

export function randomBytes(n) {
  const b = new Uint8Array(n);
  crypto.getRandomValues(b);
  return b;
}

export function hex(bytes) {
  return [...bytes].map((x) => x.toString(16).padStart(2, '0')).join('');
}

export function randomHex(n) {
  return hex(randomBytes(n));
}

export function b64encode(bytes) {
  // 큰 파일(사진 10MB)도 스택이 넘치지 않게 조각내서 바꾼다
  let s = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    s += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(s);
}

export function b64decode(str) {
  const s = atob(String(str).replace(/\s+/g, ''));
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

export function b64url(bytes) {
  return b64encode(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export const utf8 = {
  encode: (s) => new TextEncoder().encode(s),
  decode: (b) => new TextDecoder('utf-8').decode(b),
};

export async function sha256hex(text) {
  const d = await crypto.subtle.digest('SHA-256', utf8.encode(text));
  return hex(new Uint8Array(d));
}

/** 바이트 배열을 시간 차 없이 비교한다(앞부분이 맞은 길이로 비밀값을 짐작하지 못하게). */
export function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

/** 한국 시간 날짜 'YYYY-MM-DD'. 파이프라인이 KST 로 날짜를 쓴다. */
export function kstDate(ms = Date.now()) {
  return new Date(ms + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

/** 변경 기록 한 줄. 기록이 실패해도 저장 자체를 되돌리지는 않는다(커밋이 정식 기록이다). */
export async function logChange(env, username, action, target = '', detail = '') {
  try {
    await env.DB.prepare('INSERT INTO log (ts, username, action, target, detail) VALUES (?, ?, ?, ?, ?)')
      .bind(now(), username, action, String(target).slice(0, 300), String(detail).slice(0, 2000))
      .run();
  } catch (e) {
    console.error('log 기록 실패', e);
  }
}

export const USERNAME_RE = /^[a-z0-9][a-z0-9_.-]{1,23}$/;
export const MIN_PASSWORD = 10;

export function checkPassword(pw) {
  if (typeof pw !== 'string' || pw.length < MIN_PASSWORD) {
    throw new ApiError(400, `비밀번호는 ${MIN_PASSWORD}자 이상이어야 합니다`);
  }
  if (pw.length > 200) throw new ApiError(400, '비밀번호가 너무 깁니다(200자까지)');
}

export function checkUsername(u) {
  if (typeof u !== 'string' || !USERNAME_RE.test(u)) {
    throw new ApiError(400, '아이디는 영문 소문자·숫자로 시작하고, 영문 소문자·숫자·_ . - 로 2~24자여야 합니다');
  }
}

export function checkName(n) {
  if (typeof n !== 'string' || !n.trim()) throw new ApiError(400, '이름을 넣으세요');
  if (n.trim().length > 30) throw new ApiError(400, '이름이 너무 깁니다(30자까지)');
  return n.trim();
}
