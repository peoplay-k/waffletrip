// GitHub 저장소 읽기·쓰기. 토큰은 서버 비밀값(GITHUB_TOKEN)으로만 있고 화면에는 가지 않는다.
// 주소(GITHUB_API)를 바꿀 수 있게 둔 것은 테스트가 가짜 GitHub 를 띄우려고다.

import { ApiError, b64decode, utf8 } from './util.js';

export const CONFLICT_MSG = '그사이 다른 사람이 고쳤습니다. 새로 불러온 뒤 다시 고치세요.';

export class GitHub {
  constructor(env) {
    this.api = String(env.GITHUB_API || 'https://api.github.com').replace(/\/+$/, '');
    this.repo = env.GITHUB_REPO || 'peoplay-k/waffletrip';
    this.branch = env.GITHUB_BRANCH || 'main';
    this.token = env.GITHUB_TOKEN;
    [this.owner, this.name] = this.repo.split('/');
  }

  async req(method, path, { body, accept } = {}) {
    if (!this.token) throw new ApiError(503, '서버에 GitHub 토큰(GITHUB_TOKEN)이 설정되지 않았습니다. 관리자에게 알리세요.');
    const headers = {
      Authorization: `Bearer ${this.token}`,
      Accept: accept || 'application/vnd.github+json',
      'User-Agent': 'peopleroad-admin',
      'X-GitHub-Api-Version': '2022-11-28',
    };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    let res;
    try {
      res = await fetch(this.api + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch (e) {
      console.error('GitHub 연결 실패', e);
      throw new ApiError(502, 'GitHub 에 연결하지 못했습니다. 잠시 뒤 다시 하세요.');
    }
    return res;
  }

  /** 4xx/5xx 를 화면에 보일 문장으로 바꾼다. */
  async fail(res, what) {
    let msg = '';
    try {
      msg = (await res.json()).message || '';
    } catch { /* 본문 없음 */ }
    console.error(`GitHub ${what} 실패`, res.status, msg);
    if (res.status === 401) throw new ApiError(502, 'GitHub 토큰이 맞지 않거나 만료되었습니다. 관리자에게 알리세요.');
    if (res.status === 403 || res.status === 429) {
      if (/rate limit/i.test(msg) || res.headers.get('x-ratelimit-remaining') === '0') {
        throw new ApiError(503, 'GitHub 사용 한도를 넘었습니다. 몇 분 뒤 다시 하세요.');
      }
      throw new ApiError(502, 'GitHub 토큰에 이 일을 할 권한이 없습니다. 관리자에게 알리세요.');
    }
    throw new ApiError(502, `GitHub ${what} 중 오류가 났습니다(${res.status}). 잠시 뒤 다시 하세요.`);
  }

  contentsPath(path) {
    return `/repos/${this.repo}/contents/${path.split('/').map(encodeURIComponent).join('/')}`;
  }

  /** 파일 → {text, sha} 또는 없으면 null. */
  async getFile(path) {
    const res = await this.req('GET', `${this.contentsPath(path)}?ref=${encodeURIComponent(this.branch)}`);
    if (res.status === 404) return null;
    if (!res.ok) await this.fail(res, '파일 읽기');
    const data = await res.json();
    if (Array.isArray(data) || data.type !== 'file') throw new ApiError(400, '파일이 아니라 폴더입니다');
    let bytes;
    if (data.encoding === 'base64' && data.content) bytes = b64decode(data.content);
    else {
      // 1MB 가 넘으면 contents API 가 내용을 비워 준다 — 원본으로 다시 받는다
      const raw = await this.getRaw(path);
      if (!raw) return null;
      bytes = new Uint8Array(await raw.arrayBuffer());
    }
    return { text: utf8.decode(bytes), sha: data.sha };
  }

  /** 원본 바이트 응답(사진 미리보기용). 없으면 null. */
  async getRaw(path) {
    const res = await this.req('GET', `${this.contentsPath(path)}?ref=${encodeURIComponent(this.branch)}`, { accept: 'application/vnd.github.raw' });
    if (res.status === 404) return null;
    if (!res.ok) await this.fail(res, '파일 읽기');
    return res;
  }

  /**
   * 파일 쓰기(커밋). sha 는 고치기 전 파일의 해시 — 새 파일이면 null.
   * 그사이 파일이 바뀌었으면 409(ApiError, conflict:true).
   * 돌려주는 값: {sha: 새 파일 해시, commit: 커밋 해시}
   */
  async putFile(path, contentB64, sha, message) {
    const body = { message, content: contentB64, branch: this.branch };
    if (sha) body.sha = sha;
    for (let attempt = 0; attempt < 2; attempt++) {
      const res = await this.req('PUT', this.contentsPath(path), { body });
      if (res.ok) {
        const data = await res.json();
        return { sha: data.content && data.content.sha, commit: data.commit && data.commit.sha };
      }
      if (res.status === 409 || res.status === 422) {
        let msg = '';
        try {
          msg = (await res.json()).message || '';
        } catch { /* 본문 없음 */ }
        if (res.status === 422 && !/sha/i.test(msg)) throw new ApiError(422, `GitHub 가 저장을 거절했습니다: ${msg}`);
        // 같은 순간 다른 파일 커밋으로 브랜치 끝만 움직인 경우가 있다. 이 파일이 그대로면 한 번 더 한다.
        if (attempt === 0 && sha) {
          const cur = await this.getFile(path);
          if (cur && cur.sha === sha) continue;
        }
        if (!sha && res.status === 422) throw new ApiError(409, '같은 이름의 파일이 이미 있습니다', { conflict: true, exists: true });
        throw new ApiError(409, CONFLICT_MSG, { conflict: true });
      }
      await this.fail(res, '저장');
    }
    throw new ApiError(409, CONFLICT_MSG, { conflict: true });
  }

  async graphql(query, variables = {}) {
    const res = await this.req('POST', '/graphql', { body: { query, variables } });
    if (!res.ok) await this.fail(res, '목록 읽기');
    const data = await res.json();
    if (data.errors && data.errors.length) {
      console.error('GraphQL 오류', JSON.stringify(data.errors).slice(0, 500));
      throw new ApiError(502, 'GitHub 에서 목록을 읽지 못했습니다. 잠시 뒤 다시 하세요.');
    }
    return data.data;
  }

  /** 폴더의 파일 이름·해시(내용 없이). → {oid, entries:[{name, oid, type}]} 또는 null */
  async tree(dir) {
    const q = `query($owner:String!,$name:String!,$expr:String!){repository(owner:$owner,name:$name){object(expression:$expr){... on Tree{oid entries{name type oid}}}}}`;
    const d = await this.graphql(q, { owner: this.owner, name: this.name, expr: `${this.branch}:${dir}` });
    const obj = d && d.repository && d.repository.object;
    return obj && obj.entries ? obj : null;
  }

  /** 폴더의 파일을 내용까지 한 번에(처음 한 번, 캐시가 비었을 때). */
  async treeWithText(dir) {
    const q = `query($owner:String!,$name:String!,$expr:String!){repository(owner:$owner,name:$name){object(expression:$expr){... on Tree{oid entries{name type oid object{... on Blob{text isTruncated}}}}}}}`;
    const d = await this.graphql(q, { owner: this.owner, name: this.name, expr: `${this.branch}:${dir}` });
    const obj = d && d.repository && d.repository.object;
    return obj && obj.entries ? obj : null;
  }

  /** 블롭 해시 여러 개의 내용을 한 번에. → Map(oid → text|null) */
  async blobs(oids) {
    const out = new Map();
    for (let i = 0; i < oids.length; i += 100) {
      const part = oids.slice(i, i + 100).filter((o) => /^[0-9a-f]{40}$/.test(o));
      if (!part.length) continue;
      const fields = part.map((o, j) => `b${j}:object(oid:"${o}"){... on Blob{text isTruncated}}`).join(' ');
      const q = `query($owner:String!,$name:String!){repository(owner:$owner,name:$name){${fields}}}`;
      const d = await this.graphql(q, { owner: this.owner, name: this.name });
      part.forEach((o, j) => {
        const b = d && d.repository && d.repository[`b${j}`];
        out.set(o, b && !b.isTruncated ? b.text : null);
      });
    }
    return out;
  }

  async workflowRuns(workflow, n = 6) {
    const res = await this.req('GET', `/repos/${this.repo}/actions/workflows/${encodeURIComponent(workflow)}/runs?per_page=${n}`);
    if (!res.ok) await this.fail(res, '발행 상태 읽기');
    return (await res.json()).workflow_runs || [];
  }

  async dispatch(workflow) {
    const res = await this.req('POST', `/repos/${this.repo}/actions/workflows/${encodeURIComponent(workflow)}/dispatches`, { body: { ref: this.branch } });
    if (!res.ok) await this.fail(res, '발행 시작');
  }
}
