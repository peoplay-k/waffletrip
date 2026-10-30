// 서버 쪽 순수 함수 단위 테스트: 비밀번호, 권한표, 사진 판별, 목록 정렬.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hashPassword, verifyPassword } from '../../src/auth.js';
import { editPermission, allowedStatuses, sniffImage, sortArticles, checkName } from '../../src/articles.js';
import { timingSafeEqual, b64encode, b64decode } from '../../src/util.js';

const admin = { username: 'boss', role: 'admin' };
const rep = { username: 'kim', role: 'reporter' };

test('비밀번호: PBKDF2-SHA256 기본 2만 회(무료 요금제 CPU 10ms 안), 16바이트 소금, 맞으면 참', async () => {
  const h = await hashPassword('correct horse');
  assert.match(h.pw_hash, /^pbkdf2-sha256\$20000\$/);
  assert.equal(b64decode(h.pw_salt).length, 16);
  assert.equal(await verifyPassword('correct horse', h.pw_hash, h.pw_salt), true);
  assert.equal(await verifyPassword('correct horsf', h.pw_hash, h.pw_salt), false);
  assert.equal(await verifyPassword('', h.pw_hash, h.pw_salt), false);
  const h2 = await hashPassword('correct horse');
  assert.notEqual(h2.pw_salt, h.pw_salt, '소금은 매번 달라야');
  assert.notEqual(h2.pw_hash, h.pw_hash);
  assert.equal(await verifyPassword('x', 'md5$abc', h.pw_salt), false, '모르는 형식은 거절');
});

test('비밀번호 횟수는 설정을 따르고, 다른 횟수로 만든 옛 해시도 맞는다', async () => {
  const strong = await hashPassword('correct horse', { PASSWORD_ITERATIONS: '100000' });
  assert.match(strong.pw_hash, /^pbkdf2-sha256\$100000\$/);
  assert.equal(await verifyPassword('correct horse', strong.pw_hash, strong.pw_salt), true);
  // 범위 밖 설정은 기본값으로
  assert.match((await hashPassword('correct horse', { PASSWORD_ITERATIONS: '5' })).pw_hash, /^pbkdf2-sha256\$20000\$/);
  // 저장값의 터무니없는 횟수는 계산하지 않고 거절
  assert.equal(await verifyPassword('x', 'pbkdf2-sha256$99999999$AAAA', strong.pw_salt), false);
});

test('시간 차 없는 비교', () => {
  assert.equal(timingSafeEqual(new Uint8Array([1, 2, 3]), new Uint8Array([1, 2, 3])), true);
  assert.equal(timingSafeEqual(new Uint8Array([1, 2, 3]), new Uint8Array([1, 2, 4])), false);
  assert.equal(timingSafeEqual(new Uint8Array([1, 2]), new Uint8Array([1, 2, 3])), false);
});

test('권한표: 관리자는 전부', () => {
  for (const status of ['draft', 'review', 'approved', 'published', 'hidden', 'duplicate']) {
    assert.equal(editPermission(admin, { status, author: 'kim' }).ok, true);
  }
});

test('권한표: 기자는 자기 것 중 작성중·검토요청만', () => {
  assert.equal(editPermission(rep, { status: 'draft', author: 'kim' }).ok, true);
  assert.equal(editPermission(rep, { status: 'review', author: 'kim' }).ok, true);
  assert.equal(editPermission(rep, { status: 'approved', author: 'kim' }).ok, false);
  assert.equal(editPermission(rep, { status: 'published', author: 'kim' }).ok, false);
  assert.equal(editPermission(rep, { status: 'draft', author: 'lee' }).ok, false);
  assert.equal(editPermission(rep, { status: 'draft' }).ok, false, 'author 없는 파이프라인 원고');
});

test('고를 수 있는 상태', () => {
  assert.deepEqual(allowedStatuses(rep, { status: 'draft' }), ['draft', 'review']);
  assert.deepEqual(allowedStatuses(rep, {}, true), ['draft', 'review']);
  assert.deepEqual(allowedStatuses(admin, {}, true), ['draft', 'review', 'approved']);
  assert.deepEqual(allowedStatuses(admin, { status: 'review' }), ['draft', 'review', 'approved', 'hidden']);
  assert.deepEqual(allowedStatuses(admin, { status: 'published', published_id: 'c-1' }), ['published', 'hidden']);
  assert.deepEqual(allowedStatuses(admin, { status: 'hidden', published_id: 'c-1' }), ['published', 'hidden']);
  assert.deepEqual(allowedStatuses(admin, { status: 'duplicate' }), ['duplicate', 'draft', 'review', 'approved', 'hidden']);
  assert.ok(!allowedStatuses(admin, { status: 'draft' }).includes('published'), '발행된 적 없는 원고를 발행됨으로 둘 수 없다');
});

test('사진 판별은 파일 머리 바이트로', () => {
  assert.equal(sniffImage(new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 0])), 'jpg');
  assert.equal(sniffImage(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0])), 'png');
  const webp = new TextEncoder().encode('RIFF\u0000\u0000\u0000\u0000WEBPVP8 ');
  assert.equal(sniffImage(webp), 'webp');
  assert.equal(sniffImage(new TextEncoder().encode('<svg xmlns="http://www.w3.org/2000/svg"/>')), null);
  assert.equal(sniffImage(new TextEncoder().encode('GIF89a......')), null);
});

test('목록 정렬: 발행일(없으면 파일 이름 날짜) 내림차순, 같으면 파일 이름 내림차순', () => {
  const list = sortArticles([
    { path: '2026-10-28_a.md', published_on: '' },
    { path: '20261029_b.md', published_on: '2026-10-29' },
    { path: '20261030_c.md', published_on: '' },
    { path: '20261029_d.md', published_on: '2026-10-29' },
    { path: 'x.md', published_on: '' },
  ]);
  assert.deepEqual(list.map((a) => a.path), ['20261030_c.md', '20261029_d.md', '20261029_b.md', '2026-10-28_a.md', 'x.md']);
});

test('기사 파일 이름 검사', () => {
  checkName('20261030_괌-여행.md');
  for (const bad of ['../x.md', 'a/b.md', '.hidden.md', 'x.txt', '', 'a\\b.md']) {
    assert.throws(() => checkName(bad), /파일 이름/, bad);
  }
});

test('base64 왕복(큰 사진 크기)', () => {
  const big = new Uint8Array(3 * 1024 * 1024).map((_, i) => i % 251);
  assert.deepEqual(b64decode(b64encode(big)), big);
});
