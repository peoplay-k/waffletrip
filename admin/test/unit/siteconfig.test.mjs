// 구조 파일 검사·요약 단위 테스트. 진짜 config/site.json 으로 돌린다.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateSite, diffSite } from '../../public/shared/siteconfig.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = JSON.parse(fs.readFileSync(path.resolve(HERE, '../../../config/site.json'), 'utf8'));
const clone = () => structuredClone(SITE);
const msgs = (errs) => errs.map((e) => e.msg).join('\n');
const has = (errs, re) => assert.match(msgs(errs), re, `기대한 오류가 없음: ${re}\n받은 오류:\n${msgs(errs)}`);

test('지금 구조 파일은 그대로 통과한다', () => {
  assert.deepEqual(validateSite(SITE, SITE), []);
});

test('id 형식·겹침', () => {
  const c = clone();
  c.travel_sections.push({ id: 'News!', name: 'x', desc: '', visible: true });
  c.culture_sections.push({ id: 'movie', name: '또 영화', desc: '', visible: true });
  c.regions.push({ id: 'a', name: '짧은 id', keywords: [], desk_duty: '', visible: true });
  const e = validateSite(c, SITE);
  has(e, /여행 부문.*'News!'.*2~24자/);
  has(e, /문화 부문.*'movie' 가 겹칩니다/);
  has(e, /지역.*'a'.*2~24자/);
});

test('이름이 비면 막는다', () => {
  const c = clone();
  c.culture_sections[0].name = '  ';
  c.channels.ent.name = '';
  has(validateSite(c, SITE), /이름이 비었습니다/);
  has(validateSite(c, SITE), /문화 채널 이름이 비었습니다/);
});

test('채널 소개 글(desc)은 비어도 되고 글자여야 한다', () => {
  const c = clone();
  c.channels.travel.desc = '';
  assert.deepEqual(validateSite(c, SITE), []);
  delete c.channels.travel.desc;
  assert.deepEqual(validateSite(c, SITE), []);
  c.channels.ent.desc = 3;
  has(validateSite(c, SITE), /문화 채널 소개 글이 글자가 아닙니다/);
});

test('지역은 지울 수 없다(숨기기만)', () => {
  const c = clone();
  c.regions = c.regions.filter((r) => r.id !== 'laos');
  c.reporters.forEach((p) => { p.beats = p.beats.filter((b) => b !== 'laos'); });
  has(validateSite(c, SITE), /지역 'laos' 은 지울 수 없습니다/);
  const ok = clone();
  ok.regions.find((r) => r.id === 'laos').visible = false;
  assert.deepEqual(validateSite(ok, SITE), []);
});

test('지역 id 를 바꾸면 지운 것으로 보고 막는다', () => {
  const c = clone();
  c.regions.find((r) => r.id === 'kota').id = 'kotakinabalu';
  c.reporters.forEach((p) => { p.beats = p.beats.map((b) => (b === 'kota' ? 'kotakinabalu' : b)); });
  has(validateSite(c, SITE), /'kota' 은 지울 수 없습니다/);
});

test('부문 id 는 바꿀 수 없고, 지우려면 지운다고 밝혀야 한다', () => {
  const c = clone();
  c.culture_sections.find((s) => s.id === 'music').id = 'musics';
  c.culture_rules.forEach((r) => { if (r.section === 'music') r.section = 'musics'; });
  has(validateSite(c, SITE), /id 'music' 가 사라졌습니다/);

  const d = clone();
  d.culture_sections = d.culture_sections.filter((s) => s.id !== 'music');
  d.culture_rules = d.culture_rules.filter((r) => r.section !== 'music');
  has(validateSite(d, SITE), /'music' 가 사라졌습니다/);
  assert.deepEqual(validateSite(d, SITE, { deleted: { culture_sections: ['music'] } }), []);
});

test('기본 부문은 지울 수 없다', () => {
  const c = clone();
  c.travel_sections = c.travel_sections.filter((s) => s.id !== 'news');
  has(validateSite(c, SITE, { deleted: { travel_sections: ['news'] } }), /'news' 은 기본 부문이라 지울 수 없습니다/);
  const d = clone();
  d.culture_sections = d.culture_sections.filter((s) => s.id !== 'startrip');
  d.culture_rules = d.culture_rules.filter((r) => r.section !== 'startrip');
  d.culture_aliases.star = 'movie';
  has(validateSite(d, SITE, { deleted: { culture_sections: ['startrip'] } }), /'startrip' 은 기본 부문/);
});

test('문화 분류 규칙의 부문은 있어야 하고 낱말은 비면 안 된다', () => {
  const c = clone();
  c.culture_rules.push({ section: 'nope', keywords: [] });
  c.culture_rules[0].keywords.push('촬영지');
  const e = validateSite(c, SITE);
  has(e, /부문 'nope' 이 문화 부문 목록에 없습니다/);
  has(e, /낱말이 하나도 없습니다/);
  has(e, /낱말 '촬영지' 이 두 번/);
});

test('옛 부문 이름표가 없는 부문을 가리키면 막는다', () => {
  const c = clone();
  c.culture_aliases.old = 'gone';
  has(validateSite(c, SITE), /옛 부문 'old'/);
});

test('기자 담당은 지역 id·ent·data 만, 기본 기자는 명부에 있어야', () => {
  const c = clone();
  c.reporters[0].beats.push('mars');
  c.reporters.push({ name: '김태성', beats: [] });
  c.general_reporter = '없는사람';
  const e = validateSite(c, SITE);
  has(e, /담당 'mars'/);
  has(e, /같은 이름의 기자가 이미 있습니다/);
  has(e, /기본 기자 '없는사람'/);
});

test('홈 숫자 범위·묶음 순서·고정 머리기사', () => {
  const c = clone();
  c.home.hero_count = 0;
  c.home.latest_count = 999;
  c.home.travel_block_size = '5';
  c.home.order = ['travel', 'ads', 'travel'];
  c.home.show_video = 'yes';
  c.home.pinned_lead = 'c-123';
  const articles = [{ published_id: 'c-999', status: 'published', title: 'x' }];
  const e = validateSite(c, SITE, { articles });
  has(e, /넘기는 큰 기사 수는 1~8/);
  has(e, /최신 기사 수는 0~30/);
  has(e, /여행 묶음 기사 수는 1~30/);
  has(e, /모르는 묶음 'ads'/);
  has(e, /두 번 들어 있습니다/);
  has(e, /영상 보이기/);
  has(e, /고정 머리기사 'c-123' 를 발행된 기사에서 찾을 수 없습니다/);
  const ok = clone();
  ok.home.pinned_lead = 'c-999';
  assert.deepEqual(validateSite(ok, SITE, { articles }), []);
  has(validateSite(ok, SITE, { articles: [{ published_id: 'c-999', status: 'hidden', title: '내린 기사' }] }), /발행 상태가 아닙니다/);
});

test('지역 날씨·통화 형식', () => {
  const c = clone();
  c.regions[0].weather.lat = 200;
  c.regions[0].currency = 'usd';
  c.regions[1].weather = { city: '', lat: 0, lon: 0 };
  const e = validateSite(c, SITE);
  has(e, /위도는 -90~90/);
  has(e, /통화 'usd' 는 환율을 낼 수 없습니다/);
  has(e, /날씨 도시 이름이 비었습니다/);
});

test('바뀐 점 요약', () => {
  const c = clone();
  c.culture_sections.find((s) => s.id === 'movie').name = '시네마';
  c.travel_sections.push({ id: 'food', name: '미식', desc: '', visible: true });
  c.regions.reverse();
  c.regions.find((r) => r.id === 'guam').keywords.push('타무닝');
  c.home.hero_count = 6;
  c.channels.ent.desc = '';
  c.reporters[0].beats = ['guam'];
  const d = diffSite(SITE, c);
  const all = d.join('\n');
  assert.match(all, /문화 부문 이름: '영화' → '시네마'/);
  assert.match(all, /여행 부문 추가: 미식 \(food\)/);
  assert.match(all, /지역 순서:/);
  assert.match(all, /지역 괌: 낱말 추가 '타무닝'/);
  assert.match(all, /홈 넘기는 큰 기사 수: 4 → 6/);
  assert.match(all, /문화 채널 소개 글 비움/);
  assert.match(all, /기자 김태성 담당: 괌, 사이판 → 괌/);
  assert.deepEqual(diffSite(SITE, clone()), []);
});
