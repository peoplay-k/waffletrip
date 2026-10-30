// 계정 관리(관리자), 변경 기록, 발행 상태.

import { ApiError, json, readJson, now, logChange, checkPassword, checkUsername, checkName, randomBytes, b64url, sha256hex } from './util.js';
import { hashPassword, createSession } from './auth.js';
import { GitHub } from './github.js';
import { parseArticle } from './frontmatter.js';
import { DIR } from './articles.js';
import { articleSiteUrl } from '../public/shared/article_url.js';

const ROLE_LABEL = { admin: '관리자', reporter: '기자' };

function checkRole(role) {
  if (!(role in ROLE_LABEL)) throw new ApiError(400, '역할은 관리자 또는 기자여야 합니다');
}

async function activeAdmins(env, except) {
  const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND disabled = 0 AND username != ?").bind(except).first();
  return row.n;
}

export async function handleListUsers(request, env) {
  const { results } = await env.DB.prepare('SELECT username, name, role, disabled, created_at FROM users ORDER BY created_at').all();
  return json({ users: results.map((u) => ({ ...u, disabled: !!u.disabled })) });
}

// ── 초대 링크 ───────────────────────────────────────────────────────────
// 비밀번호를 관리자가 정해 카톡으로 보내면 채팅방에 남는다. 대신 3일 안에 한 번만 쓰는 링크를
// 주고, 링크를 연 본인이 비밀번호를 정한다(2026-10-30).

const INVITE_MS = 3 * 24 * 3600 * 1000;

async function issueInvite(env, me, username) {
  const token = b64url(randomBytes(24));
  const t = now();
  await env.DB.batch([
    env.DB.prepare('DELETE FROM invites WHERE username = ? OR expires_at < ?').bind(username, t),
    env.DB.prepare('INSERT INTO invites (token_hash, username, expires_at, created_by, created_at) VALUES (?, ?, ?, ?, ?)')
      .bind(await sha256hex(token), username, t + INVITE_MS, me.username, t),
  ]);
  return { token, expires_at: t + INVITE_MS };
}

function inviteUrl(request, token) {
  return `${new URL(request.url).origin}/#/invite/${token}`;
}

export async function handleCreateUser(request, env, me) {
  const b = await readJson(request, 10000);
  const username = String(b.username || '').trim().toLowerCase();
  checkUsername(username);
  const name = checkName(b.name);
  const role = b.role || 'reporter';
  checkRole(role);
  const byInvite = b.invite === true;
  // 초대로 만들면 비밀번호는 아무도 모르는 난수 — 링크로 정하기 전에는 로그인할 수 없다
  const password = byInvite ? b64url(randomBytes(32)) : b.password;
  if (!byInvite) checkPassword(password);
  const h = await hashPassword(password, env);
  const res = await env.DB.prepare(
    `INSERT INTO users (username, name, role, pw_hash, pw_salt, disabled, created_at)
     VALUES (?, ?, ?, ?, ?, 0, ?) ON CONFLICT(username) DO NOTHING`,
  ).bind(username, name, role, h.pw_hash, h.pw_salt, now()).run();
  if (!res.meta || res.meta.changes !== 1) throw new ApiError(409, `'${username}' 은 이미 있는 아이디입니다`);
  await logChange(env, me.username, byInvite ? '계정 만듦(초대 링크)' : '계정 만듦', username, `${name} · ${ROLE_LABEL[role]}`);
  const out = { ok: true, user: { username, name, role, disabled: false } };
  if (byInvite) {
    const inv = await issueInvite(env, me, username);
    out.invite = { url: inviteUrl(request, inv.token), expires_at: inv.expires_at };
  }
  return json(out, 201);
}

/** 있는 계정에 새 초대 링크(관리자). 비밀번호를 잊은 사람에게도 이걸 준다 — 링크로 새로 정한다. */
export async function handleInviteUser(request, env, me, username) {
  const user = await env.DB.prepare('SELECT username, name, disabled FROM users WHERE username = ?').bind(username).first();
  if (!user) throw new ApiError(404, '그런 계정이 없습니다');
  if (user.disabled) throw new ApiError(400, '사용 중지된 계정입니다. 먼저 다시 사용으로 바꾸세요.');
  const inv = await issueInvite(env, me, username);
  await logChange(env, me.username, '초대 링크 만듦', username, user.name);
  return json({ ok: true, url: inviteUrl(request, inv.token), expires_at: inv.expires_at }, 201);
}

async function findInvite(env, token) {
  if (typeof token !== 'string' || token.length < 20 || token.length > 100) return null;
  const row = await env.DB.prepare(
    `SELECT i.token_hash, i.username, i.expires_at, u.name, u.disabled
       FROM invites i JOIN users u ON u.username = i.username
      WHERE i.token_hash = ?`,
  ).bind(await sha256hex(token)).first();
  if (!row || row.expires_at < now() || row.disabled) return null;
  return row;
}

/** 링크를 열었을 때: 누구의 초대인지만 알려 준다(비밀 없음). */
export async function handleInviteStatus(request, env) {
  const token = new URL(request.url).searchParams.get('token') || '';
  const inv = await findInvite(env, token);
  if (!inv) return json({ valid: false });
  return json({ valid: true, username: inv.username, name: inv.name, expires_at: inv.expires_at });
}

/** 링크로 비밀번호 정하기 → 그 자리에서 로그인. 링크는 지운다(한 번만). */
export async function handleInviteAccept(request, env) {
  const b = await readJson(request, 10000);
  const inv = await findInvite(env, b.token);
  if (!inv) throw new ApiError(410, '초대 링크가 만료됐거나 이미 쓰였습니다. 관리자에게 새 링크를 받으세요.');
  checkPassword(b.password);
  const h = await hashPassword(b.password, env);
  // 링크를 지우는 것과 비밀번호를 바꾸는 것을 한 묶음으로 — 두 번 쓰이지 않게
  const results = await env.DB.batch([
    env.DB.prepare('DELETE FROM invites WHERE token_hash = ?').bind(inv.token_hash),
    env.DB.prepare('UPDATE users SET pw_hash = ?, pw_salt = ? WHERE username = ?').bind(h.pw_hash, h.pw_salt, inv.username),
    env.DB.prepare('DELETE FROM sessions WHERE username = ?').bind(inv.username),
  ]);
  if (!results[0].meta || results[0].meta.changes !== 1) throw new ApiError(410, '초대 링크가 방금 쓰였습니다.');
  const user = await env.DB.prepare('SELECT username, name, role FROM users WHERE username = ?').bind(inv.username).first();
  await logChange(env, user.username, '초대 링크로 비밀번호 정함', user.username);
  const cookie = await createSession(env, user.username);
  return json({ username: user.username, name: user.name, role: user.role, site_url: env.SITE_URL || 'https://waffletrip.com' }, 200, { 'Set-Cookie': cookie });
}

export async function handleUpdateUser(request, env, me, username) {
  const b = await readJson(request, 10000);
  const user = await env.DB.prepare('SELECT * FROM users WHERE username = ?').bind(username).first();
  if (!user) throw new ApiError(404, '그런 계정이 없습니다');
  const sets = [];
  const binds = [];
  const notes = [];
  let killSessions = false;

  if (b.name !== undefined) {
    const name = checkName(b.name);
    if (name !== user.name) {
      sets.push('name = ?');
      binds.push(name);
      notes.push(`이름 ${user.name} → ${name}`);
    }
  }
  if (b.role !== undefined && b.role !== user.role) {
    checkRole(b.role);
    if (username === me.username) throw new ApiError(400, '자기 계정의 관리자 권한은 뺄 수 없습니다');
    if (user.role === 'admin' && !user.disabled && (await activeAdmins(env, username)) === 0) {
      throw new ApiError(400, '마지막 관리자의 권한은 뺄 수 없습니다');
    }
    sets.push('role = ?');
    binds.push(b.role);
    notes.push(`역할 ${ROLE_LABEL[user.role]} → ${ROLE_LABEL[b.role]}`);
    killSessions = true;
  }
  if (b.disabled !== undefined && !!b.disabled !== !!user.disabled) {
    if (username === me.username) throw new ApiError(400, '자기 계정은 중지할 수 없습니다');
    if (b.disabled && user.role === 'admin' && (await activeAdmins(env, username)) === 0) {
      throw new ApiError(400, '마지막 관리자는 중지할 수 없습니다');
    }
    sets.push('disabled = ?');
    binds.push(b.disabled ? 1 : 0);
    notes.push(b.disabled ? '사용 중지' : '다시 사용');
    if (b.disabled) killSessions = true;
  }
  if (b.password !== undefined) {
    checkPassword(b.password);
    const h = await hashPassword(b.password, env);
    sets.push('pw_hash = ?', 'pw_salt = ?');
    binds.push(h.pw_hash, h.pw_salt);
    notes.push('비밀번호 재설정');
    killSessions = true;
  }
  if (!sets.length) return json({ ok: true, unchanged: true });
  const stmts = [env.DB.prepare(`UPDATE users SET ${sets.join(', ')} WHERE username = ?`).bind(...binds, username)];
  // 권한이 바뀌거나 비밀번호를 새로 정하면 그 사람의 로그인은 모두 끊는다
  if (killSessions) stmts.push(env.DB.prepare('DELETE FROM sessions WHERE username = ?').bind(username));
  // 잠금도 풀어 준다 — 관리자가 비밀번호를 새로 알려 주는 흔한 경우
  if (b.password !== undefined) stmts.push(env.DB.prepare('DELETE FROM login_attempts WHERE key = ?').bind(`user:${username}`));
  await env.DB.batch(stmts);
  await logChange(env, me.username, '계정 고침', username, notes.join(', '));
  return json({ ok: true });
}

export async function handleDeleteUser(request, env, me, username) {
  if (username === me.username) throw new ApiError(400, '자기 계정은 지울 수 없습니다');
  const user = await env.DB.prepare('SELECT * FROM users WHERE username = ?').bind(username).first();
  if (!user) throw new ApiError(404, '그런 계정이 없습니다');
  if (user.role === 'admin' && !user.disabled && (await activeAdmins(env, username)) === 0) {
    throw new ApiError(400, '마지막 관리자는 지울 수 없습니다');
  }
  await env.DB.batch([
    env.DB.prepare('DELETE FROM users WHERE username = ?').bind(username),
    env.DB.prepare('DELETE FROM sessions WHERE username = ?').bind(username),
  ]);
  await logChange(env, me.username, '계정 지움', username, user.name);
  return json({ ok: true });
}

export async function handleLog(request, env) {
  const url = new URL(request.url);
  const limit = Math.min(500, Math.max(1, Number(url.searchParams.get('limit')) || 100));
  const before = Number(url.searchParams.get('before')) || 0;
  const stmt = before
    ? env.DB.prepare('SELECT * FROM log WHERE id < ? ORDER BY id DESC LIMIT ?').bind(before, limit)
    : env.DB.prepare('SELECT * FROM log ORDER BY id DESC LIMIT ?').bind(limit);
  const { results } = await stmt.all();
  return json({ log: results });
}

// ── 발행 상태 ───────────────────────────────────────────────────────────

const WORKFLOW = 'daily.yml';

export async function handleDeploys(request, env) {
  const gh = new GitHub(env);
  const runs = await gh.workflowRuns(WORKFLOW, 6);
  const list = runs.map((r) => ({
    id: r.id,
    status: r.status,
    conclusion: r.conclusion,
    event: r.event,
    title: r.display_title || r.name || '',
    created_at: r.created_at,
    updated_at: r.updated_at,
    run_started_at: r.run_started_at || r.created_at,
    url: r.html_url,
    head_sha: r.head_sha || '',
  }));
  await attachArticleLinks(env, gh, list);
  for (const r of list) delete r.head_sha;
  const running = list.some((r) => r.status !== 'completed');
  return json({ runs: list, running });
}

/**
 * 저장해서 돈 실행(run)에 그 기사의 지면 주소를 붙인다(사장님 2026-10-30: "오픈이 되면 기사 링크로
 * 가야지. 왜 깃허브로 가니"). 실행의 커밋 해시 → 기록(log.commit_sha) → 파일 → 발행 id → 주소.
 * 한 번 알아낸 것은 run_links 에 둔다(발행 id 는 안 바뀐다). 지면에 없는 기사(작성중·내림)는
 * 빈 주소로 적어 두어 다시 묻지 않는다.
 */
async function attachArticleLinks(env, gh, list) {
  if (!list.length) return;
  const { results } = await env.DB.prepare(
    `SELECT run_id, url, title FROM run_links WHERE run_id IN (${list.map(() => '?').join(',')})`,
  ).bind(...list.map((r) => r.id)).all();
  const known = new Map(results.map((r) => [r.run_id, r]));
  for (const r of list) {
    const hit = known.get(r.id);
    if (hit) {
      if (hit.url) {
        r.article_url = hit.url;
        r.article_title = hit.title;
      }
      continue;
    }
    if (r.status !== 'completed' || r.conclusion !== 'success' || r.event !== 'push' || !r.head_sha) continue;
    try {
      const row = await env.DB.prepare('SELECT target FROM log WHERE commit_sha = ? ORDER BY id DESC LIMIT 1').bind(r.head_sha).first();
      if (!row || !/\.md$/.test(row.target)) continue;
      const file = await gh.getFile(`${DIR}/${row.target}`);
      if (!file) continue;
      const { front } = parseArticle(file.text);
      const url = articleSiteUrl(front, env.SITE_URL);
      const title = String(front.title || '');
      if (url) {
        r.article_url = url;
        r.article_title = title;
      }
      await env.DB.prepare('INSERT OR REPLACE INTO run_links (run_id, url, title, created_at) VALUES (?, ?, ?, ?)')
        .bind(r.id, url, title, now()).run();
    } catch (e) {
      console.error('실행의 기사 주소를 못 찾음', r.id, e);
    }
  }
}

/** 지금 발행(관리자). 구조만 바꾸면 매일 발행이 저절로 돌지 않아 둔 단추다. */
export async function handleDispatch(request, env, me) {
  await new GitHub(env).dispatch(WORKFLOW);
  await logChange(env, me.username, '발행 시작', WORKFLOW);
  return json({ ok: true }, 202);
}
