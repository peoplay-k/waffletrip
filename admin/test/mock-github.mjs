// 가짜 GitHub — 편집실이 쓰는 REST·GraphQL 만 흉내 낸다. 테스트 전용.
// 저장소는 임시 폴더(root)의 파일이다. 블롭 해시는 진짜 git 과 같은 방식(sha1("blob N\0"+내용))으로 낸다.
//
//   node test/mock-github.mjs <root> [port]      혼자 띄울 때
//
// 테스트용 뒷문(/__*): 커밋 목록 보기, 파일을 몰래 바꾸기(동시 편집 흉내), 호출 횟수 보기.

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const TOKEN = 'test-token';

function blobSha(buf) {
  return crypto.createHash('sha1').update(`blob ${buf.length}\0`).update(buf).digest('hex');
}

export function startMockGitHub({ root, port = 0, repo = 'peoplay-k/waffletrip', branch = 'main' }) {
  const blobs = new Map(); // oid → Buffer (지난 내용도 남겨 둔다, 진짜 git 처럼)
  const commits = [];
  const stats = { graphqlTree: 0, graphqlTreeText: 0, graphqlBlobs: 0, blobsRequested: 0, rest: 0 };
  const runs = [
    { id: 2, name: '매일 발행', display_title: '편집실(admin): 기사 고침', status: 'completed', conclusion: 'success', event: 'push', created_at: new Date(Date.now() - 3600e3).toISOString(), updated_at: new Date(Date.now() - 3000e3).toISOString(), html_url: 'https://github.com/x/runs/2' },
    { id: 1, name: '매일 발행', display_title: '매일 발행', status: 'completed', conclusion: 'failure', event: 'schedule', created_at: new Date(Date.now() - 86400e3).toISOString(), updated_at: new Date(Date.now() - 86000e3).toISOString(), html_url: 'https://github.com/x/runs/1' },
  ];

  const abs = (p) => {
    const full = path.resolve(root, p);
    if (!full.startsWith(path.resolve(root) + path.sep)) throw new Error('bad path');
    return full;
  };
  const readFile = (p) => {
    try {
      const st = fs.statSync(abs(p));
      if (!st.isFile()) return null;
      const buf = fs.readFileSync(abs(p));
      blobs.set(blobSha(buf), buf);
      return buf;
    } catch {
      return null;
    }
  };
  const writeFile = (p, buf) => {
    fs.mkdirSync(path.dirname(abs(p)), { recursive: true });
    fs.writeFileSync(abs(p), buf);
    blobs.set(blobSha(buf), buf);
  };
  const tree = (dir) => {
    let names;
    try {
      names = fs.readdirSync(abs(dir)).sort();
    } catch {
      return null;
    }
    const entries = names.filter((n) => fs.statSync(abs(`${dir}/${n}`)).isFile()).map((n) => {
      const buf = readFile(`${dir}/${n}`);
      return { name: n, type: 'blob', oid: blobSha(buf), buf };
    });
    const oid = crypto.createHash('sha1').update(entries.map((e) => `${e.name} ${e.oid}`).join('\n')).digest('hex');
    return { oid, entries };
  };

  const send = (res, status, data, headers = {}) => {
    const body = typeof data === 'string' || Buffer.isBuffer(data) ? data : JSON.stringify(data);
    res.writeHead(status, { 'Content-Type': 'application/json', ...headers });
    res.end(body);
  };

  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const raw = Buffer.concat(chunks);
    const url = new URL(req.url, 'http://x');
    const p = decodeURIComponent(url.pathname);

    // ── 테스트 뒷문 ──
    if (p === '/__commits') return send(res, 200, commits);
    if (p === '/__stats') return send(res, 200, stats);
    if (p === '/__read') {
      const buf = readFile(url.searchParams.get('path'));
      return buf ? send(res, 200, buf, { 'Content-Type': 'application/octet-stream' }) : send(res, 404, { message: 'Not Found' });
    }
    if (p === '/__write' && req.method === 'POST') {
      const { path: fp, text } = JSON.parse(raw.toString('utf8'));
      writeFile(fp, Buffer.from(text, 'utf8'));
      commits.push({ path: fp, message: '(바깥에서 고침)', sha: blobSha(Buffer.from(text, 'utf8')) });
      return send(res, 200, { ok: true });
    }

    if (req.headers.authorization !== `Bearer ${TOKEN}`) return send(res, 401, { message: 'Bad credentials' });
    if (!req.headers['user-agent']) return send(res, 403, { message: 'User-Agent required' });

    if (p === '/graphql' && req.method === 'POST') {
      const { query, variables } = JSON.parse(raw.toString('utf8'));
      const [owner, name] = repo.split('/');
      if (variables.owner !== owner || variables.name !== name) return send(res, 200, { data: { repository: null }, errors: [{ message: 'Could not resolve to a Repository' }] });
      if (variables.expr) {
        const [ref, dir] = variables.expr.split(':');
        if (ref !== branch) return send(res, 200, { data: { repository: { object: null } } });
        const t = tree(dir);
        if (!t) return send(res, 200, { data: { repository: { object: null } } });
        const withText = /entries\s*\{[^}]*object\s*\{/.test(query);
        if (withText) stats.graphqlTreeText++;
        else stats.graphqlTree++;
        return send(res, 200, {
          data: {
            repository: {
              object: {
                oid: t.oid,
                entries: t.entries.map((e) => ({
                  name: e.name, type: e.type, oid: e.oid,
                  ...(withText ? { object: { text: e.buf.toString('utf8'), isTruncated: false } } : {}),
                })),
              },
            },
          },
        });
      }
      const re = /(b\d+):object\(oid:"([0-9a-f]{40})"\)/g;
      const repoData = {};
      let m;
      let n = 0;
      while ((m = re.exec(query))) {
        n++;
        const buf = blobs.get(m[2]);
        repoData[m[1]] = buf ? { text: buf.toString('utf8'), isTruncated: false } : null;
      }
      if (!n) return send(res, 200, { errors: [{ message: 'mock: unsupported query' }] });
      stats.graphqlBlobs++;
      stats.blobsRequested += n;
      return send(res, 200, { data: { repository: repoData } });
    }

    const prefix = `/repos/${repo}`;
    if (!p.startsWith(prefix + '/')) return send(res, 404, { message: 'Not Found' });
    const rest = p.slice(prefix.length);
    stats.rest++;

    if (rest.startsWith('/contents/')) {
      const fp = rest.slice('/contents/'.length);
      if (req.method === 'GET') {
        if ((url.searchParams.get('ref') || branch) !== branch) return send(res, 404, { message: 'No commit found for the ref' });
        const buf = readFile(fp);
        if (!buf) return send(res, 404, { message: 'Not Found' });
        if ((req.headers.accept || '').includes('application/vnd.github.raw')) {
          return send(res, 200, buf, { 'Content-Type': 'application/octet-stream' });
        }
        return send(res, 200, {
          type: 'file', name: path.basename(fp), path: fp, sha: blobSha(buf), size: buf.length,
          encoding: 'base64', content: buf.toString('base64').replace(/(.{60})/g, '$1\n'),
        });
      }
      if (req.method === 'PUT') {
        const body = JSON.parse(raw.toString('utf8'));
        if (!body.message || typeof body.content !== 'string') return send(res, 422, { message: 'Invalid request.' });
        if (body.branch && body.branch !== branch) return send(res, 422, { message: 'Branch not found' });
        const cur = readFile(fp);
        if (cur && !body.sha) return send(res, 422, { message: 'Invalid request.\n\n"sha" wasn\'t supplied.' });
        if (cur && body.sha !== blobSha(cur)) return send(res, 409, { message: `${fp} does not match ${body.sha}` });
        if (!cur && body.sha) return send(res, 409, { message: 'sha does not match' });
        const buf = Buffer.from(body.content, 'base64');
        writeFile(fp, buf);
        const sha = blobSha(buf);
        const commit = crypto.createHash('sha1').update(`${commits.length}:${fp}:${sha}`).digest('hex');
        commits.push({ path: fp, message: body.message, sha, commit });
        if (/^content\/review\/.+\.md$/.test(fp)) {
          // 진짜 GitHub 처럼 푸시가 '매일 발행'을 깨운다 — 시험에서는 바로 끝난 것으로 둔다
          const id = runs.length + 1;
          runs.unshift({ id, name: '매일 발행', display_title: String(body.message).split('\n')[0], status: 'completed', conclusion: 'success', event: 'push', head_sha: commit, created_at: new Date(Date.now() - 30000).toISOString(), updated_at: new Date().toISOString(), html_url: `https://github.com/x/runs/${id}` });
        }
        return send(res, cur ? 200 : 201, { content: { name: path.basename(fp), path: fp, sha }, commit: { sha: commit, message: body.message } });
      }
    }

    const wf = /^\/actions\/workflows\/([^/]+)\/(runs|dispatches)$/.exec(rest);
    if (wf) {
      if (wf[1] !== 'daily.yml') return send(res, 404, { message: 'Not Found' });
      if (wf[2] === 'runs' && req.method === 'GET') {
        // 띄운 지 20초 지난 실행은 끝난 것으로 친다
        for (const r of runs) {
          if (r.status !== 'completed' && Date.now() - Date.parse(r.created_at) > 20000) {
            r.status = 'completed';
            r.conclusion = 'success';
            r.updated_at = new Date().toISOString();
          }
        }
        const n = Number(url.searchParams.get('per_page') || 30);
        return send(res, 200, { total_count: runs.length, workflow_runs: runs.slice(0, n) });
      }
      if (wf[2] === 'dispatches' && req.method === 'POST') {
        const body = JSON.parse(raw.toString('utf8') || '{}');
        if (body.ref !== branch) return send(res, 422, { message: 'No ref found' });
        const id = runs.length + 1;
        runs.unshift({ id, name: '매일 발행', display_title: '매일 발행', status: 'in_progress', conclusion: null, event: 'workflow_dispatch', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), html_url: `https://github.com/x/runs/${id}` });
        res.writeHead(204);
        return res.end();
      }
    }
    return send(res, 404, { message: 'Not Found' });
  });

  return new Promise((resolve) => {
    server.listen(port, '127.0.0.1', () => {
      resolve({ server, port: server.address().port, commits, stats, close: () => new Promise((r) => server.close(r)) });
    });
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const root = process.argv[2];
  if (!root) {
    console.error('쓰는 법: node test/mock-github.mjs <저장소 폴더> [포트]');
    process.exit(1);
  }
  const m = await startMockGitHub({ root, port: Number(process.argv[3] || 8790) });
  console.log(`가짜 GitHub: http://127.0.0.1:${m.port} (토큰: ${TOKEN})`);
}
