// 테스트 무대: 임시 저장소 사본 + 가짜 GitHub + `wrangler dev --local`(D1 은 임시 폴더).
// e2e 테스트와 손으로 띄워 보는 `node test/harness.mjs` 가 같이 쓴다.

import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import { fileURLToPath } from 'node:url';
import { startMockGitHub, TOKEN } from './mock-github.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ADMIN_DIR = path.resolve(HERE, '..');
export const REPO_DIR = path.resolve(ADMIN_DIR, '..');

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.listen(0, '127.0.0.1', () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
    s.on('error', reject);
  });
}

async function waitFor(url, ms, proc) {
  const until = Date.now() + ms;
  while (Date.now() < until) {
    if (proc && proc.exitCode !== null) throw new Error(`wrangler dev 가 끝나 버렸습니다(종료 코드 ${proc.exitCode})`);
    try {
      const r = await fetch(url);
      if (r.status < 500) return;
    } catch { /* 아직 안 떴다 */ }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`${url} 가 ${ms / 1000}초 안에 뜨지 않았습니다`);
}

export async function startStage({ quiet = true } = {}) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'peopleroad-admin-'));
  const root = path.join(tmp, 'repo');
  fs.mkdirSync(path.join(root, 'content'), { recursive: true });
  fs.cpSync(path.join(REPO_DIR, 'content/review'), path.join(root, 'content/review'), { recursive: true });
  fs.mkdirSync(path.join(root, 'content/uploads'), { recursive: true });
  fs.mkdirSync(path.join(root, 'config'), { recursive: true });
  fs.copyFileSync(path.join(REPO_DIR, 'config/site.json'), path.join(root, 'config/site.json'));

  const mock = await startMockGitHub({ root });
  const state = path.join(tmp, 'state');
  const env = { ...process.env, WRANGLER_SEND_METRICS: 'false', CI: '1', NO_COLOR: '1' };
  const wrangler = path.join(ADMIN_DIR, 'node_modules/.bin/wrangler');

  const mig = spawnSync(wrangler, ['d1', 'migrations', 'apply', 'peopleroad-admin', '--local', '--persist-to', state], { cwd: ADMIN_DIR, env, encoding: 'utf8' });
  if (mig.status !== 0) throw new Error('D1 마이그레이션 실패\n' + mig.stdout + mig.stderr);

  const port = await freePort();
  const inspector = await freePort();
  const proc = spawn(wrangler, [
    'dev', '--local', '--ip', '127.0.0.1', '--port', String(port), '--inspector-port', String(inspector),
    '--persist-to', state,
    '--var', `GITHUB_API:http://127.0.0.1:${mock.port}`,
    '--var', `GITHUB_TOKEN:${TOKEN}`,
    '--var', 'ADMIN_SETUP_CODE:test',
  ], { cwd: ADMIN_DIR, env, stdio: ['ignore', 'pipe', 'pipe'] });
  let log = '';
  const keep = (d) => {
    log += d.toString();
    if (!quiet) process.stderr.write(d);
  };
  proc.stdout.on('data', keep);
  proc.stderr.on('data', keep);
  const base = `http://127.0.0.1:${port}`;
  try {
    await waitFor(`${base}/api/setup`, 90000, proc);
  } catch (e) {
    proc.kill('SIGTERM');
    await mock.close();
    throw new Error(e.message + '\n' + log.slice(-3000));
  }

  return {
    base, root, tmp, mock, mockBase: `http://127.0.0.1:${mock.port}`,
    log: () => log,
    /** 로컬 D1 에 SQL 을 돌려 줄 목록을 돌려준다(테스트에서 저장 모양을 확인하려고). */
    d1(sql) {
      const r = spawnSync(wrangler, ['d1', 'execute', 'peopleroad-admin', '--local', '--persist-to', state, '--json', '--command', sql], { cwd: ADMIN_DIR, env, encoding: 'utf8' });
      if (r.status !== 0) throw new Error('D1 조회 실패\n' + r.stdout + r.stderr);
      return JSON.parse(r.stdout)[0].results;
    },
    readRepo: (p) => fs.readFileSync(path.join(root, p), 'utf8'),
    async stop() {
      proc.kill('SIGTERM');
      await new Promise((r) => {
        if (proc.exitCode !== null) return r();
        const t = setTimeout(() => {
          proc.kill('SIGKILL');
          r();
        }, 5000);
        proc.on('exit', () => {
          clearTimeout(t);
          r();
        });
      });
      await mock.close();
      fs.rmSync(tmp, { recursive: true, force: true });
    },
  };
}

// 손으로 띄워 보기: node test/harness.mjs  → 주소를 알려 주고 Ctrl+C 까지 돈다(설치 코드: test)
if (import.meta.url === `file://${process.argv[1]}`) {
  const s = await startStage({ quiet: false });
  console.log(`\n편집실: ${s.base}  (설치 코드: test)\n가짜 GitHub: ${s.mockBase}\n임시 저장소: ${s.root}\n`);
  process.on('SIGINT', async () => {
    await s.stop();
    process.exit(0);
  });
}
