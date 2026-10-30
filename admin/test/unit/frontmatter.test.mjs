// 앞머리 읽기·쓰기 단위 테스트. content/review 의 진짜 원고 전부로 돌린다.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  splitDoc, parseArticle, parseFront, segment, updateFrontText, serializeFront, joinDoc, emitString, cleanText, articleMeta,
} from '../../src/frontmatter.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REVIEW = path.resolve(HERE, '../../../content/review');
const files = fs.readdirSync(REVIEW).filter((f) => f.endsWith('.md')).sort();
const read = (f) => fs.readFileSync(path.join(REVIEW, f), 'utf8');

// 파이프라인 칸: 편집실 저장으로 한 글자도 바뀌면 안 된다
const PIPELINE = ['id', 'published_id', 'published_on', 'sources', 'reason', 'duplicate_of', 'photo_note'];

/** PyYAML 로 여러 글을 읽는다. 파이썬·PyYAML 이 없으면 null(그 검사는 건너뛴다). */
function pyyaml(texts) {
  const r = spawnSync('python3', ['-I', path.join(HERE, 'pyyaml_load.py')], { input: JSON.stringify(texts), encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
  if (r.status !== 0) return null;
  return JSON.parse(r.stdout);
}
const HAS_PYYAML = pyyaml(['a: 1']) !== null;

test(`진짜 원고 ${files.length}개가 있다`, () => {
  assert.ok(files.length > 100, '원고가 너무 적다 — 경로를 확인');
});

test('모든 원고: 읽기 → 고치지 않고 쓰기 = 글자 하나 다르지 않다', () => {
  for (const f of files) {
    const raw = read(f);
    const a = parseArticle(raw);
    assert.ok(a.hasFront, `${f}: 앞머리를 못 찾음`);
    assert.ok(segment(a.frontText).ok, `${f}: 칸 단위로 자르지 못함`);
    const again = joinDoc(updateFrontText(a.frontText, a.front, structuredClone(a.front)), a.body);
    assert.equal(again, raw, `${f}: 바뀐 것이 없는데 글이 달라짐`);
  }
});

test('모든 원고: 통째로 다시 써도(새 원고 출력기) 같은 값으로 읽힌다', () => {
  for (const f of files) {
    const a = parseArticle(read(f));
    const out = serializeFront(a.front);
    assert.deepEqual(parseFront(out), a.front, `${f}: 다시 쓴 앞머리의 값이 다름`);
    assert.deepEqual(Object.keys(parseFront(out)), Object.keys(a.front), `${f}: 칸 순서가 다름`);
  }
});

test('모든 원고: PyYAML(파이프라인)도 다시 쓴 앞머리를 원래와 같게 읽는다', { skip: !HAS_PYYAML && 'python3 + PyYAML 없음' }, () => {
  const originals = [];
  const rewritten = [];
  for (const f of files) {
    const a = parseArticle(read(f));
    originals.push(a.frontText);
    rewritten.push(serializeFront(a.front));
  }
  const A = pyyaml(originals);
  const B = pyyaml(rewritten);
  files.forEach((f, i) => assert.deepEqual(B[i], A[i], `${f}: PyYAML 이 다르게 읽음`));
});

const TRICKY = [
  'yes', 'No', 'on', 'OFF', 'y', 'n', 'true', 'null', '~', '', ' ', '2026-10-30', '2026-10-30 10:00', '1:20', '0777', '0x1F', '1_000',
  '1e3', '.5', '.inf', '-.inf', '.nan', '12', '-3', '+4', '3.14', '- 목록 아님', '#해시', 'a: b', 'a #b', 'a:b', '끝에 콜론:', "it's", '"따옴표"',
  ' 앞 빈칸', '뒤 빈칸 ', '@멘션', '`코드`', '%퍼센트', '!느낌표', '&앵커', '*별', '|', '>', '?', '[괄호]', '{중괄호}', '<<', '=',
  '줄\n바꿈', '탭\t문자', '세 줄\n\n띄움', '---', '제목 --- 가운데', '----', '…말줄임', '“둥근 따옴표”', '이모지 😀', '\u2028줄구분', 'é', '中文',
  'KBS2 \'욕망의 덫\' 48회, 현재의 유품', '[단독] 괌 여행: 지금 가도 될까?', '가격 $100 #특가', '100%', 'C:\\경로', 'https://example.com/?a=1#x',
];

test('까다로운 문자열: 출력 → yaml 패키지·PyYAML 모두 원래 문자열로 읽는다', () => {
  const texts = TRICKY.map((s) => `k: ${emitString(s)}\n`);
  texts.forEach((t, i) => {
    assert.equal(parseFront(t).k, TRICKY[i], `yaml 패키지: ${JSON.stringify(TRICKY[i])} → ${t}`);
    assert.ok(!t.slice(3).includes('---'), `'---' 가 글자 그대로 남음: ${t}`);
  });
  if (HAS_PYYAML) {
    const got = pyyaml(texts);
    got.forEach((g, i) => assert.equal(g.k, TRICKY[i], `PyYAML: ${JSON.stringify(TRICKY[i])} → ${texts[i]}`));
  }
});

test('모든 원고: 편집 칸을 고치면 그 칸만 바뀌고 파이프라인 칸·모르는 칸·순서는 그대로', () => {
  const edited = [];
  for (const [i, f] of files.entries()) {
    const raw = read(f);
    const a = parseArticle(raw);
    const next = structuredClone(a.front);
    next.title = TRICKY[i % TRICKY.length] || '새 제목';
    next.summary = '요약 첫 줄\n둘째 줄: "따옴표" 와 \'홑따옴표\'';
    next.status = 'hidden';
    next.photo_hero = true; // 없던 칸은 끝에 붙는다
    const text = updateFrontText(a.frontText, a.front, next);
    const back = parseFront(text);
    assert.equal(back.title, next.title, f);
    assert.equal(back.summary, next.summary, f);
    assert.equal(back.status, 'hidden', f);
    assert.equal(back.photo_hero, true, f);
    // 고치지 않은 칸은 원래 글자 덩어리가 그대로 들어 있다
    const seg = segment(a.frontText);
    for (const b of seg.blocks) {
      if (['title', 'summary', 'status'].includes(b.key)) continue;
      assert.ok(text.includes(b.text), `${f}: '${b.key}' 칸의 글자가 바뀜`);
      assert.deepEqual(back[b.key], a.front[b.key], `${f}: '${b.key}' 값이 바뀜`);
    }
    for (const k of PIPELINE) if (k in a.front) assert.deepEqual(back[k], a.front[k], `${f}: 파이프라인 칸 ${k}`);
    // 원래 칸은 원래 자리에, 새 칸은 끝에 붙는다
    assert.deepEqual(Object.keys(back), [...Object.keys(a.front), ...Object.keys(next).filter((k) => !(k in a.front))], `${f}: 칸 순서`);
    edited.push({ text, next });
  }
  if (HAS_PYYAML) {
    const got = pyyaml(edited.map((e) => e.text));
    got.forEach((g, i) => {
      assert.equal(g.title, edited[i].next.title, `PyYAML title ${files[i]}`);
      assert.equal(g.summary, edited[i].next.summary, `PyYAML summary ${files[i]}`);
      assert.equal(g.status, 'hidden');
    });
  }
});

test('모르는 칸(중첩 값 포함)은 다른 칸을 고쳐도 그대로 남는다', () => {
  const raw = '---\nid: x1\ncustom_map:\n  a: 1\n  b:\n  - 가\n  - 나\ntitle: 옛 제목\nweird_list:\n- {k: v}\n- [1, 2]\nstatus: draft\n---\n본문\n';
  const a = parseArticle(raw);
  const next = { ...structuredClone(a.front), title: '새 제목' };
  const out = joinDoc(updateFrontText(a.frontText, a.front, next), a.body);
  assert.equal(out, raw.replace('title: 옛 제목', 'title: 새 제목'));
});

test('나누기: 앞머리 없음·CRLF·BOM·본문 속 --- ', () => {
  assert.deepEqual(splitDoc('그냥 글'), { hasFront: false, frontText: '', body: '그냥 글' });
  assert.equal(splitDoc('---\na: 1\n').hasFront, false, '닫는 줄이 없으면 앞머리가 아니다');
  const crlf = splitDoc('---\r\na: 1\r\n---\r\n본문');
  assert.equal(crlf.hasFront, true);
  assert.equal(crlf.body, '본문');
  assert.equal(splitDoc('\ufeff---\na: 1\n---\nb').body, 'b');
  const hr = splitDoc('---\na: 1\n---\n위\n\n---\n\n아래\n');
  assert.equal(hr.body, '위\n\n---\n\n아래\n');
  assert.deepEqual(parseFront(hr.frontText), { a: 1 });
});

test('화면 글자 정리: CRLF·제어 문자', () => {
  assert.equal(cleanText('가\r\n나\r다\u0000\u0007\u0085'), '가\n나\n다');
  assert.equal(cleanText(null), '');
});

test('목록 요약: 깨진 앞머리는 오류 표시로', () => {
  const m = articleMeta('x.md', '---\ntitle: [깨짐\n---\n');
  assert.equal(m.status, 'error');
  const ok = articleMeta('y.md', "---\ntitle: 제목\npublished_on: '2026-10-30'\nstatus: published\n---\n");
  assert.equal(ok.title, '제목');
  assert.equal(ok.published_on, '2026-10-30');
  const date = articleMeta('z.md', '---\ntitle: t\npublished_on: 2026-10-30\n---\n');
  assert.equal(date.published_on, '2026-10-30', '따옴표 없는 날짜도 문자열로');
});
