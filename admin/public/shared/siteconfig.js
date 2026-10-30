// 사이트 구조(config/site.json) 검사와 바뀐 점 요약.
// 화면(브라우저)과 서버(Worker)가 이 파일 하나를 같이 쓴다 — 화면에서 미리 보여 준
// 오류와 서버가 막는 오류가 어긋나지 않게. 서버는 화면을 믿지 않고 다시 검사한다.

export const ID_RE = /^[a-z0-9-]{2,24}$/;
// 자동 분류 규칙이 걸린 기본 여행 부문, 문화의 기본 부문. 지우면 기사가 갈 곳이 없다 — 숨기기만.
export const PROTECTED_TRAVEL = ['news', 'biz', 'feature', 'data'];
export const PROTECTED_CULTURE = ['startrip'];
export const HOME_BLOCKS = ['travel', 'culture', 'culture_sections', 'latest'];
export const HOME_BLOCK_LABELS = {
  travel: '여행 기사 묶음',
  culture: '문화 기사 묶음',
  culture_sections: '문화 부문별 묶음',
  latest: '최신 기사',
};
// 범위는 파이프라인(src/site_config.py HOME_RANGES)과 같아야 한다 — 여기서 통과한 값이
// 빌드에서 막히면 지면이 멈춘다. tests/test_site_config.py 가 두 검사기를 맞춰 본다.
export const HOME_NUMBERS = {
  hero_count: { label: '넘기는 큰 기사 수', min: 1, max: 8 },
  travel_block_size: { label: '여행 묶음 기사 수', min: 1, max: 30 },
  culture_grid: { label: '문화 격자 기사 수', min: 0, max: 24 },
  culture_block_size: { label: '문화 부문별 기사 수', min: 1, max: 20 },
  latest_count: { label: '최신 기사 수', min: 0, max: 30 },
  photo_row: { label: '사진 줄 사진 수', min: 0, max: 24 },
};
// 환율을 낼 수 있는 통화(src/site_config.py CURRENCIES 와 같다). 다른 통화는 수집이 죽는다.
export const CURRENCIES = ['USD', 'MYR', 'VND', 'LAK', 'JPY', 'THB', 'TWD'];
export const HOME_BOOLS = {
  show_data_strip: '환율·날씨 띠 보이기',
  show_photo_row: '사진 줄 보이기',
  show_video: '영상 보이기',
};
export const EXTRA_BEATS = { ent: '문화(연예)', data: '통계·리포트' };

const LIST_LABEL = {
  travel_sections: '여행 부문',
  culture_sections: '문화 부문',
  regions: '지역',
};

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isStr = (v) => typeof v === 'string';
const nonEmpty = (v) => isStr(v) && v.trim() !== '';
const ids = (list) => (Array.isArray(list) ? list.map((x) => x && x.id) : []);

/**
 * next 를 검사한다. current 는 지금 저장소의 파일(없으면 null).
 * opts.deleted = {travel_sections:[id], culture_sections:[id]} — 일부러 지운 부문.
 *   여기 없는데 사라진 id 는 '이름 바꾸려다 id 를 바꾼 것'으로 보고 막는다.
 * opts.articles = 기사 목록(고정 머리기사 확인용). 없으면 그 검사는 건너뛴다.
 * 돌려주는 값: [{path, msg}] — 비어 있으면 통과.
 */
export function validateSite(next, current, opts = {}) {
  const errs = [];
  const err = (path, msg) => errs.push({ path, msg });
  const deleted = opts.deleted || {};

  if (!isObj(next)) return [{ path: '', msg: '구조 파일이 객체가 아닙니다' }];

  // 채널
  if (!isObj(next.channels) || !isObj(next.channels.travel) || !isObj(next.channels.ent)) {
    err('channels', '채널(여행·문화) 칸이 없습니다');
  } else {
    const extra = Object.keys(next.channels).filter((k) => k !== 'travel' && k !== 'ent');
    if (extra.length) err('channels', `채널은 여행·문화 둘뿐입니다 (모르는 채널: ${extra.join(', ')})`);
    for (const [k, label] of [['travel', '여행'], ['ent', '문화']]) {
      if (!nonEmpty(next.channels[k].name)) err(`channels.${k}.name`, `${label} 채널 이름이 비었습니다`);
      else if (next.channels[k].name.length > 20) err(`channels.${k}.name`, `${label} 채널 이름이 너무 깁니다(20자까지)`);
      // desc: 채널 첫 화면 소개 글. 비우면 지역·부문 목록으로 자동으로 만든다.
      const d = next.channels[k].desc;
      if (d !== undefined && !isStr(d)) err(`channels.${k}.desc`, `${label} 채널 소개 글이 글자가 아닙니다`);
      else if (isStr(d) && d.length > 1000) err(`channels.${k}.desc`, `${label} 채널 소개 글이 너무 깁니다(1000자까지)`);
    }
  }

  // 부문(여행·문화)
  for (const key of ['travel_sections', 'culture_sections']) {
    const label = LIST_LABEL[key];
    const list = next[key];
    if (!Array.isArray(list) || !list.length) {
      err(key, `${label}이 하나도 없습니다`);
      continue;
    }
    checkSectionList(list, key, label, err);
    if (list.every((s) => isObj(s) && s.visible === false)) err(key, `${label}을 전부 숨길 수는 없습니다 — 하나는 보여야 합니다`);
    if (current && Array.isArray(current[key])) {
      const now = new Set(ids(list));
      const okDeleted = new Set(Array.isArray(deleted[key]) ? deleted[key] : []);
      const protectedIds = key === 'travel_sections' ? PROTECTED_TRAVEL : PROTECTED_CULTURE;
      for (const old of ids(current[key])) {
        if (!old || now.has(old)) continue;
        if (protectedIds.includes(old)) {
          err(key, `${label} '${old}' 은 기본 부문이라 지울 수 없습니다 — 숨기기를 쓰세요`);
        } else if (!okDeleted.has(old)) {
          err(key, `${label} id '${old}' 가 사라졌습니다. 한 번 만든 id 는 바꿀 수 없습니다(주소가 깨집니다) — 이름만 바꾸세요`);
        }
      }
    }
  }

  // 문화 분류 규칙
  const cultureIds = new Set(ids(next.culture_sections));
  if (!Array.isArray(next.culture_rules)) {
    err('culture_rules', '문화 분류 규칙 칸이 없습니다');
  } else {
    next.culture_rules.forEach((r, i) => {
      const at = `문화 분류 규칙 ${i + 1}번째`;
      if (!isObj(r)) return err(`culture_rules.${i}`, `${at}: 형식이 틀렸습니다`);
      if (!cultureIds.has(r.section)) err(`culture_rules.${i}.section`, `${at}: 부문 '${r.section || ''}' 이 문화 부문 목록에 없습니다`);
      checkWords(r.keywords, `culture_rules.${i}.keywords`, at, err, { allowEmpty: false });
    });
  }
  if (next.culture_aliases !== undefined) {
    if (!isObj(next.culture_aliases)) err('culture_aliases', '옛 부문 이름표(culture_aliases) 형식이 틀렸습니다');
    else {
      for (const [from, to] of Object.entries(next.culture_aliases)) {
        if (!cultureIds.has(to)) err('culture_aliases', `옛 부문 '${from}' 이 가리키는 '${to}' 가 문화 부문 목록에 없습니다`);
      }
    }
  }

  // 지역
  const regionIds = new Set();
  if (!Array.isArray(next.regions) || !next.regions.length) {
    err('regions', '지역이 하나도 없습니다');
  } else {
    next.regions.forEach((r, i) => {
      const at = `지역 ${i + 1}번째${r && r.name ? `(${r.name})` : ''}`;
      if (!isObj(r)) return err(`regions.${i}`, `${at}: 형식이 틀렸습니다`);
      if (!isStr(r.id) || !ID_RE.test(r.id)) err(`regions.${i}.id`, `${at}: id '${r.id || ''}' 는 영문 소문자·숫자·하이픈 2~24자여야 합니다`);
      else if (regionIds.has(r.id)) err(`regions.${i}.id`, `${at}: id '${r.id}' 가 겹칩니다`);
      else regionIds.add(r.id);
      if (!nonEmpty(r.name)) err(`regions.${i}.name`, `${at}: 이름이 비었습니다`);
      else if (r.name.length > 20) err(`regions.${i}.name`, `${at}: 이름이 너무 깁니다(20자까지)`);
      checkWords(r.keywords, `regions.${i}.keywords`, at, err, { allowEmpty: true });
      if (r.desk_duty !== undefined && !isStr(r.desk_duty)) err(`regions.${i}.desk_duty`, `${at}: 담당 설명이 글자가 아닙니다`);
      if (typeof r.visible !== 'boolean') err(`regions.${i}.visible`, `${at}: 보이기 값이 없습니다`);
      if (r.currency !== undefined && r.currency !== '' && !CURRENCIES.includes(r.currency)) {
        err(`regions.${i}.currency`, `${at}: 통화 '${r.currency}' 는 환율을 낼 수 없습니다 (가능: ${CURRENCIES.join(', ')})`);
      }
      if (r.weather !== undefined) {
        const w = r.weather;
        if (!isObj(w) || !nonEmpty(w.city)) err(`regions.${i}.weather`, `${at}: 날씨 도시 이름이 비었습니다`);
        else {
          if (!(typeof w.lat === 'number' && w.lat >= -90 && w.lat <= 90)) err(`regions.${i}.weather.lat`, `${at}: 날씨 위도는 -90~90 사이 숫자여야 합니다`);
          if (!(typeof w.lon === 'number' && w.lon >= -180 && w.lon <= 180)) err(`regions.${i}.weather.lon`, `${at}: 날씨 경도는 -180~180 사이 숫자여야 합니다`);
        }
      }
      for (const flag of ['require_travel_word', 'destination']) {
        if (r[flag] !== undefined && typeof r[flag] !== 'boolean') err(`regions.${i}.${flag}`, `${at}: ${flag} 값은 켬/끔이어야 합니다`);
      }
    });
    if (next.regions.every((r) => isObj(r) && r.visible === false)) err('regions', '지역을 전부 숨길 수는 없습니다 — 하나는 보여야 합니다');
    // 지역은 지우지 않는다 — 기사·주소가 함께 사라진다
    if (current && Array.isArray(current.regions)) {
      for (const old of ids(current.regions)) {
        if (old && !regionIds.has(old)) err('regions', `지역 '${old}' 은 지울 수 없습니다(그 지역 기사와 주소가 사라집니다) — 숨기기를 쓰세요. id 도 바꿀 수 없습니다`);
      }
    }
  }
  if (next.korea_travel_words !== undefined) checkWords(next.korea_travel_words, 'korea_travel_words', '국내 여행 낱말', err, { allowEmpty: true });

  // 기자
  const names = new Set();
  if (!Array.isArray(next.reporters) || !next.reporters.length) {
    err('reporters', '기자가 한 명도 없습니다');
  } else {
    next.reporters.forEach((p, i) => {
      const at = `기자 ${i + 1}번째${p && p.name ? `(${p.name})` : ''}`;
      if (!isObj(p)) return err(`reporters.${i}`, `${at}: 형식이 틀렸습니다`);
      if (!nonEmpty(p.name)) err(`reporters.${i}.name`, `${at}: 이름이 비었습니다`);
      else if (p.name !== p.name.trim()) err(`reporters.${i}.name`, `${at}: 이름 앞뒤에 빈칸이 있습니다`);
      else if (p.name.length > 20) err(`reporters.${i}.name`, `${at}: 이름이 너무 깁니다(20자까지)`);
      else if (names.has(p.name)) err(`reporters.${i}.name`, `${at}: 같은 이름의 기자가 이미 있습니다`);
      else names.add(p.name);
      if (!Array.isArray(p.beats)) err(`reporters.${i}.beats`, `${at}: 담당(beats) 목록이 없습니다`);
      else {
        const seen = new Set();
        for (const b of p.beats) {
          if (!(regionIds.has(b) || b in EXTRA_BEATS)) err(`reporters.${i}.beats`, `${at}: 담당 '${b}' 는 지역 id 나 ent·data 여야 합니다`);
          if (seen.has(b)) err(`reporters.${i}.beats`, `${at}: 담당 '${b}' 가 두 번 들어 있습니다`);
          seen.add(b);
        }
      }
    });
  }
  if (!nonEmpty(next.general_reporter) || !names.has(next.general_reporter)) {
    err('general_reporter', `기본 기자 '${next.general_reporter || ''}' 가 기자 명부에 없습니다`);
  }

  // 홈 배치
  const h = next.home;
  if (!isObj(h)) err('home', '홈 배치 칸이 없습니다');
  else {
    for (const [k, spec] of Object.entries(HOME_NUMBERS)) {
      const v = h[k];
      if (!Number.isInteger(v) || v < spec.min || v > spec.max) {
        err(`home.${k}`, `홈: ${spec.label}는 ${spec.min}~${spec.max} 사이 정수여야 합니다 (지금: ${v === undefined ? '없음' : v})`);
      }
    }
    for (const [k, label] of Object.entries(HOME_BOOLS)) {
      if (typeof h[k] !== 'boolean') err(`home.${k}`, `홈: '${label}' 값은 켬/끔이어야 합니다`);
    }
    if (!Array.isArray(h.order) || !h.order.length) err('home.order', '홈: 묶음 순서가 비었습니다');
    else {
      const seen = new Set();
      for (const b of h.order) {
        if (!HOME_BLOCKS.includes(b)) err('home.order', `홈: 모르는 묶음 '${b}' 이 순서에 있습니다`);
        else if (seen.has(b)) err('home.order', `홈: 묶음 '${HOME_BLOCK_LABELS[b]}' 이 두 번 들어 있습니다`);
        seen.add(b);
      }
    }
    if (h.pinned_lead !== undefined && !isStr(h.pinned_lead)) err('home.pinned_lead', '홈: 고정 머리기사 값이 글자가 아닙니다');
    else if (nonEmpty(h.pinned_lead) && Array.isArray(opts.articles)) {
      const hit = opts.articles.find((a) => a.published_id === h.pinned_lead);
      if (!hit) err('home.pinned_lead', `홈: 고정 머리기사 '${h.pinned_lead}' 를 발행된 기사에서 찾을 수 없습니다`);
      else if (hit.status !== 'published') err('home.pinned_lead', `홈: 고정 머리기사 '${hit.title}' 는 지금 발행 상태가 아닙니다(${hit.status})`);
    }
  }
  return errs;
}

function checkSectionList(list, key, label, err) {
  const seen = new Set();
  list.forEach((s, i) => {
    const at = `${label} ${i + 1}번째${s && s.name ? `(${s.name})` : ''}`;
    if (!isObj(s)) return err(`${key}.${i}`, `${at}: 형식이 틀렸습니다`);
    if (!isStr(s.id) || !ID_RE.test(s.id)) err(`${key}.${i}.id`, `${at}: id '${s.id || ''}' 는 영문 소문자·숫자·하이픈 2~24자여야 합니다`);
    else if (seen.has(s.id)) err(`${key}.${i}.id`, `${at}: id '${s.id}' 가 겹칩니다`);
    else seen.add(s.id);
    if (!nonEmpty(s.name)) err(`${key}.${i}.name`, `${at}: 이름이 비었습니다`);
    else if (s.name.length > 20) err(`${key}.${i}.name`, `${at}: 이름이 너무 깁니다(20자까지)`);
    if (s.desc !== undefined && !isStr(s.desc)) err(`${key}.${i}.desc`, `${at}: 설명이 글자가 아닙니다`);
    if (typeof s.visible !== 'boolean') err(`${key}.${i}.visible`, `${at}: 보이기 값이 없습니다`);
  });
}

function checkWords(words, path, at, err, { allowEmpty }) {
  if (!Array.isArray(words)) return err(path, `${at}: 낱말 목록이 없습니다`);
  if (!allowEmpty && !words.length) err(path, `${at}: 낱말이 하나도 없습니다`);
  const seen = new Set();
  for (const w of words) {
    if (!isStr(w) || !w.trim()) {
      err(path, `${at}: 빈 낱말이 있습니다`);
      continue;
    }
    if (w.length > 40) err(path, `${at}: 낱말 '${w.slice(0, 20)}…' 이 너무 깁니다(40자까지)`);
    const k = w.toLowerCase();
    if (seen.has(k)) err(path, `${at}: 낱말 '${w}' 이 두 번 들어 있습니다`);
    seen.add(k);
  }
}

// ── 바뀐 점 요약 ────────────────────────────────────────────────────────

const show = (w) => `'${String(w).replace(/^ | $/g, '␣')}'`;

function wordDiff(a = [], b = []) {
  const A = new Set(a);
  const B = new Set(b);
  const added = b.filter((w) => !A.has(w));
  const removed = a.filter((w) => !B.has(w));
  const parts = [];
  if (added.length) parts.push('낱말 추가 ' + added.map(show).join(', '));
  if (removed.length) parts.push('낱말 뺌 ' + removed.map(show).join(', '));
  if (!parts.length && JSON.stringify(a) !== JSON.stringify(b)) parts.push('낱말 순서 바뀜');
  return parts;
}

function orderChanged(before, after, key) {
  const common = new Set(before.map((x) => x[key]).filter((k) => after.some((y) => y[key] === k)));
  const a = before.map((x) => x[key]).filter((k) => common.has(k));
  const b = after.map((x) => x[key]).filter((k) => common.has(k));
  return a.join('\u0000') !== b.join('\u0000');
}

function diffSections(before = [], after = [], label, out) {
  const old = new Map(before.map((s) => [s.id, s]));
  const now = new Map(after.map((s) => [s.id, s]));
  for (const s of after) {
    const o = old.get(s.id);
    if (!o) {
      out.push(`${label} 추가: ${s.name} (${s.id})${s.visible === false ? ' — 숨김' : ''}`);
      continue;
    }
    if (o.name !== s.name) out.push(`${label} 이름: '${o.name}' → '${s.name}' (${s.id})`);
    if ((o.desc || '') !== (s.desc || '')) out.push(`${label} 설명 바뀜: ${s.name}`);
    if (o.visible !== s.visible) out.push(`${label} ${s.visible ? '보이기' : '숨기기'}: ${s.name}`);
  }
  for (const o of before) if (!now.has(o.id)) out.push(`${label} 삭제: ${o.name} (${o.id})`);
  if (orderChanged(before, after, 'id')) out.push(`${label} 순서: ${after.map((s) => s.name).join(' · ')}`);
}

/** 사람이 읽을 바뀐 점 목록(한국어 줄). */
export function diffSite(before, after) {
  const out = [];
  if (!before || !after) return out;
  for (const [k, label] of [['travel', '여행'], ['ent', '문화']]) {
    const a = before.channels?.[k]?.name;
    const b = after.channels?.[k]?.name;
    if (a !== b) out.push(`${label} 채널 이름: '${a}' → '${b}'`);
    if ((before.channels?.[k]?.desc || '') !== (after.channels?.[k]?.desc || '')) {
      out.push(`${label} 채널 소개 글 ${after.channels?.[k]?.desc ? '바뀜' : '비움(자동으로 만듦)'}`);
    }
  }
  diffSections(before.travel_sections, after.travel_sections, '여행 부문', out);
  diffSections(before.culture_sections, after.culture_sections, '문화 부문', out);

  const rb = before.culture_rules || [];
  const ra = after.culture_rules || [];
  const secName = (id) => (after.culture_sections || []).find((s) => s.id === id)?.name
    || (before.culture_sections || []).find((s) => s.id === id)?.name || id;
  for (let i = 0; i < Math.max(rb.length, ra.length); i++) {
    const a = rb[i];
    const b = ra[i];
    if (!a) out.push(`문화 분류 규칙 추가(${i + 1}번째): ${secName(b.section)} ← ${(b.keywords || []).map(show).join(', ')}`);
    else if (!b) out.push(`문화 분류 규칙 삭제(${i + 1}번째였던 ${secName(a.section)})`);
    else {
      if (a.section !== b.section) out.push(`문화 분류 규칙 ${i + 1}번째: 부문 ${secName(a.section)} → ${secName(b.section)}`);
      for (const p of wordDiff(a.keywords, b.keywords)) out.push(`문화 분류 규칙 ${i + 1}번째(${secName(b.section)}): ${p}`);
    }
  }

  const regOld = new Map((before.regions || []).map((r) => [r.id, r]));
  for (const r of after.regions || []) {
    const o = regOld.get(r.id);
    if (!o) {
      out.push(`지역 추가: ${r.name} (${r.id})`);
      continue;
    }
    if (o.name !== r.name) out.push(`지역 이름: '${o.name}' → '${r.name}' (${r.id})`);
    if (o.visible !== r.visible) out.push(`지역 ${r.visible ? '보이기' : '숨기기'}: ${r.name}`);
    if ((o.desk_duty || '') !== (r.desk_duty || '')) out.push(`지역 담당 설명 바뀜: ${r.name}`);
    for (const p of wordDiff(o.keywords, r.keywords)) out.push(`지역 ${r.name}: ${p}`);
    if ((o.currency || '') !== (r.currency || '')) out.push(`지역 ${r.name}: 통화 ${o.currency || '없음'} → ${r.currency || '없음'}`);
    if (JSON.stringify(o.weather || null) !== JSON.stringify(r.weather || null)) out.push(`지역 ${r.name}: 날씨 지점 바뀜`);
    if (!!o.require_travel_word !== !!r.require_travel_word) out.push(`지역 ${r.name}: 여행 낱말 필요 ${r.require_travel_word ? '켬' : '끔'}`);
    if ((o.destination !== false) !== (r.destination !== false)) out.push(`지역 ${r.name}: 여행지 ${r.destination === false ? '아님' : '맞음'}`);
  }
  for (const o of before.regions || []) if (!(after.regions || []).some((r) => r.id === o.id)) out.push(`지역 삭제: ${o.name} (${o.id})`);
  if (orderChanged(before.regions || [], after.regions || [], 'id')) out.push(`지역 순서: ${(after.regions || []).map((r) => r.name).join(' · ')}`);
  for (const p of wordDiff(before.korea_travel_words, after.korea_travel_words)) out.push(`국내 여행 낱말: ${p}`);

  const repOld = new Map((before.reporters || []).map((p) => [p.name, p]));
  const regionName = (id) => EXTRA_BEATS[id] || (after.regions || []).find((r) => r.id === id)?.name || id;
  for (const p of after.reporters || []) {
    const o = repOld.get(p.name);
    if (!o) {
      out.push(`기자 추가: ${p.name} (담당: ${(p.beats || []).map(regionName).join(', ') || '없음'})`);
      continue;
    }
    if (JSON.stringify(o.beats || []) !== JSON.stringify(p.beats || [])) {
      out.push(`기자 ${p.name} 담당: ${(o.beats || []).map(regionName).join(', ') || '없음'} → ${(p.beats || []).map(regionName).join(', ') || '없음'}`);
    }
  }
  for (const o of before.reporters || []) if (!(after.reporters || []).some((p) => p.name === o.name)) out.push(`기자 삭제: ${o.name}`);
  if (orderChanged(before.reporters || [], after.reporters || [], 'name')) out.push(`기자 순서: ${(after.reporters || []).map((p) => p.name).join(' · ')}`);
  if (before.general_reporter !== after.general_reporter) out.push(`기본 기자: ${before.general_reporter} → ${after.general_reporter}`);

  const hb = before.home || {};
  const ha = after.home || {};
  for (const [k, spec] of Object.entries(HOME_NUMBERS)) if (hb[k] !== ha[k]) out.push(`홈 ${spec.label}: ${hb[k]} → ${ha[k]}`);
  for (const [k, label] of Object.entries(HOME_BOOLS)) if (hb[k] !== ha[k]) out.push(`홈 ${label}: ${ha[k] ? '켬' : '끔'}`);
  if (JSON.stringify(hb.order) !== JSON.stringify(ha.order)) out.push(`홈 묶음 순서: ${(ha.order || []).map((b) => HOME_BLOCK_LABELS[b] || b).join(' → ')}`);
  if ((hb.pinned_lead || '') !== (ha.pinned_lead || '')) out.push(`홈 고정 머리기사: ${ha.pinned_lead ? ha.pinned_lead : '자동'}`);

  // 화면이 다루지 않는 칸이라도 바뀌었으면 알린다
  const known = new Set(['channels', 'travel_sections', 'culture_sections', 'culture_rules', 'regions', 'korea_travel_words', 'reporters', 'general_reporter', 'home']);
  for (const k of new Set([...Object.keys(before), ...Object.keys(after)])) {
    if (!known.has(k) && JSON.stringify(before[k]) !== JSON.stringify(after[k])) out.push(`기타 칸 '${k}' 바뀜`);
  }
  return out;
}
