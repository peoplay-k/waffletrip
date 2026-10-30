// 피플로드 편집실 Worker — 화면(public/)과 API(/api/*)를 같은 주소에서 낸다.
// 설계: docs/ADMIN_DESIGN.md 5절.

import { ApiError, json } from './util.js';
import {
  getSession, handleLogin, handleLogout, handleChangeOwnPassword, handleSetupStatus, handleSetup,
} from './auth.js';
import { handleList, handleGet, handlePut, handleCreate, handleUpload, handleMedia } from './articles.js';
import { handleGetSite, handlePutSite } from './site.js';
import {
  handleListUsers, handleCreateUser, handleUpdateUser, handleDeleteUser, handleLog, handleDeploys, handleDispatch,
  handleInviteUser, handleInviteStatus, handleInviteAccept,
} from './users.js';

const SECURITY_HEADERS = {
  'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'same-origin',
  'Strict-Transport-Security': 'max-age=31536000',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

function withHeaders(res, extra = {}) {
  const out = new Response(res.body, res);
  for (const [k, v] of Object.entries({ ...SECURITY_HEADERS, ...extra })) out.headers.set(k, v);
  return out;
}

// [메서드, 경로 모양, 권한('public'|'user'|'admin'), 처리기]
const ROUTES = [
  ['GET', /^\/api\/setup$/, 'public', handleSetupStatus],
  ['POST', /^\/api\/setup$/, 'public', handleSetup],
  ['POST', /^\/api\/login$/, 'public', handleLogin],
  ['POST', /^\/api\/logout$/, 'user', handleLogout],
  ['GET', /^\/api\/me$/, 'user', async (req, env, me) => json({ username: me.username, name: me.name, role: me.role, site_url: env.SITE_URL || 'https://waffletrip.com' })],
  ['POST', /^\/api\/me\/password$/, 'user', handleChangeOwnPassword],
  ['GET', /^\/api\/articles$/, 'user', handleList],
  ['POST', /^\/api\/articles$/, 'user', handleCreate],
  ['GET', /^\/api\/articles\/([^/]+)$/, 'user', handleGet],
  ['PUT', /^\/api\/articles\/([^/]+)$/, 'user', handlePut],
  ['POST', /^\/api\/upload$/, 'user', handleUpload],
  ['GET', /^\/api\/media$/, 'user', handleMedia],
  ['GET', /^\/api\/site$/, 'user', handleGetSite],
  ['PUT', /^\/api\/site$/, 'admin', handlePutSite],
  ['GET', /^\/api\/users$/, 'admin', handleListUsers],
  ['POST', /^\/api\/users$/, 'admin', handleCreateUser],
  ['PUT', /^\/api\/users\/([^/]+)$/, 'admin', handleUpdateUser],
  ['DELETE', /^\/api\/users\/([^/]+)$/, 'admin', handleDeleteUser],
  ['POST', /^\/api\/users\/([^/]+)\/invite$/, 'admin', handleInviteUser],
  ['GET', /^\/api\/invite$/, 'public', handleInviteStatus],
  ['POST', /^\/api\/invite$/, 'public', handleInviteAccept],
  ['GET', /^\/api\/log$/, 'admin', handleLog],
  ['GET', /^\/api\/deploys$/, 'user', handleDeploys],
  ['POST', /^\/api\/deploys$/, 'admin', handleDispatch],
];

async function api(request, env, url) {
  const method = request.method;
  // CSRF: 쓰기 요청은 우리 화면만 붙이는 헤더가 있어야 한다. 다른 사이트의 폼은 이 헤더를 못 붙인다.
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    if (request.headers.get('X-Requested-With') !== 'peopleroad') {
      throw new ApiError(403, '요청 확인 헤더가 없습니다. 편집실 화면에서 다시 하세요.');
    }
    const origin = request.headers.get('Origin');
    if (origin && origin !== url.origin) throw new ApiError(403, '다른 사이트에서 온 요청은 받지 않습니다');
  }
  let pathMatched = false;
  for (const [m, re, perm, handler] of ROUTES) {
    const hit = re.exec(url.pathname);
    if (!hit) continue;
    pathMatched = true;
    if (m !== method && !(m === 'GET' && method === 'HEAD')) continue;
    let me = null;
    if (perm !== 'public') {
      me = await getSession(env, request);
      if (!me) throw new ApiError(401, '로그인이 필요합니다');
      if (perm === 'admin' && me.role !== 'admin') throw new ApiError(403, '관리자만 할 수 있습니다');
    }
    let arg;
    try {
      arg = hit[1] === undefined ? undefined : decodeURIComponent(hit[1]);
    } catch {
      throw new ApiError(400, '주소가 틀렸습니다');
    }
    return handler(request, env, me, arg);
  }
  if (pathMatched) throw new ApiError(405, '이 주소에서는 그 요청을 받지 않습니다');
  throw new ApiError(404, '없는 API 주소입니다');
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/')) {
      let res;
      try {
        res = await api(request, env, url);
      } catch (e) {
        if (e instanceof ApiError) res = json({ error: e.message, ...e.extra }, e.status);
        else {
          console.error('처리 못 한 오류', e && e.stack ? e.stack : e);
          res = json({ error: '서버에서 예상하지 못한 오류가 났습니다. 잠시 뒤 다시 하세요.' }, 500);
        }
      }
      return withHeaders(res);
    }
    if (!['GET', 'HEAD'].includes(request.method)) return withHeaders(json({ error: '없는 주소입니다' }, 404));
    const res = await env.ASSETS.fetch(request);
    // 화면 파일은 늘 새것을 확인하게 한다 — 고친 화면이 바로 보이게(파일이 작아 부담이 없다)
    return withHeaders(res, { 'Cache-Control': 'no-cache' });
  },
};
