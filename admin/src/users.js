// 계정 관리(관리자), 변경 기록, 발행 상태.

import { ApiError, json, readJson, now, logChange, checkPassword, checkUsername, checkName } from './util.js';
import { hashPassword } from './auth.js';
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

export async function handleCreateUser(request, env, me) {
  const b = await readJson(request, 10000);
  const username = String(b.username || '').trim().toLowerCase();
  checkUsername(username);
  const name = checkName(b.name);
  const role = b.role || 'reporter';
  checkRole(role);
  checkPassword(b.password);
  const h = await hashPassword(b.password, env);
  const res = await env.DB.prepare(
    `INSERT INTO users (username, name, role, pw_hash, pw_salt, disabled, created_at)
     VALUES (?, ?, ?, ?, ?, 0, ?) ON CONFLICT(username) DO NOTHING`,
  ).bind(username, name, role, h.pw_hash, h.pw_salt, now()).run();
  if (!res.meta || res.meta.changes !== 1) throw new ApiError(409, `'${username}' 은 이미 있는 아이디입니다`);
  await logChange(env, me.username, '계정 만듦', username, `${name} · ${ROLE_LABEL[role]}`);
  return json({ ok: true, user: { username, name, role, disabled: false } }, 201);
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
