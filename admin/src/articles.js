// 기사 원고(content/review/*.md) API.
// 권한은 여기서 판단한다 — 화면이 무엇을 보내든 서버가 다시 확인한다(설계 4절 권한표).

import { ApiError, json, readJson, b64encode, utf8, kstDate, randomHex, logChange, now } from './util.js';
import { GitHub, CONFLICT_MSG } from './github.js';
import {
  parseArticle, updateFrontText, serializeFront, joinDoc, articleMeta, deepEqual, cleanText,
} from './frontmatter.js';
import { getSiteConfig } from './site.js';

export const DIR = 'content/review';
export const UPLOAD_DIR = 'content/uploads';

export const STATUS_LABEL = {
  draft: '작성중', review: '검토요청', approved: '발행대기', published: '발행됨', hidden: '내림', duplicate: '중복',
};
// 화면에서 고칠 수 있는 칸. 나머지(id·published_id·sources …)는 파이프라인 칸이라 손대지 않는다.
export const EDITABLE = ['title', 'channel', 'region', 'category', 'topic', 'section', 'summary',
  'source_name', 'kind', 'source_url', 'photo', 'photo_hero', 'status'];
const SECTIONS = ['news', 'flight', 'data', 'promo'];
const KINDS = ['취재', '기획', '인터뷰', '해설', '보도자료'];
const MAX_BODY = 400 * 1024;

export function checkName(name) {
  if (typeof name !== 'string' || !/^[^/\\\x00-\x1f]{1,150}\.md$/.test(name) || name.startsWith('.')) {
    throw new ApiError(400, '기사 파일 이름이 틀렸습니다');
  }
}

// ── 권한 ────────────────────────────────────────────────────────────────

/** 이 사람이 이 기사를 고칠 수 있나. {ok, why} */
export function editPermission(me, front) {
  if (me.role === 'admin') return { ok: true };
  if ((front.author || '') !== me.username) return { ok: false, why: '다른 사람이 만든 기사는 고칠 수 없습니다(기자는 자기가 만든 기사만).' };
  if (!['draft', 'review'].includes(front.status)) {
    return { ok: false, why: `'${STATUS_LABEL[front.status] || front.status}' 상태의 기사는 관리자만 고칠 수 있습니다.` };
  }
  return { ok: true };
}

/** 고를 수 있는 상태. 지금 상태는 그대로 두고 저장할 수 있게 늘 넣는다. */
export function allowedStatuses(me, front, isNew = false) {
  let list;
  if (me.role !== 'admin') list = ['draft', 'review'];
  else if (isNew) list = ['draft', 'review', 'approved'];
  else if (front.published_id) {
    // 이미 지면에 나간 기사는 '발행됨'과 '내림' 사이만 오간다. 작성중으로 돌리면 파이프라인이 헷갈린다.
    list = ['published', 'hidden'];
  } else list = ['draft', 'review', 'approved', 'hidden'];
  if (!isNew && front.status && !list.includes(front.status) && me.role === 'admin') list = [front.status, ...list];
  return list;
}

// ── 목록 ────────────────────────────────────────────────────────────────

function dateFromName(name) {
  const m = /^(\d{4})-?(\d{2})-?(\d{2})_/.exec(name);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : '';
}

/** 최신이 위로: 발행일(없으면 파일 이름의 날짜) 내림차순, 같으면 파일 이름 내림차순 */
export function sortArticles(list) {
  const key = (a) => a.published_on || dateFromName(a.path);
  return list.sort((a, b) => {
    const ka = key(a);
    const kb = key(b);
    if (ka !== kb) return ka < kb ? 1 : -1;
    return a.path < b.path ? 1 : a.path > b.path ? -1 : 0;
  });
}

/**
 * 원고 목록. 폴더 해시가 같으면 저장해 둔 목록을 그대로 낸다.
 * 바뀌었으면 파일 내용 해시(블롭)별로 저장해 둔 요약을 쓰고, 새 블롭만 GitHub 에서 읽는다.
 * 처음(캐시가 비었을 때)은 폴더 전체를 GraphQL 한 번으로 내용까지 읽는다.
 */
export async function listArticles(env) {
  const gh = new GitHub(env);
  const tree = await gh.tree(DIR);
  if (!tree) return { articles: [], oid: null };
  const hit = await env.DB.prepare('SELECT list FROM list_cache WHERE tree_oid = ?').bind(tree.oid).first();
  if (hit) return { articles: JSON.parse(hit.list), oid: tree.oid, cached: true };

  const files = tree.entries.filter((e) => e.type === 'blob' && e.name.endsWith('.md'));
  const known = new Map();
  const uniq = [...new Set(files.map((f) => f.oid))];
  const reads = [];
  for (let i = 0; i < uniq.length; i += 90) {
    const part = uniq.slice(i, i + 90);
    reads.push(env.DB.prepare(`SELECT oid, meta FROM blob_meta WHERE oid IN (${part.map(() => '?').join(',')})`).bind(...part));
  }
  for (let i = 0; i < reads.length; i += 50) {
    for (const r of await env.DB.batch(reads.slice(i, i + 50))) {
      for (const row of r.results) known.set(row.oid, JSON.parse(row.meta));
    }
  }

  const missing = files.filter((f) => !known.has(f.oid));
  if (missing.length) {
    let texts;
    if (missing.length > 150) {
      const full = await gh.treeWithText(DIR);
      texts = new Map((full ? full.entries : []).map((e) => [e.oid, e.object && !e.object.isTruncated ? e.object.text : null]));
    } else {
      texts = await gh.blobs(missing.map((f) => f.oid));
    }
    const writes = [];
    for (const f of missing) {
      if (known.has(f.oid)) continue;
      let text = texts.get(f.oid);
      if (text === null || text === undefined) {
        const file = await gh.getFile(`${DIR}/${f.name}`);
        text = file ? file.text : '';
      }
      const { path, ...meta } = articleMeta(f.name, text);
      known.set(f.oid, meta);
      writes.push(env.DB.prepare('INSERT OR REPLACE INTO blob_meta (oid, meta, seen) VALUES (?, ?, ?)').bind(f.oid, JSON.stringify(meta), now()));
    }
    for (let i = 0; i < writes.length; i += 100) await env.DB.batch(writes.slice(i, i + 100));
  }

  const articles = sortArticles(files.map((f) => ({ path: f.name, ...known.get(f.oid) })));
  const packed = JSON.stringify(articles);
  // D1 한 칸은 2MB 까지다. 넘으면 목록 캐시는 건너뛴다(블롭 캐시만으로도 충분히 빠르다).
  if (packed.length < 1_800_000) {
    await env.DB.batch([
      env.DB.prepare('DELETE FROM list_cache WHERE tree_oid != ?').bind(tree.oid),
      env.DB.prepare('INSERT OR REPLACE INTO list_cache (tree_oid, list, created_at) VALUES (?, ?, ?)').bind(tree.oid, packed, now()),
    ]);
  }
  return { articles, oid: tree.oid, cached: false };
}

/** 저장 직후 새 파일의 요약을 미리 넣어 둔다 — 다음 목록에서 GitHub 를 덜 부른다. */
async function warmBlob(env, sha, name, text) {
  if (!sha) return;
  const { path, ...meta } = articleMeta(name, text);
  await env.DB.prepare('INSERT OR REPLACE INTO blob_meta (oid, meta, seen) VALUES (?, ?, ?)').bind(sha, JSON.stringify(meta), now()).run();
}

export async function handleList(request, env) {
  const { articles, oid } = await listArticles(env);
  return json({ articles, oid });
}

// ── 하나 읽기 ──────────────────────────────────────────────────────────

async function loadArticle(env, name) {
  checkName(name);
  const file = await new GitHub(env).getFile(`${DIR}/${name}`);
  if (!file) throw new ApiError(404, '그런 기사가 없습니다. 목록을 새로 고치세요.');
  let parsed;
  try {
    parsed = parseArticle(file.text);
  } catch (e) {
    throw new ApiError(422, `기사 앞머리(YAML)를 읽지 못했습니다: ${String(e.message).slice(0, 200)}. GitHub 에서 직접 고쳐야 합니다.`);
  }
  return { file, ...parsed };
}

export async function handleGet(request, env, me, name) {
  const { file, front, body } = await loadArticle(env, name);
  const perm = editPermission(me, front);
  return json({
    name, front, body, sha: file.sha,
    can: { edit: perm.ok, why: perm.why || '', statuses: perm.ok ? allowedStatuses(me, front) : [] },
  });
}

// ── 칸 검사 ─────────────────────────────────────────────────────────────

function str(v) {
  return v === null || v === undefined ? '' : cleanText(v);
}

/**
 * 화면에서 온 칸을 정리·검사해 next 에 넣는다. current 와 같은 값은 검사를 건너뛴다 —
 * 예전 기사에 남은 옛 값(필자 칸의 매체 이름 같은)이 있어도 다른 칸을 고쳐 저장할 수 있게.
 */
function applyFields(input, current, next, config, statuses) {
  const regionIds = new Set((config.regions || []).map((r) => r.id));
  const cultureIds = new Set((config.culture_sections || []).map((s) => s.id));
  const aliasIds = new Set(Object.keys(config.culture_aliases || {}));
  const travelIds = new Set((config.travel_sections || []).map((s) => s.id));
  const reporters = new Set((config.reporters || []).map((r) => r.name));
  const errs = [];
  const changed = (k) => !deepEqual(next[k], current[k]);

  for (const k of EDITABLE) {
    if (!(k in input)) continue;
    let v = input[k];
    if (k === 'photo_hero') v = v === true || v === 'true';
    else v = str(v).trim();
    if (k === 'summary') v = str(input[k]).trim();
    // 원래 없던 칸을 빈 값으로 새로 만들지 않는다(원고를 쓸데없이 바꾸지 않게)
    if (!(k in current) && (v === '' || v === false)) continue;
    next[k] = v;
  }

  const title = str(next.title).trim();
  if (!title) errs.push('제목을 넣으세요');
  else if (title.length > 200) errs.push('제목이 너무 깁니다(200자까지)');
  if (title.includes('\n')) errs.push('제목에 줄바꿈을 넣을 수 없습니다');
  if (!['travel', 'ent'].includes(next.channel)) errs.push('채널(여행·문화)을 고르세요');
  if (next.channel === 'travel') {
    if (!next.region) errs.push('여행 기사는 지역면을 고르세요');
    else if ((changed('region') || changed('channel')) && !regionIds.has(next.region)) errs.push(`지역 '${next.region}' 이 구조에 없습니다`);
    if (next.topic && changed('topic') && !travelIds.has(next.topic)) errs.push(`여행 부문 '${next.topic}' 이 구조에 없습니다`);
  }
  if (next.channel === 'ent' && next.category && (changed('category') || changed('channel'))
      && !cultureIds.has(next.category) && !aliasIds.has(next.category)) {
    errs.push(`문화 부문 '${next.category}' 이 구조에 없습니다`);
  }
  if (next.section && changed('section') && !SECTIONS.includes(next.section)) errs.push(`부문 '${next.section}' 은 고를 수 없습니다`);
  if (next.kind && changed('kind') && !KINDS.includes(next.kind)) errs.push(`기사 종류 '${next.kind}' 는 고를 수 없습니다`);
  if (next.source_name && changed('source_name') && !reporters.has(next.source_name)) {
    errs.push(`필자 '${next.source_name}' 은 기자 명부에 없습니다 — 명부에 있는 사람만 고를 수 있습니다`);
  }
  if (next.source_url && changed('source_url') && !/^https?:\/\/[^\s<>"]{3,2000}$/.test(next.source_url)) errs.push('원문 링크는 http:// 나 https:// 로 시작하는 주소여야 합니다');
  if (next.photo && changed('photo') && !/^\/(content\/uploads|assets)\/[A-Za-z0-9_\-./]+\.(jpe?g|png|webp)$/i.test(next.photo) || (next.photo && /\.\./.test(next.photo))) {
    errs.push('대표 사진 주소가 틀렸습니다 — 사진 올리기로 넣으세요');
  }
  if (typeof next.summary === 'string' && next.summary.length > 1000) errs.push('요약이 너무 깁니다(1000자까지)');
  if (errs.length) throw new ApiError(400, errs[0], { errors: errs });
  // 상태는 권한 문제다(기자는 발행대기·발행 불가) — 칸 오류(400)와 나눠 403 으로 답한다
  if (!statuses.includes(next.status)) {
    throw new ApiError(403, `'${STATUS_LABEL[next.status] || next.status || '빈 값'}' 상태로는 저장할 수 없습니다 (고를 수 있는 것: ${statuses.map((s) => STATUS_LABEL[s]).join('·')})`);
  }
}

function commitAction(before, after) {
  const t = String(after.title || '').slice(0, 60);
  if (before.status !== after.status) {
    if (after.status === 'hidden') return `기사 내림 — ${t}`;
    if (before.status === 'hidden' && after.status === 'published') return `기사 다시 올림 — ${t}`;
    return `${STATUS_LABEL[after.status] || after.status}(으)로 — ${t}`;
  }
  return `기사 고침 — ${t}`;
}

// ── 저장 ────────────────────────────────────────────────────────────────

export async function handlePut(request, env, me, name) {
  const input = await readJson(request, MAX_BODY + 64 * 1024);
  if (!input.front || typeof input.front !== 'object') throw new ApiError(400, '앞머리(front)가 없습니다');
  if (typeof input.body !== 'string') throw new ApiError(400, '본문(body)이 없습니다');
  if (input.body.length > MAX_BODY) throw new ApiError(413, '본문이 너무 깁니다');
  const { file, frontText, front, body, hasFront } = await loadArticle(env, name);
  if (!hasFront) throw new ApiError(422, '앞머리가 없는 파일은 편집실에서 고칠 수 없습니다');
  if (input.sha !== file.sha) throw new ApiError(409, CONFLICT_MSG, { conflict: true });

  const perm = editPermission(me, front);
  if (!perm.ok) throw new ApiError(403, perm.why);
  const next = structuredClone(front);
  applyFields(input.front, front, next, await getSiteConfig(env), allowedStatuses(me, front));
  // 기자가 다른 사람 기사로 바꾸지 못하게 author 는 늘 원래 값
  if ('author' in front) next.author = front.author;

  const newBody = cleanText(input.body);
  const newText = joinDoc(updateFrontText(frontText, front, next), deepEqual(newBody, body) ? body : newBody);
  if (newText === file.text) return json({ unchanged: true, sha: file.sha, name });

  const action = commitAction(front, next);
  const res = await new GitHub(env).putFile(`${DIR}/${name}`, b64encode(utf8.encode(newText)), file.sha, `편집실(${me.username}): ${action}`);
  await warmBlob(env, res.sha, name, newText);
  await logChange(env, me.username, action, name, front.status !== next.status ? `${front.status} → ${next.status}` : '');
  return json({ ok: true, sha: res.sha, commit: res.commit, name, status: next.status });
}

// ── 새 기사 ─────────────────────────────────────────────────────────────

function slugify(title) {
  // tools/new_article.py 의 slugify 와 같은 규칙(한글 그대로, 빈칸은 하이픈)
  const s = String(title).normalize('NFC').replace(/[^\p{L}\p{N}_\s-]/gu, '').trim().replace(/\s+/g, '-');
  return s.slice(0, 40).replace(/^-+|-+$/g, '') || 'article';
}

export async function handleCreate(request, env, me) {
  const input = await readJson(request, MAX_BODY + 64 * 1024);
  if (!input.front || typeof input.front !== 'object') throw new ApiError(400, '앞머리(front)가 없습니다');
  const body = cleanText(input.body || '');
  if (body.length > MAX_BODY) throw new ApiError(413, '본문이 너무 깁니다');

  const config = await getSiteConfig(env);
  // 칸 순서는 tools/new_article.py 가 만드는 원고와 같게 둔다
  const blank = { id: '', channel: '', region: '', category: '', section: 'news', title: '', source_name: '', kind: '취재', source_url: '', summary: '', status: 'draft' };
  const next = { ...blank };
  const f = input.front;
  applyFields({ ...f, topic: f.topic, photo: f.photo, photo_hero: f.photo_hero }, blank, next, config, allowedStatuses(me, {}, true));
  if (next.channel === 'ent') next.region = '';
  else next.category = '';

  const day = kstDate().replace(/-/g, '');
  const key = next.channel === 'ent' ? `ent-${next.category || 'startrip'}` : next.region;
  next.id = `art-${key}-${day}-${randomHex(3)}`;
  // 상태 다음 자리에 만든 사람(기록용)
  const ordered = {};
  for (const [k, v] of Object.entries(next)) if (k !== 'status') ordered[k] = v;
  ordered.status = next.status;
  ordered.author = me.username;

  const text = joinDoc(serializeFront(ordered), body.replace(/^\n+/, '\n'));
  const base = `${day}_${slugify(next.title)}`;
  const gh = new GitHub(env);
  const action = `새 기사 — ${String(next.title).slice(0, 60)}`;
  for (let i = 0; i < 6; i++) {
    const name = i === 0 ? `${base}.md` : i < 5 ? `${base}-${i + 1}.md` : `${base}-${randomHex(3)}.md`;
    try {
      const res = await gh.putFile(`${DIR}/${name}`, b64encode(utf8.encode(text)), null, `편집실(${me.username}): ${action}`);
      await warmBlob(env, res.sha, name, text);
      await logChange(env, me.username, action, name, next.status);
      return json({ ok: true, name, sha: res.sha, status: next.status }, 201);
    } catch (e) {
      if (!(e instanceof ApiError && e.extra && e.extra.exists)) throw e;
    }
  }
  throw new ApiError(409, '같은 이름의 기사 파일이 너무 많습니다. 제목을 바꿔 보세요.');
}

// ── 사진 ────────────────────────────────────────────────────────────────

const MAX_UPLOAD = 10 * 1024 * 1024;

/** 파일 머리 바이트로 종류를 본다. 브라우저가 보낸 Content-Type 은 믿지 않는다. */
export function sniffImage(b) {
  if (b.length > 3 && b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return 'jpg';
  if (b.length > 8 && b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47 && b[4] === 0x0d && b[5] === 0x0a && b[6] === 0x1a && b[7] === 0x0a) return 'png';
  if (b.length > 12 && String.fromCharCode(...b.subarray(0, 4)) === 'RIFF' && String.fromCharCode(...b.subarray(8, 12)) === 'WEBP') return 'webp';
  return null;
}

export async function handleUpload(request, env, me) {
  if (Number(request.headers.get('content-length') || 0) > MAX_UPLOAD + 64 * 1024) throw new ApiError(413, '사진은 10MB 까지 올릴 수 있습니다');
  const ct = request.headers.get('content-type') || '';
  let bytes;
  if (ct.startsWith('multipart/form-data')) {
    let form;
    try {
      form = await request.formData();
    } catch {
      throw new ApiError(400, '올린 파일을 읽지 못했습니다');
    }
    const file = form.get('file');
    if (!file || typeof file === 'string') throw new ApiError(400, '사진 파일이 없습니다');
    bytes = new Uint8Array(await file.arrayBuffer());
  } else {
    bytes = new Uint8Array(await request.arrayBuffer());
  }
  if (!bytes.length) throw new ApiError(400, '빈 파일입니다');
  if (bytes.length > MAX_UPLOAD) throw new ApiError(413, '사진은 10MB 까지 올릴 수 있습니다');
  const ext = sniffImage(bytes);
  if (!ext) throw new ApiError(415, '사진은 JPG·PNG·WEBP 만 올릴 수 있습니다');
  const name = `${kstDate().replace(/-/g, '')}_${randomHex(6)}.${ext}`;
  const res = await new GitHub(env).putFile(`${UPLOAD_DIR}/${name}`, b64encode(bytes), null, `편집실(${me.username}): 사진 올림 ${name}`);
  await logChange(env, me.username, '사진 올림', `${UPLOAD_DIR}/${name}`, `${bytes.length} bytes`);
  return json({ ok: true, path: `/${UPLOAD_DIR}/${name}`, sha: res.sha }, 201);
}

const MEDIA_TYPES = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };

/** 저장소의 사진을 편집실 화면에서 미리 보게 대신 받아 준다(지면에 반영되기 전 사진도 보이게). */
export async function handleMedia(request, env) {
  const p = new URL(request.url).searchParams.get('path') || '';
  const m = /^\/?((?:content\/uploads|assets)\/[A-Za-z0-9_\-./]+\.(jpe?g|png|webp))$/i.exec(p);
  if (!m || p.includes('..')) throw new ApiError(400, '사진 주소가 틀렸습니다');
  const res = await new GitHub(env).getRaw(m[1]);
  if (!res) throw new ApiError(404, '사진이 저장소에 없습니다(사진 반입이 옮겼거나 지웠을 수 있습니다)');
  return new Response(res.body, {
    headers: { 'Content-Type': MEDIA_TYPES[m[2].toLowerCase()], 'Cache-Control': 'private, max-age=300' },
  });
}
