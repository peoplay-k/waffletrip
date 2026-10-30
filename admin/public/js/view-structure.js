// 구조 편집: 여행 부문 · 문화 부문 · 문화 분류 규칙 · 지역 · 기자 · 홈 배치.
// 화면에서 고친 것은 모아 두었다가 '저장' 한 번에 바뀐 점 요약을 보여 주고 커밋한다.
// 검사 규칙은 서버와 같은 파일(shared/siteconfig.js)을 쓴다.

import { h, clear, api, store, toast, banner, modal, confirmBox, statusBadge, debounce } from './core.js';
import {
  validateSite, diffSite, ID_RE, PROTECTED_TRAVEL, PROTECTED_CULTURE, HOME_BLOCKS, HOME_BLOCK_LABELS,
  HOME_NUMBERS, HOME_BOOLS, EXTRA_BEATS, CURRENCIES,
} from '../shared/siteconfig.js';

const TABS = [
  ['travel', '여행 부문', ['channels.travel', 'travel_sections']],
  ['culture', '문화 부문', ['channels.ent', 'culture_sections']],
  ['rules', '문화 분류 규칙', ['culture_rules', 'culture_aliases']],
  ['regions', '지역', ['regions', 'korea_travel_words']],
  ['reporters', '기자', ['reporters', 'general_reporter']],
  ['home', '홈 배치', ['home']],
];

const tabOfPath = (path) => {
  for (const [id, , prefixes] of TABS) if (prefixes.some((p) => path === p || path.startsWith(p + '.'))) return id;
  if (path === 'channels') return 'travel';
  return null;
};
const showWord = (w) => String(w).replace(/^ +| +$/g, (m) => '␣'.repeat(m.length));

export async function renderStructure(ctx, tabParam) {
  const { main } = ctx;
  main.append(h('div', { class: 'loading' }, h('span', { class: 'spinner' }), ' 구조를 불러오는 중…'));

  let orig;
  let sha;
  let articles = null;
  try {
    const [site, list] = await Promise.all([api('GET', '/api/site'), store.loadArticles(true).catch(() => null)]);
    orig = site.config;
    sha = site.sha;
    articles = list;
  } catch (e) {
    clear(main).append(banner('bad', `구조를 읽지 못했습니다: ${e.message}`));
    return {};
  }
  let work = structuredClone(orig);
  let deleted = { travel_sections: [], culture_sections: [] };
  let fresh = new WeakSet(); // 이번에 새로 만든 항목(id 를 아직 고칠 수 있다)
  const opened = new WeakSet(); // 펼쳐 둔 지역
  let tab = TABS.some(([id]) => id === tabParam) ? tabParam : 'travel';
  let errors = [];

  const dirtyEl = h('span', { class: 'dirty', hidden: true }, '● 저장 안 됨');
  const saveBtn = h('button', { type: 'button', class: 'primary', id: 'structure-save', on: { click: () => save() } }, '저장');
  const resetBtn = h('button', {
    type: 'button', id: 'structure-reset',
    on: {
      click: async () => {
        if (!isDirty() || await confirmBox('되돌리기', '저장하지 않은 고친 내용을 모두 버리고 저장된 구조로 되돌립니다.', { ok: '되돌리기', kind: 'danger' })) {
          work = structuredClone(orig);
          deleted = { travel_sections: [], culture_sections: [] };
          fresh = new WeakSet();
          changed();
          drawPanel();
        }
      },
    },
  }, '되돌리기');
  const errBox = h('div', { id: 'structure-errors' });
  const msg = h('div', { id: 'structure-msg' });
  const tabBar = h('div', { class: 'subtabs', role: 'tablist' });
  const panel = h('div', { id: 'structure-panel' });

  clear(main).append(
    h('div', { class: 'page-head' }, h('div', {},
      h('h1', {}, '사이트 구조'),
      h('p', {}, '메뉴·지역·기자·홈 배치를 고칩니다. 여러 곳을 고친 뒤 \'저장\'을 한 번 누르면 바뀐 점을 보여 주고 저장소에 올립니다. 지면 반영은 다음 발행 때입니다.'))),
    h('div', { class: 'savebar' }, saveBtn, resetBtn, dirtyEl),
    msg, errBox, tabBar, panel);

  const isDirty = () => JSON.stringify(work) !== JSON.stringify(orig) || deleted.travel_sections.length > 0 || deleted.culture_sections.length > 0;

  function tabDirty(id) {
    const pick = (c) => {
      switch (id) {
        case 'travel': return [c.channels?.travel, c.travel_sections];
        case 'culture': return [c.channels?.ent, c.culture_sections];
        case 'rules': return [c.culture_rules, c.culture_aliases];
        case 'regions': return [c.regions, c.korea_travel_words];
        case 'reporters': return [c.reporters, c.general_reporter];
        default: return [c.home];
      }
    };
    return JSON.stringify(pick(work)) !== JSON.stringify(pick(orig));
  }

  function drawTabs() {
    clear(tabBar);
    const errTabs = new Set(errors.map((e) => tabOfPath(e.path)));
    for (const [id, label] of TABS) {
      tabBar.append(h('button', {
        type: 'button', role: 'tab', class: tab === id ? 'on' : '', 'aria-selected': String(tab === id), dataset: { tab: id },
        on: { click: () => switchTab(id) },
      }, label,
      errTabs.has(id) ? h('span', { class: 'dot errdot', title: '고칠 곳이 있습니다' }) : tabDirty(id) ? h('span', { class: 'dot', title: '고쳤습니다' }) : null));
    }
  }

  function switchTab(id) {
    tab = id;
    history.replaceState(null, '', `#/structure/${id}`);
    drawTabs();
    drawPanel();
  }

  function drawErrors() {
    clear(errBox);
    if (!errors.length) return;
    errBox.append(banner('bad', h('div', {}, `고칠 곳이 ${errors.length}군데 있습니다. 고치기 전에는 저장할 수 없습니다.`,
      h('ul', { class: 'err-list' }, errors.slice(0, 12).map((e) => {
        const t = tabOfPath(e.path);
        return h('li', {}, t && t !== tab
          ? h('a', { on: { click: () => switchTab(t) } }, `[${TABS.find((x) => x[0] === t)[1]}] ${e.msg}`)
          : e.msg);
      }), errors.length > 12 ? h('li', {}, `… 외 ${errors.length - 12}건`) : null))));
  }

  const revalidate = debounce(() => {
    errors = validateSite(work, orig, { deleted, articles });
    drawErrors();
    drawTabs();
  }, 200);

  function changed() {
    dirtyEl.hidden = !isDirty();
    revalidate();
  }

  // ── 작은 부품 ──

  function textInput(obj, key, attrs = {}, { optional = false, transform } = {}) {
    const had = key in obj;
    const el = h('input', { type: 'text', value: obj[key] ?? '', ...attrs });
    el.addEventListener('input', () => {
      const v = transform ? transform(el.value) : el.value;
      if (optional && v === '' && !had) delete obj[key];
      else obj[key] = v;
      changed();
    });
    return el;
  }

  // 통화는 환율을 낼 수 있는 것만 고른다(모르는 통화는 수집이 죽는다). 원화권은 '없음'.
  function currencySelect(r) {
    const el = h('select', { 'aria-label': '통화', class: 'mono' });
    el.append(h('option', { value: '' }, '없음(원화권)'));
    for (const c of CURRENCIES) el.append(h('option', { value: c }, c));
    el.value = CURRENCIES.includes(r.currency) ? r.currency : '';
    el.addEventListener('change', () => {
      if (el.value === '') delete r.currency;
      else r.currency = el.value;
      changed();
    });
    return el;
  }

  function textArea(obj, key, attrs = {}) {
    const had = key in obj;
    const el = h('textarea', { rows: '2', ...attrs });
    el.value = obj[key] ?? '';
    el.addEventListener('input', () => {
      if (el.value === '' && !had) delete obj[key];
      else obj[key] = el.value;
      changed();
    });
    return el;
  }

  function toggle(obj, key, label, { onFlip, def = false, removeWhenDefault = false } = {}) {
    const had = key in obj;
    const input = h('input', { type: 'checkbox', checked: key in obj ? !!obj[key] : def });
    input.addEventListener('change', () => {
      // 원래 없던 칸은 기본값으로 돌아오면 다시 없앤다(파일을 쓸데없이 바꾸지 않게)
      if (removeWhenDefault && !had && input.checked === def) delete obj[key];
      else obj[key] = input.checked;
      changed();
      if (onFlip) onFlip();
    });
    return h('label', { class: 'switch' }, input, label);
  }

  function moves(arr, i, key) {
    const mv = (d) => (e) => {
      e.preventDefault();
      e.stopPropagation();
      const j = i + d;
      if (j < 0 || j >= arr.length) return;
      [arr[i], arr[j]] = [arr[j], arr[i]];
      changed();
      drawPanel();
      const again = panel.querySelector(`[data-move="${key}:${j}:${d}"]`) || panel.querySelector(`[data-move="${key}:${j}:${-d}"]`);
      if (again) again.focus();
    };
    return h('span', { class: 'moves' },
      h('button', { type: 'button', class: 'icon', title: '위로', 'aria-label': '위로', disabled: i === 0, dataset: { move: `${key}:${i}:-1` }, on: { click: mv(-1) } }, '↑'),
      h('button', { type: 'button', class: 'icon', title: '아래로', 'aria-label': '아래로', disabled: i === arr.length - 1, dataset: { move: `${key}:${i}:1` }, on: { click: mv(1) } }, '↓'));
  }

  /** 낱말 칩. Enter 나 쉼표로 넣고 × 로 뺀다. 붙여 넣은 '가,나,다' 는 나눠 넣는다. */
  function chips(arr, { placeholder = '낱말을 넣고 Enter', id } = {}) {
    const box = h('div', { class: 'chips' });
    const input = h('input', { type: 'text', placeholder, 'aria-label': placeholder, id });
    const draw = () => {
      for (const c of [...box.querySelectorAll('.chip')]) c.remove();
      arr.forEach((w, i) => {
        box.insertBefore(h('span', { class: 'chip', title: w !== w.trim() ? '앞뒤 빈칸(␣)도 낱말의 일부입니다' : null },
          showWord(w),
          h('button', {
            type: 'button', 'aria-label': `${w} 빼기`, title: '빼기',
            on: {
              click: () => {
                arr.splice(i, 1);
                changed();
                draw();
                input.focus();
              },
            },
          }, '×')), input);
      });
    };
    const add = (raw) => {
      let added = 0;
      for (const piece of raw.split(/[,\n]/)) {
        // 앞쪽 빈칸만 지운다 — '섬 ' 처럼 뒤 빈칸이 뜻을 가진 낱말이 있다
        const w = piece.replace(/^\s+/, '');
        if (!w.trim()) continue;
        if (arr.some((x) => x.toLowerCase() === w.toLowerCase())) {
          toast(`'${w}' 은 이미 있습니다`);
          continue;
        }
        arr.push(w);
        added++;
      }
      if (added) {
        changed();
        draw();
      }
    };
    input.addEventListener('keydown', (e) => {
      if ((e.key === 'Enter' || e.key === ',') && !e.isComposing) {
        e.preventDefault();
        add(input.value);
        input.value = '';
      }
    });
    input.addEventListener('paste', (e) => {
      const t = e.clipboardData && e.clipboardData.getData('text');
      if (t && /[,\n]/.test(t)) {
        e.preventDefault();
        add(t);
      }
    });
    input.addEventListener('blur', () => {
      if (input.value.trim()) {
        add(input.value);
        input.value = '';
      }
    });
    box.append(input);
    draw();
    return box;
  }

  function idField(obj, list, label) {
    if (!fresh.has(obj)) return h('span', { class: 'idtag', title: '한 번 만든 id 는 바꿀 수 없습니다(주소가 깨집니다)' }, obj.id);
    const err = h('span', { class: 'err small' });
    const input = h('input', { type: 'text', value: obj.id, placeholder: '영문 id (예: food)', 'aria-label': `${label} id`, class: 'mono new-id', size: '14' });
    const check = () => {
      const dup = list.filter((x) => x.id === obj.id).length > 1;
      err.textContent = !ID_RE.test(obj.id) ? '영문 소문자·숫자·하이픈 2~24자' : dup ? '이미 있는 id' : '';
      input.classList.toggle('invalid', !!err.textContent);
    };
    input.addEventListener('input', () => {
      obj.id = input.value.trim().toLowerCase();
      check();
      changed();
    });
    check();
    return h('span', { class: 'row' }, input, err);
  }

  // ── 부문(여행·문화) ──

  function channelCard(key, label) {
    const ch = work.channels[key];
    return h('div', { class: 'card' },
      h('h2', {}, `${label} 채널`),
      h('div', { class: 'grid2' },
        h('div', { class: 'field' }, h('label', { for: `ch-${key}-name` }, '채널 이름'), textInput(ch, 'name', { id: `ch-${key}-name`, maxlength: '20' }),
          h('div', { class: 'hint' }, `주소(/${key}/)는 바뀌지 않습니다.`)),
        h('div', { class: 'field' }, h('label', { for: `ch-${key}-desc` }, '채널 소개 글'), textArea(ch, 'desc', { id: `ch-${key}-desc`, rows: '3', maxlength: '1000' }),
          h('div', { class: 'hint' }, '채널 첫 화면 위에 나옵니다. 비우면 지역·부문 목록으로 자동으로 만듭니다.'))));
  }

  function sectionPanel(key, label, protectedIds, fallback) {
    const list = work[key];
    const wrap = h('div');
    list.forEach((s, i) => {
      const isProtected = protectedIds.includes(s.id) && !fresh.has(s);
      wrap.append(h('div', { class: `item${s.visible === false ? ' off' : ''}${fresh.has(s) ? ' new' : ''}`, dataset: { id: s.id || '' } },
        h('div', { class: 'item-head' },
          moves(list, i, key),
          idField(s, list, label),
          h('div', { class: 'spacer' }),
          toggle(s, 'visible', '메뉴에 보이기', { onFlip: drawPanel }),
          h('button', {
            type: 'button', class: 'small danger', disabled: isProtected,
            title: isProtected ? '기본 부문이라 지울 수 없습니다 — 숨기기를 쓰세요' : '지우기',
            on: { click: () => removeSection(key, s, label, fallback) },
          }, '지우기')),
        h('div', { class: 'item-body grid2' },
          h('div', { class: 'field' }, h('label', {}, '이름'), textInput(s, 'name', { maxlength: '20', 'aria-label': `${label} 이름`, class: 'sec-name' })),
          h('div', { class: 'field' }, h('label', {}, '설명'), textArea(s, 'desc', { 'aria-label': `${label} 설명` })))));
    });
    wrap.append(h('button', {
      type: 'button', id: `add-${key}`,
      on: {
        click: () => {
          const s = { id: '', name: '', desc: '', visible: true };
          fresh.add(s);
          list.push(s);
          changed();
          drawPanel();
          const ids = panel.querySelectorAll('.new-id');
          if (ids.length) ids[ids.length - 1].focus();
        },
      },
    }, `+ ${label} 추가`));
    return wrap;
  }

  async function removeSection(key, s, label, fallback) {
    const isNew = fresh.has(s);
    const rules = key === 'culture_sections' ? work.culture_rules.filter((r) => r.section === s.id).length : 0;
    if (!isNew) {
      const text = h('div', {},
        h('p', {}, `${label} '${s.name}' (${s.id}) 을 지웁니다. 그 부문의 기사는 기본 부문(${fallback})으로 갑니다.`),
        rules ? h('p', {}, `이 부문을 가리키는 문화 분류 규칙 ${rules}줄도 함께 지웁니다.`) : null,
        h('p', { class: 'muted small' }, '메뉴에서만 빼려면 지우지 말고 \'메뉴에 보이기\'를 끄세요. 저장하기 전까지는 되돌릴 수 있습니다.'));
      if (!(await confirmBox(`${label} 지우기`, text, { ok: '지우기', kind: 'danger' }))) return;
    }
    const list = work[key];
    list.splice(list.indexOf(s), 1);
    if (!isNew && orig[key].some((x) => x.id === s.id)) deleted[key].push(s.id);
    if (key === 'culture_sections') {
      work.culture_rules = work.culture_rules.filter((r) => r.section !== s.id);
      // 옛 부문 이름표가 지운 부문을 가리키면 기본 부문으로 돌린다
      for (const [from, to] of Object.entries(work.culture_aliases || {})) if (to === s.id) work.culture_aliases[from] = 'startrip';
    }
    changed();
    drawPanel();
  }

  // ── 문화 분류 규칙 ──

  function rulesPanel() {
    const list = work.culture_rules;
    const sections = work.culture_sections;
    const wrap = h('div', {},
      banner('info', work.culture_rules_note || '문화 기사에 부문이 비어 오면 제목으로 정한다. 위에서부터 먼저 걸리는 줄의 부문이 된다.'));
    list.forEach((r, i) => {
      const sel = h('select', { 'aria-label': `규칙 ${i + 1} 부문` }, sections.map((s) => h('option', { value: s.id }, s.name)));
      if (!sections.some((s) => s.id === r.section)) sel.append(h('option', { value: r.section }, `(없는 부문) ${r.section}`));
      sel.value = r.section;
      sel.addEventListener('change', () => {
        r.section = sel.value;
        changed();
      });
      wrap.append(h('div', { class: 'item rule' },
        h('div', { class: 'item-head' },
          moves(list, i, 'rules'),
          h('strong', {}, `${i + 1}번째`),
          h('span', { class: 'muted small' }, '이 낱말이 제목에 있으면 →'),
          h('span', {}, sel),
          h('div', { class: 'spacer' }),
          h('button', {
            type: 'button', class: 'small danger',
            on: {
              click: async () => {
                if (r.keywords.length && !(await confirmBox('규칙 지우기', `${i + 1}번째 규칙(낱말 ${r.keywords.length}개)을 지웁니다.`, { ok: '지우기', kind: 'danger' }))) return;
                list.splice(i, 1);
                changed();
                drawPanel();
              },
            },
          }, '지우기')),
        h('div', { class: 'item-body' }, chips(r.keywords, { id: `rule-${i}-input` }))));
    });
    wrap.append(h('button', {
      type: 'button', id: 'add-rule',
      on: {
        click: () => {
          list.push({ section: sections[0] ? sections[0].id : '', keywords: [] });
          changed();
          drawPanel();
          const inputs = panel.querySelectorAll('.rule .chips input');
          if (inputs.length) inputs[inputs.length - 1].focus();
        },
      },
    }, '+ 규칙 추가'));
    return wrap;
  }

  // ── 지역 ──

  function numberInput(obj, key, attrs) {
    const el = h('input', { type: 'number', value: obj[key] ?? '', step: 'any', ...attrs });
    el.addEventListener('input', () => {
      const v = el.value.trim();
      obj[key] = v === '' || !Number.isFinite(Number(v)) ? v : Number(v);
      changed();
    });
    return el;
  }

  function regionsPanel() {
    const list = work.regions;
    const wrap = h('div', {},
      banner('info', '지역은 지울 수 없습니다 — 그 지역의 기사와 주소가 함께 사라집니다. 안 쓰는 지역은 \'보이기\'를 끄세요. 순서는 지역 목록의 순서입니다.'));
    list.forEach((r, i) => {
      const weatherOn = h('input', { type: 'checkbox', checked: !!r.weather });
      const weatherFields = h('div', { class: 'grid3', hidden: !r.weather });
      const drawWeather = () => {
        clear(weatherFields);
        if (!r.weather) return;
        weatherFields.append(
          h('div', { class: 'field' }, h('label', {}, '날씨 도시'), textInput(r.weather, 'city', { 'aria-label': '날씨 도시' })),
          h('div', { class: 'field' }, h('label', {}, '위도'), numberInput(r.weather, 'lat', { min: '-90', max: '90', 'aria-label': '위도' })),
          h('div', { class: 'field' }, h('label', {}, '경도'), numberInput(r.weather, 'lon', { min: '-180', max: '180', 'aria-label': '경도' })));
      };
      weatherOn.addEventListener('change', () => {
        if (weatherOn.checked) r.weather = (orig.regions.find((x) => x.id === r.id) || {}).weather ? structuredClone(orig.regions.find((x) => x.id === r.id).weather) : { city: r.name || '', lat: 0, lon: 0 };
        else delete r.weather;
        weatherFields.hidden = !weatherOn.checked;
        drawWeather();
        changed();
      });
      drawWeather();
      const det = h('details', { class: `item region${r.visible === false ? ' off' : ''}${fresh.has(r) ? ' new' : ''}`, open: opened.has(r) || fresh.has(r), dataset: { id: r.id || '' } },
        h('summary', { class: 'item-head' },
          h('span', { class: 'chev', 'aria-hidden': 'true' }, '▸'),
          h('span', { class: 'name' }, r.name || '(이름 없음)'),
          fresh.has(r) ? null : h('span', { class: 'idtag' }, r.id),
          r.visible === false ? h('span', { class: 'badge s-hidden' }, '숨김') : null,
          h('span', { class: 'muted small' }, `낱말 ${(r.keywords || []).length}개`),
          h('div', { class: 'spacer' }),
          moves(list, i, 'regions')),
        h('div', { class: 'item-body' },
          fresh.has(r) ? h('div', { class: 'field' }, h('label', {}, 'id (주소: /travel/<id>/ — 나중에 못 바꿉니다)'), idField(r, list, '지역')) : null,
          h('div', { class: 'grid2' },
            h('div', { class: 'field' }, h('label', {}, '이름'), textInput(r, 'name', { maxlength: '20', 'aria-label': '지역 이름', class: 'region-name' })),
            h('div', { class: 'field' }, h('label', {}, ' '), toggle(r, 'visible', '지역 목록에 보이기', { onFlip: drawPanel }))),
          h('div', { class: 'field' }, h('label', {}, '담당 설명'), textInput(r, 'desk_duty', { 'aria-label': '담당 설명' }),
            h('div', { class: 'hint' }, '매체 소개의 편집국 표에 나옵니다.')),
          h('div', { class: 'field' }, h('label', {}, '고르는 낱말'), chips(r.keywords || (r.keywords = []), { id: `region-${r.id || i}-kw` }),
            h('div', { class: 'hint' }, '수집한 기사 제목에 이 낱말이 있으면 이 지역 기사로 잡습니다. 영어는 소문자로 넣습니다.')),
          h('div', { class: 'grid3' },
            h('div', { class: 'field' }, h('label', {}, '통화'), currencySelect(r),
              h('div', { class: 'hint' }, '환율 띠에 씁니다. 원화권이면 "없음".')),
            h('div', { class: 'field' }, h('label', {}, ' '), toggle(r, 'require_travel_word', '국내 — 제목에 여행 낱말이 있어야 잡힘', { removeWhenDefault: true })),
            h('div', { class: 'field' }, h('label', {}, ' '), toggle(r, 'destination', '여행지(끄면 업계 소식처럼 목적지가 아닌 지면)', { def: true, removeWhenDefault: true }))),
          h('div', { class: 'field' }, h('label', { class: 'check' }, weatherOn, '날씨 띠에 이 지역 날씨 넣기'), weatherFields)));
      det.addEventListener('toggle', () => {
        if (det.open) opened.add(r);
        else opened.delete(r);
      });
      wrap.append(det);
    });
    wrap.append(h('button', {
      type: 'button', id: 'add-region',
      on: {
        click: () => {
          const r = { id: '', name: '', keywords: [], desk_duty: '', visible: true };
          fresh.add(r);
          list.push(r);
          changed();
          drawPanel();
          const ids = panel.querySelectorAll('.new-id');
          if (ids.length) ids[ids.length - 1].focus();
        },
      },
    }, '+ 지역 추가'));
    wrap.append(h('div', { class: 'card', id: 'korea-words' },
      h('h2', {}, '국내 여행 낱말'),
      h('p', { class: 'muted small' }, '\'국내 — 여행 낱말이 있어야 잡힘\'을 켠 지역은 제목에 이 낱말 중 하나가 있어야 그 지역 기사로 잡힙니다. ␣ 는 빈칸입니다.'),
      chips(work.korea_travel_words || (work.korea_travel_words = []), { id: 'korea-words-input' })));
    return wrap;
  }

  // ── 기자 ──

  function reportersPanel() {
    const list = work.reporters;
    const beatsAll = [...work.regions.map((r) => ({ id: r.id, label: r.name })), ...Object.entries(EXTRA_BEATS).map(([id, label]) => ({ id, label }))];
    const generalSel = h('select', { id: 'general-reporter' });
    const drawGeneral = () => {
      clear(generalSel).append(...list.map((p) => h('option', { value: p.name }, p.name || '(이름 없음)')));
      if (!list.some((p) => p.name === work.general_reporter)) generalSel.append(h('option', { value: work.general_reporter }, `(명부에 없음) ${work.general_reporter}`));
      generalSel.value = work.general_reporter;
    };
    generalSel.addEventListener('change', () => {
      work.general_reporter = generalSel.value;
      changed();
    });
    const wrap = h('div', {}, banner('warn', '기자 이름은 기사 서명에 그대로 나갑니다 — 실제 직원만 넣습니다. 담당은 그 지면 기사에 자동으로 붙는 이름입니다.'));
    list.forEach((p, i) => {
      const name = h('input', { type: 'text', value: p.name, maxlength: '20', 'aria-label': '기자 이름', class: 'reporter-name' });
      name.addEventListener('input', () => {
        const old = p.name;
        p.name = name.value.trim();
        if (work.general_reporter === old) work.general_reporter = p.name;
        drawGeneral();
        changed();
      });
      const beats = h('div', { class: 'beats' }, beatsAll.map((b) => {
        const c = h('input', { type: 'checkbox', checked: (p.beats || []).includes(b.id), value: b.id });
        c.addEventListener('change', () => {
          const set = new Set(p.beats || []);
          if (c.checked) set.add(b.id);
          else set.delete(b.id);
          // 순서는 지역 목록 순서를 따른다(사람이 읽기 좋게)
          p.beats = beatsAll.map((x) => x.id).filter((x) => set.has(x));
          changed();
        });
        return h('label', { class: 'check' }, c, b.label);
      }));
      wrap.append(h('div', { class: 'item reporter' },
        h('div', { class: 'item-head' },
          moves(list, i, 'reporters'),
          h('span', {}, name),
          h('div', { class: 'spacer' }),
          h('button', {
            type: 'button', class: 'small danger',
            on: {
              click: async () => {
                if (!(await confirmBox('기자 지우기', `${p.name || '(이름 없음)'} 기자를 명부에서 뺍니다. 이 사람이 담당한 지면은 기본 기자 이름이 붙습니다.`, { ok: '지우기', kind: 'danger' }))) return;
                list.splice(i, 1);
                changed();
                drawPanel();
              },
            },
          }, '지우기')),
        h('div', { class: 'item-body' }, h('div', { class: 'small muted' }, '담당'), beats)));
    });
    wrap.append(h('button', {
      type: 'button', id: 'add-reporter',
      on: {
        click: () => {
          list.push({ name: '', beats: [] });
          changed();
          drawPanel();
          const names = panel.querySelectorAll('.reporter-name');
          if (names.length) names[names.length - 1].focus();
        },
      },
    }, '+ 기자 추가'));
    drawGeneral();
    wrap.append(h('div', { class: 'card' },
      h('div', { class: 'field' }, h('label', { for: 'general-reporter' }, '기본 기자'), generalSel,
        h('div', { class: 'hint' }, '담당이 없는 지면 기사에 붙는 이름입니다.'))));
    return wrap;
  }

  // ── 홈 배치 ──

  function homePanel() {
    const hm = work.home;
    const nums = h('div', { class: 'grid3' }, Object.entries(HOME_NUMBERS).map(([k, spec]) => {
      const el = h('input', { type: 'number', id: `home-${k}`, min: String(spec.min), max: String(spec.max), step: '1', value: hm[k] ?? '' });
      el.addEventListener('input', () => {
        const v = el.value.trim();
        hm[k] = /^-?\d+$/.test(v) ? Number(v) : v;
        changed();
      });
      return h('div', { class: 'field' }, h('label', { for: `home-${k}` }, spec.label), el, h('div', { class: 'hint' }, `${spec.min}~${spec.max}`));
    }));
    const bools = h('div', { class: 'row' }, Object.entries(HOME_BOOLS).map(([k, label]) => toggle(hm, k, label)));

    const order = h('ol', { class: 'order-list', id: 'home-order' });
    const drawOrder = () => {
      clear(order);
      const on = hm.order || (hm.order = []);
      const all = [...on, ...HOME_BLOCKS.filter((b) => !on.includes(b))];
      all.forEach((b) => {
        const i = on.indexOf(b);
        const inc = h('input', { type: 'checkbox', checked: i >= 0, 'aria-label': `${HOME_BLOCK_LABELS[b] || b} 넣기` });
        inc.addEventListener('change', () => {
          if (inc.checked) on.push(b);
          else on.splice(on.indexOf(b), 1);
          changed();
          drawOrder();
        });
        const mv = (d) => () => {
          const j = i + d;
          [on[i], on[j]] = [on[j], on[i]];
          changed();
          drawOrder();
        };
        order.append(h('li', { class: i < 0 ? 'off' : '', dataset: { block: b } },
          inc,
          h('span', { class: 'spacer' }, HOME_BLOCK_LABELS[b] || b),
          i >= 0 ? h('span', { class: 'moves' },
            h('button', { type: 'button', class: 'icon', 'aria-label': '위로', disabled: i === 0, on: { click: mv(-1) } }, '↑'),
            h('button', { type: 'button', class: 'icon', 'aria-label': '아래로', disabled: i === on.length - 1, on: { click: mv(1) } }, '↓')) : h('span', { class: 'muted small' }, '홈에 안 나옴')));
      });
    };
    drawOrder();

    // 고정 머리기사 고르기
    const pinBox = h('div', { id: 'pin-box' });
    const drawPin = () => {
      clear(pinBox);
      const cur = hm.pinned_lead || '';
      const hit = cur && articles ? articles.find((a) => a.published_id === cur) : null;
      pinBox.append(h('div', { class: 'row' },
        h('span', {}, '지금: '),
        cur ? h('strong', { id: 'pin-current' }, hit ? hit.title : cur) : h('strong', { id: 'pin-current' }, '자동 (가장 좋은 최신 기사)'),
        hit ? statusBadge(hit.status) : null,
        cur ? h('button', { type: 'button', class: 'small', id: 'pin-clear', on: { click: () => { hm.pinned_lead = ''; changed(); drawPin(); } } }, '자동으로') : null));
      if (!articles) {
        pinBox.append(h('p', { class: 'muted small' }, '기사 목록을 못 읽어 고르기 창을 띄우지 못했습니다. 발행 id 를 직접 넣으세요.'),
          textInput(hm, 'pinned_lead', { placeholder: '발행 id', 'aria-label': '고정 머리기사 발행 id' }));
        return;
      }
      const q = h('input', { type: 'search', id: 'pin-search', placeholder: '발행된 기사 제목으로 찾기', 'aria-label': '고정할 기사 찾기' });
      const results = h('div', { class: 'picker-results', hidden: true });
      q.addEventListener('input', debounce(() => {
        const words = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
        clear(results);
        if (!words.length) {
          results.hidden = true;
          return;
        }
        const found = articles.filter((a) => a.status === 'published' && a.published_id && words.every((w) => (a.title || '').toLowerCase().includes(w))).slice(0, 30);
        results.hidden = false;
        if (!found.length) results.append(h('div', { class: 'empty small' }, '찾는 기사가 없습니다(발행된 기사만 고를 수 있습니다).'));
        for (const a of found) {
          results.append(h('button', {
            type: 'button', dataset: { pid: a.published_id },
            on: { click: () => { hm.pinned_lead = a.published_id; changed(); drawPin(); } },
          }, a.title, h('span', { class: 'muted small' }, ` · ${a.published_on || ''}`)));
        }
      }, 150));
      pinBox.append(q, results);
    };
    drawPin();

    return h('div', {},
      h('div', { class: 'card' }, h('h2', {}, '기사 수'), nums),
      h('div', { class: 'card' }, h('h2', {}, '보이기'), bools),
      h('div', { class: 'card' }, h('h2', {}, '묶음 순서'), h('p', { class: 'muted small' }, '홈에서 위에서부터 이 순서로 나옵니다. 빼면 홈에 나오지 않습니다.'), order),
      h('div', { class: 'card' }, h('h2', {}, '고정 머리기사'), h('p', { class: 'muted small' }, '고르면 그 기사를 홈 맨 위 큰 기사로 고정합니다. 비우면 자동입니다.'), pinBox));
  }

  function drawPanel() {
    clear(panel);
    if (tab === 'travel') panel.append(channelCard('travel', '여행'), h('h2', {}, '여행 부문'), h('p', { class: 'muted small' }, '순서가 곧 메뉴 순서입니다. 기본 넷(뉴스·업계·기획·통계)은 자동 분류 규칙이 있어 지울 수 없고, 새로 만든 부문에는 기사에서 직접 고른 것만 들어갑니다.'), sectionPanel('travel_sections', '여행 부문', PROTECTED_TRAVEL, '뉴스'));
    else if (tab === 'culture') panel.append(channelCard('ent', '문화'), h('h2', {}, '문화 부문'), h('p', { class: 'muted small' }, '순서가 곧 메뉴 순서입니다. 주소는 /ent/<id>/ 입니다.'), sectionPanel('culture_sections', '문화 부문', PROTECTED_CULTURE, '스타의 여행'));
    else if (tab === 'rules') panel.append(rulesPanel());
    else if (tab === 'regions') panel.append(regionsPanel());
    else if (tab === 'reporters') panel.append(reportersPanel());
    else panel.append(homePanel());
  }

  // ── 저장 ──

  async function save() {
    errors = validateSite(work, orig, { deleted, articles });
    drawErrors();
    drawTabs();
    if (errors.length) {
      await modal({
        title: '아직 저장할 수 없습니다',
        body: h('div', {}, h('p', {}, '아래를 고친 뒤 다시 저장하세요.'), h('ul', { class: 'changes', id: 'save-errors' }, errors.map((e) => h('li', {}, e.msg)))),
      });
      return;
    }
    const changes = diffSite(orig, work);
    if (!changes.length) {
      toast('바뀐 것이 없습니다');
      return;
    }
    const status = h('div');
    await modal({
      title: `이렇게 저장합니다 (${changes.length}건)`,
      body: h('div', {},
        h('ul', { class: 'changes', id: 'save-changes' }, changes.map((c) => h('li', {}, c))),
        h('p', { class: 'muted small' }, '저장하면 저장소(config/site.json)에 커밋됩니다. 지면 반영은 다음 발행 때입니다 — 바로 반영하려면 발행 상태에서 \'지금 발행\'을 누르세요.'),
        status),
      buttons: [{ label: '취소', value: false }, { label: '저장', kind: 'primary', value: true }],
      onButton: async (v, ctl) => {
        if (!v) return true;
        ctl.setBusy(true);
        clear(status).append(h('p', {}, h('span', { class: 'spinner' }), ' 저장 중…'));
        try {
          const r = await api('PUT', '/api/site', { config: work, sha, deleted });
          sha = r.sha;
          orig = structuredClone(work);
          deleted = { travel_sections: [], culture_sections: [] };
          fresh = new WeakSet();
          store.dropSite();
          changed();
          drawPanel();
          clear(msg).append(banner('ok', r.unchanged ? '바뀐 것이 없어 저장하지 않았습니다.' : `구조를 저장했습니다(${(r.changes || changes).length}건). 다음 발행 때 지면에 반영됩니다.`,
            h('a', { class: 'btn small', href: '#/deploys' }, '발행 상태 보기')));
          return true;
        } catch (e) {
          ctl.setBusy(false);
          clear(status);
          if (e.status === 409) {
            status.append(banner('warn', e.message, h('button', {
              type: 'button', class: 'small',
              on: {
                click: async () => {
                  ctl.close(false);
                  orig = work; // 버리기 확인을 다시 묻지 않게
                  clear(main);
                  Object.assign(self, await renderStructure(ctx, tab));
                },
              },
            }, '새로 불러오기(고친 것 버림)')));
          } else if (e.data && Array.isArray(e.data.errors)) {
            status.append(banner('bad', '서버가 저장을 막았습니다:', h('ul', {}, e.data.errors.map((x) => h('li', {}, x.msg || String(x))))));
          } else status.append(banner('bad', `저장하지 못했습니다: ${e.message}`));
          return false;
        }
      },
    });
  }

  drawTabs();
  drawPanel();
  changed();
  const self = { isDirty };
  return self;
}
