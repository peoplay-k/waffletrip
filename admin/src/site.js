// 사이트 구조 파일(config/site.json) API.

import { ApiError, json, readJson, b64encode, utf8, logChange } from './util.js';
import { GitHub, CONFLICT_MSG } from './github.js';
import { validateSite, diffSite } from '../public/shared/siteconfig.js';
import { listArticles } from './articles.js';

export const SITE_PATH = 'config/site.json';

// 기사 저장 때 칸 검사에 쓰는 구조. 한 Worker 안에서 30초만 기억한다(구조를 저장하면 바로 비운다).
let cache = null;

export async function getSiteConfig(env, { fresh = false } = {}) {
  if (!fresh && cache && cache.at > Date.now() - 30000) return cache.config;
  const file = await new GitHub(env).getFile(SITE_PATH);
  if (!file) throw new ApiError(500, `저장소에 ${SITE_PATH} 가 없습니다`);
  let config;
  try {
    config = JSON.parse(file.text);
  } catch {
    throw new ApiError(500, `${SITE_PATH} 가 JSON 형식이 아닙니다. GitHub 에서 직접 고쳐야 합니다.`);
  }
  cache = { at: Date.now(), config, sha: file.sha };
  return config;
}

async function loadSite(env) {
  const file = await new GitHub(env).getFile(SITE_PATH);
  if (!file) throw new ApiError(500, `저장소에 ${SITE_PATH} 가 없습니다`);
  try {
    return { file, config: JSON.parse(file.text) };
  } catch {
    throw new ApiError(500, `${SITE_PATH} 가 JSON 형식이 아닙니다. GitHub 에서 직접 고쳐야 합니다.`);
  }
}

export async function handleGetSite(request, env) {
  const { file, config } = await loadSite(env);
  return json({ config, sha: file.sha });
}

export async function handlePutSite(request, env, me) {
  const input = await readJson(request, 1024 * 1024);
  const next = input.config;
  if (!next || typeof next !== 'object' || Array.isArray(next)) throw new ApiError(400, '구조(config)가 없습니다');
  const { file, config: current } = await loadSite(env);
  if (input.sha !== file.sha) throw new ApiError(409, CONFLICT_MSG, { conflict: true });

  const pinned = next.home && typeof next.home.pinned_lead === 'string' && next.home.pinned_lead.trim();
  const articles = pinned ? (await listArticles(env)).articles : null;
  const errors = validateSite(next, current, { deleted: input.deleted || {}, articles });
  if (errors.length) {
    throw new ApiError(400, `고칠 곳이 ${errors.length}군데 있습니다: ${errors[0].msg}`, { errors });
  }
  const changes = diffSite(current, next);
  // 파이썬 json.dump(indent=2, ensure_ascii=False) 와 같은 모양이다 — 고친 줄만 이력에 남는다
  const text = JSON.stringify(next, null, 2) + (file.text.endsWith('\n') ? '\n' : '');
  if (text === file.text) return json({ unchanged: true, sha: file.sha, changes: [] });

  const head = changes.length ? `${changes[0]}${changes.length > 1 ? ` 외 ${changes.length - 1}건` : ''}` : '형식 정리';
  const message = `편집실(${me.username}): 사이트 구조 — ${head}` + (changes.length > 1 ? '\n\n' + changes.map((c) => `- ${c}`).join('\n') : '');
  const res = await new GitHub(env).putFile(SITE_PATH, b64encode(utf8.encode(text)), file.sha, message);
  cache = null;
  await logChange(env, me.username, '사이트 구조 바꿈', SITE_PATH, changes.join('\n'));
  return json({ ok: true, sha: res.sha, commit: res.commit, changes });
}
