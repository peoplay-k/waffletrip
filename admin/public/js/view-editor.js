// 기사 쓰기·고치기.
// 칸 이름표와 안내 글은 옛 편집실(static/admin/config.yml)의 것을 그대로 옮겼다 — 기자들이 익숙한 말.

import {
  h, clear, api, store, toast, banner, statusBadge, STATUS, confirmBox, field, select, debounce,
} from './core.js';
import { renderMarkdown, countChars } from './markdown.js';

const SECTIONS = [
  { value: 'news', label: '일반 소식·해설' },
  { value: 'flight', label: '항공·노선' },
  { value: 'data', label: '데이터·통계' },
  { value: 'promo', label: '안내' },
];
const KINDS = ['취재', '기획', '인터뷰', '해설', '보도자료'];
const RESULT = {
  draft: '저장했습니다. 작성중이라 지면에는 나가지 않습니다.',
  review: '검토요청으로 저장했습니다. 관리자가 확인한 뒤 발행합니다.',
  approved: '저장했습니다. 발행대기 — 10분 안팎에 지면에 반영됩니다.',
  published: '저장했습니다. 10분 안팎에 지면에 반영됩니다.',
  hidden: '기사를 내렸습니다. 10분 안팎에 지면에서 빠집니다.',
};
const MAX_PHOTO = 10 * 1024 * 1024;

let flash = null; // 새 기사를 만든 뒤 편집 화면으로 넘어가며 보여 줄 말

function viewMode() {
  try {
    return localStorage.getItem('editor-view') || 'both';
  } catch {
    return 'both';
  }
}

export async function renderEditor(ctx, name) {
  const { main, me } = ctx;
  const isNew = !name;
  const isAdmin = me.role === 'admin';
  main.append(h('div', { class: 'loading' }, h('span', { class: 'spinner' }), ' 기사를 불러오는 중…'));

  let config;
  let art;
  try {
    [config, art] = await Promise.all([
      store.loadSite(),
      isNew ? null : api('GET', `/api/articles/${encodeURIComponent(name)}`),
    ]);
  } catch (e) {
    clear(main).append(banner('bad', e.message, h('a', { class: 'btn small', href: '#/articles' }, '목록으로')));
    return {};
  }

  if (isNew) {
    art = {
      name: null, sha: null, body: '',
      front: { title: '', channel: 'travel', region: '', category: '', topic: '', section: 'news', summary: '', source_name: '', kind: '취재', source_url: '', photo: '', photo_hero: false, status: 'draft' },
      can: { edit: true, statuses: isAdmin ? ['draft', 'review', 'approved'] : ['draft', 'review'] },
    };
  }

  let saving = false;
  let original = '';
  const fr = art.front;

  // ── 칸 ──
  const ro = !art.can.edit;
  const title = h('input', { type: 'text', id: 'f-title', class: 'title-input', value: fr.title || '', maxlength: '200', placeholder: '제목', disabled: ro });

  const channel = select([{ value: 'travel', label: '여행 — 지역면에 실립니다' }, { value: 'ent', label: '문화 — /ent/ 부문에 실립니다' }], fr.channel === 'ent' ? 'ent' : 'travel', { id: 'f-channel', disabled: ro });

  const regionOpts = [{ value: '', label: '— 고르세요 —' }, ...(config.regions || []).map((r) => ({ value: r.id, label: r.name + (r.visible === false ? ' (숨김)' : '') }))];
  if (fr.region && !regionOpts.some((o) => o.value === fr.region)) regionOpts.push({ value: fr.region, label: `(구조에 없음) ${fr.region}` });
  const region = select(regionOpts, fr.region || '', { id: 'f-region', disabled: ro });

  const topicOpts = [{ value: '', label: '자동 — 규칙대로 나눔' }, ...(config.travel_sections || []).map((s) => ({ value: s.id, label: s.name + (s.visible === false ? ' (숨김)' : '') }))];
  if (fr.topic && !topicOpts.some((o) => o.value === fr.topic)) topicOpts.push({ value: fr.topic, label: `(구조에 없음) ${fr.topic}` });
  const topic = select(topicOpts, fr.topic || '', { id: 'f-topic', disabled: ro });

  const catOpts = [{ value: '', label: '자동 — 제목으로 추정' }, ...(config.culture_sections || []).map((s) => ({ value: s.id, label: s.name + (s.visible === false ? ' (숨김)' : '') }))];
  if (fr.category && !catOpts.some((o) => o.value === fr.category)) {
    const to = (config.culture_aliases || {})[fr.category];
    catOpts.push({ value: fr.category, label: to ? `(옛 이름 ${fr.category} → ${to})` : `(구조에 없음) ${fr.category}` });
  }
  const category = select(catOpts, fr.category || '', { id: 'f-category', disabled: ro });

  const secOpts = [...SECTIONS];
  if (fr.section && !secOpts.some((o) => o.value === fr.section)) secOpts.push({ value: fr.section, label: fr.section });
  const section = select(secOpts, fr.section || 'news', { id: 'f-section', disabled: ro });

  const summary = h('textarea', { id: 'f-summary', rows: '3', maxlength: '1000', disabled: ro }, '');
  summary.value = fr.summary || '';

  const nameOpts = [{ value: '', label: '자동 — 그 지면 담당 기자' }, ...(config.reporters || []).map((r) => ({ value: r.name, label: `${r.name} 기자` }))];
  if (fr.source_name && !nameOpts.some((o) => o.value === fr.source_name)) nameOpts.push({ value: fr.source_name, label: `(명부 밖) ${fr.source_name}` });
  const sourceName = select(nameOpts, fr.source_name || '', { id: 'f-source-name', disabled: ro });

  const kindOpts = [{ value: '', label: '— 없음 —' }, ...KINDS.map((k) => ({ value: k, label: k }))];
  if (fr.kind && !KINDS.includes(fr.kind)) kindOpts.push({ value: fr.kind, label: fr.kind });
  const kind = select(kindOpts, fr.kind || '', { id: 'f-kind', disabled: ro });

  const sourceUrl = h('input', { type: 'url', id: 'f-source-url', value: fr.source_url || '', placeholder: 'https://', disabled: ro });

  const statuses = art.can.statuses.length ? art.can.statuses : [fr.status];
  const status = select(statuses.map((s) => ({ value: s, label: STATUS[s] ? STATUS[s].label : s })), fr.status || 'draft', { id: 'f-status', disabled: ro });
  const statusHint = h('div', { class: 'hint' });

  let photo = fr.photo || '';
  const photoBox = h('div', { class: 'photo-box', id: 'photo-box' });
  const photoHero = h('input', { type: 'checkbox', id: 'f-photo-hero', checked: !!fr.photo_hero, disabled: ro });
  const fileInput = h('input', { type: 'file', id: 'f-photo-file', accept: 'image/jpeg,image/png,image/webp', class: 'sr-only', tabindex: '-1' });

  const body = h('textarea', { id: 'f-body', spellcheck: 'false', disabled: ro, placeholder: '본문을 씁니다. 문단 사이는 빈 줄 하나.' });
  body.value = art.body || '';
  const preview = h('div', { class: 'preview', id: 'preview', 'aria-label': '미리보기' });
  const panes = h('div', { class: `body-panes ${viewMode()}` }, body, preview);
  const charCount = h('span', { class: 'muted small' });

  const msg = h('div', { id: 'editor-msg' });
  const dirtyEl = h('span', { class: 'dirty', hidden: true }, '● 저장 안 됨');
  const saveBtn = h('button', { type: 'button', class: 'primary', id: 'save', hidden: ro }, isNew ? '만들기' : '저장');
  const badgeSlot = h('span', {}, statusBadge(fr.status));

  function collect() {
    const f = {
      title: title.value.trim(),
      channel: channel.value,
      region: region.value,
      category: category.value,
      topic: topic.value,
      section: section.value,
      summary: summary.value.trim(),
      source_name: sourceName.value,
      kind: kind.value,
      source_url: sourceUrl.value.trim(),
      photo,
      photo_hero: photoHero.checked,
      status: status.value,
    };
    return f;
  }
  const snapshot = () => JSON.stringify([collect(), body.value]);
  const isDirty = () => !saving && art.can.edit && snapshot() !== original;
  const refreshDirty = () => {
    dirtyEl.hidden = !isDirty();
  };

  // ── 채널에 따라 보이는 칸 ──
  const travelOnly = [];
  const entOnly = [];
  function applyChannel() {
    const ent = channel.value === 'ent';
    for (const el of travelOnly) el.hidden = ent;
    for (const el of entOnly) el.hidden = !ent;
  }
  function applyStatusHint() {
    const s = STATUS[status.value];
    statusHint.textContent = s ? s.hint : '';
  }

  function drawPhoto() {
    clear(photoBox);
    if (photo) {
      const img = h('img', { alt: '대표 사진 미리보기', src: `/api/media?path=${encodeURIComponent(photo.replace(/^\//, ''))}` });
      img.addEventListener('error', () => {
        img.replaceWith(h('div', { class: 'muted small' }, '미리보기를 못 띄웠습니다(사진 반입이 옮겼거나 지웠을 수 있습니다).'));
      });
      photoBox.append(img, h('div', { class: 'path' }, photo));
    } else {
      photoBox.append(h('div', { class: 'muted small' }, '대표 사진이 없습니다.', fr.channel !== 'ent' ? ' 여행 기사는 지역 사진이 자동으로 붙습니다.' : ''));
    }
    if (!ro) {
      photoBox.append(h('div', { class: 'row' },
        h('button', { type: 'button', class: 'small', id: 'photo-upload', on: { click: () => fileInput.click() } }, photo ? '다른 사진 올리기' : '사진 올리기'),
        photo ? h('button', { type: 'button', class: 'small ghost', on: { click: () => { photo = ''; drawPhoto(); refreshDirty(); } } }, '빼기') : null));
    }
  }

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = '';
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return toast('사진은 JPG·PNG·WEBP 만 올릴 수 있습니다', { bad: true });
    if (file.size > MAX_PHOTO) return toast(`사진이 너무 큽니다(${(file.size / 1048576).toFixed(1)}MB). 10MB 까지 올릴 수 있습니다.`, { bad: true });
    clear(photoBox).append(h('div', { class: 'muted' }, h('span', { class: 'spinner' }), ' 사진을 올리는 중…'));
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await api('POST', '/api/upload', fd);
      photo = r.path;
      toast('사진을 올렸습니다. 기사를 저장해야 기사에 붙습니다.');
    } catch (e) {
      toast(`사진을 올리지 못했습니다: ${e.message}`, { bad: true });
    }
    drawPhoto();
    refreshDirty();
  });

  const drawPreview = () => {
    preview.innerHTML = renderMarkdown(body.value); // renderMarkdown 은 글자를 모두 이스케이프한다
    charCount.textContent = `${countChars(body.value).toLocaleString('ko-KR')}자(빈칸 빼고)`;
  };
  const drawPreviewSoon = debounce(drawPreview, 120);

  // ── 저장 ──
  function showErrors(list, head) {
    clear(msg).append(banner('bad', head, h('ul', {}, list.map((x) => h('li', {}, x)))));
    msg.scrollIntoView({ block: 'nearest' });
  }

  async function save() {
    if (saving || !art.can.edit) return;
    const f = collect();
    const errs = [];
    if (!f.title) errs.push('제목을 넣으세요');
    if (f.channel === 'travel' && !f.region) errs.push('여행 기사는 지역면을 고르세요');
    if (f.source_url && !/^https?:\/\//.test(f.source_url)) errs.push('원문 링크는 http:// 나 https:// 로 시작해야 합니다');
    if (errs.length) return showErrors(errs, '저장하기 전에 고칠 곳이 있습니다');
    if (!isNew && f.status === 'hidden' && fr.status !== 'hidden'
        && !(await confirmBox('기사 내리기', '이 기사를 지면·목록·검색·RSS 에서 뺍니다. 나중에 \'발행됨\'으로 바꾸면 돌아옵니다.', { ok: '내리기', kind: 'danger' }))) return;

    saving = true;
    saveBtn.disabled = true;
    saveBtn.textContent = '저장 중…';
    clear(msg);
    try {
      if (isNew) {
        const r = await api('POST', '/api/articles', { front: f, body: body.value });
        store.dropArticles();
        flash = RESULT[r.status] || '만들었습니다.';
        original = snapshot();
        location.hash = `#/edit/${encodeURIComponent(r.name)}`;
        return;
      }
      const r = await api('PUT', `/api/articles/${encodeURIComponent(name)}`, { front: f, body: body.value, sha: art.sha });
      if (r.unchanged) {
        clear(msg).append(banner('info', '바뀐 것이 없어 저장하지 않았습니다.'));
        original = snapshot();
      } else {
        art.sha = r.sha;
        original = snapshot();
        store.dropArticles();
        showSaved(RESULT[r.status] || '저장했습니다.');
        if (ctx.onChange) ctx.onChange();
        await reloadMeta();
      }
    } catch (e) {
      if (e.status === 409) showConflict();
      else if (e.data && Array.isArray(e.data.errors) && e.data.errors.length > 1) showErrors(e.data.errors, '저장하지 못했습니다');
      else clear(msg).append(banner('bad', `저장하지 못했습니다: ${e.message}`));
      msg.scrollIntoView({ block: 'nearest' });
    } finally {
      saving = false;
      saveBtn.disabled = false;
      saveBtn.textContent = isNew ? '만들기' : '저장';
      refreshDirty();
    }
  }

  function showSaved(text) {
    clear(msg).append(banner('ok', text, h('a', { href: '#/deploys', class: 'btn small' }, '발행 상태 보기')));
  }

  function showConflict() {
    const copy = h('button', {
      type: 'button', class: 'small',
      on: {
        click: async () => {
          try {
            await navigator.clipboard.writeText(body.value);
            toast('내 본문을 복사했습니다. 새로 불러온 뒤 붙여 넣으세요.');
          } catch {
            body.focus();
            body.select();
            toast('본문을 선택했습니다. Ctrl+C(⌘C)로 복사하세요.');
          }
        },
      },
    }, '내 본문 복사');
    const reload = h('button', {
      type: 'button', class: 'small primary', id: 'conflict-reload',
      on: {
        click: async () => {
          if (!(await confirmBox('새로 불러오기', '지금 화면의 고친 내용은 버리고 저장소의 최신 기사를 불러옵니다.', { ok: '불러오기', kind: 'danger' }))) return;
          original = snapshot();
          api_.destroy();
          clear(main);
          // 같은 그릇에 다시 그리고, 바깥(app.js)이 쥔 화면 객체도 새 것으로 바꾼다
          Object.assign(api_, await renderEditor(ctx, name));
        },
      },
    }, '새로 불러오기');
    clear(msg).append(banner('warn', '그사이 다른 사람이 고쳤습니다. 내 고친 내용은 아직 이 화면에 있습니다 — 본문을 복사해 두고 새로 불러오세요.', copy, reload));
  }

  async function reloadMeta() {
    // 상태를 바꾸면 고를 수 있는 상태·고칠 권한이 달라진다(예: 기자가 검토요청 → 관리자가 승인)
    try {
      const fresh = await api('GET', `/api/articles/${encodeURIComponent(name)}`);
      art.sha = fresh.sha;
      art.can = fresh.can;
      Object.assign(fr, fresh.front);
      badgeSlot.replaceChildren(statusBadge(fresh.front.status));
      const keepVal = fresh.front.status;
      const opts = fresh.can.statuses.length ? fresh.can.statuses : [keepVal];
      status.replaceChildren(...opts.map((s) => h('option', { value: s }, STATUS[s] ? STATUS[s].label : s)));
      status.value = keepVal;
      drawQuick();
      if (!fresh.can.edit) {
        lockAll(fresh.can.why);
      }
      original = snapshot();
      refreshDirty();
    } catch { /* 저장은 됐다 — 다음에 열 때 맞춰진다 */ }
  }

  function lockAll(why) {
    for (const el of [title, channel, region, topic, category, section, summary, sourceName, kind, sourceUrl, status, photoHero, body]) el.disabled = true;
    saveBtn.hidden = true;
    art.can.edit = false;
    msg.append(banner('info', `이제 이 기사는 고칠 수 없습니다. ${why || ''}`));
    drawPhoto();
  }

  // 관리자 빠른 단추: 승인·내리기·다시 올리기
  const quick = h('div', { class: 'row' });
  function drawQuick() {
    clear(quick);
    if (!isAdmin || isNew || !art.can.edit) return;
    const act = (label, to, kind = '') => h('button', {
      type: 'button', class: `small ${kind}`, dataset: { quick: to },
      on: {
        click: () => {
          status.value = to;
          applyStatusHint();
          save();
        },
      },
    }, label);
    const st = fr.status;
    if (st === 'review' || st === 'draft') quick.append(act('발행대기로 승인하고 저장', 'approved', 'primary'));
    if (st === 'published') quick.append(act('지면에서 내리기', 'hidden', 'danger'));
    if (st === 'hidden' && art.can.statuses.includes('published')) quick.append(act('다시 올리기', 'published'));
  }

  // ── 그리기 ──
  clear(main);
  const back = h('a', { href: '#/articles', class: 'btn small ghost' }, '← 목록');
  const bar = h('div', { class: 'editbar' }, back, badgeSlot,
    h('div', { class: 'title' }, isNew ? '새 기사' : (art.front.title || name)), dirtyEl, saveBtn);

  const regionField = field('지역면', region, { hint: '여행 기사는 반드시 고릅니다.' });
  const topicField = field('여행 부문 (선택)', topic, { hint: '비우면 규칙대로 자동으로 나눕니다. 고르면 그 부문에 실립니다.' });
  const catField = field('문화 부문', category, { hint: '비우면 제목으로 추정하고, 모르면 스타의 여행으로 갑니다.' });
  travelOnly.push(regionField, topicField);
  entOnly.push(catField);

  const pipeline = h('details', {},
    h('summary', {}, '파이프라인 정보 (편집실은 손대지 않습니다)'),
    h('dl', { class: 'meta' },
      ...['id', 'published_id', 'published_on', 'author', 'reason', 'duplicate_of', 'photo_note'].flatMap((k) => (fr[k] ? [h('dt', {}, k), h('dd', {}, String(fr[k]))] : [])),
      ...(Array.isArray(fr.sources) && fr.sources.length ? [h('dt', {}, 'sources'), h('dd', {}, ...fr.sources.map((s) => h('div', {}, String(s))))] : []),
      ...(name ? [h('dt', {}, '파일'), h('dd', {}, `content/review/${name}`)] : [])));

  const viewBtns = h('div', { class: 'body-tools', role: 'group', 'aria-label': '본문 보기' });
  const setView = (v) => {
    panes.className = `body-panes ${v}`;
    for (const b of viewBtns.querySelectorAll('button[data-v]')) b.classList.toggle('on', b.dataset.v === v);
    try {
      localStorage.setItem('editor-view', v);
    } catch { /* */ }
  };
  for (const [v, label] of [['write', '쓰기'], ['both', '나란히'], ['preview-only', '미리보기']]) {
    viewBtns.append(h('button', { type: 'button', dataset: { v }, class: viewMode() === v ? 'on' : '', on: { click: () => setView(v) } }, label));
  }
  viewBtns.append(h('span', { class: 'spacer' }), charCount);

  main.append(...[bar, msg,
    ro ? banner('info', `읽기만 할 수 있습니다. ${art.can.why || ''}`) : null,
    flash ? banner('ok', flash, h('a', { href: '#/deploys', class: 'btn small' }, '발행 상태 보기')) : null,
    h('div', { class: 'editor' },
      h('div', { class: 'col' },
        h('div', { class: 'card' },
          field('제목', title, { hint: '지면에 그대로 나갑니다. 어절 단위로 끊어 읽히게 씁니다.' }),
          field('요약', summary, { hint: '목록과 검색 결과, 카톡 공유 카드에 나옵니다. 한두 문장.' }),
          h('div', { class: 'field' },
            h('label', { for: 'f-body' }, '본문'),
            viewBtns,
            panes,
            h('div', { class: 'hint' }, '신문 기사 형식: 요약 문단 → 발표 문단("○○는 N일 …했다고 밝혔다") → 세부 문단 → 관계자 말. 소제목·목록·표·굵은 글씨·"알아둘 점"은 쓰지 않습니다. 매체 이름("○○ 보도에 따르면")·상품 링크·전화번호는 넣지 않습니다.')))),
      h('div', { class: 'side' },
        h('div', { class: 'card' },
          field('상태', status, {}),
          statusHint,
          quick),
        h('div', { class: 'card' },
          field('채널', channel, { hint: '문화를 고르면 지역면 대신 문화 부문이 지면이 됩니다.' }),
          regionField, topicField, catField,
          field('기사 성격', section, {}),
          field('필자', sourceName, { hint: '비워 두면 그 지면 담당 기자 이름이 붙습니다. 명부에 있는 사람만 고를 수 있습니다(구조 → 기자).' }),
          field('기사 종류', kind, { hint: '취재·기획·인터뷰가 자체 기사입니다(네이버 제휴 심사는 자체 기사 비중 50% 이상을 봅니다). 보도자료를 다시 쓴 것은 \'보도자료\', 여러 매체 보도를 묶어 정리한 것은 \'해설\'.' }),
          field('원문 링크', sourceUrl, { hint: '다른 매체 보도나 보도자료를 정리한 경우에만 넣습니다.' })),
        h('div', { class: 'card' },
          h('label', {}, '대표 사진'),
          photoBox, fileInput,
          h('div', { class: 'hint small muted' }, '직접 찍은 사진만. 얼굴이 보이면 지면에 안 나갑니다(자동 검사). 공개 저장소라 올린 원본은 지워도 이력에 남습니다. 연예인 사진은 본인·소속사 동의가 있을 때만. JPG·PNG·WEBP, 10MB 까지.'),
          h('div', { class: 'field' }, h('label', { class: 'check' }, photoHero, '1면용 풍경 사진'), h('div', { class: 'hint' }, '사람 없는 풍경이면 켭니다. 1면과 지역면 톱에 우선 쓰입니다.')),
          fr.photo_note ? banner('warn', `사진 검사 결과: ${fr.photo_note}`) : null),
        isNew ? null : h('div', { class: 'card' }, pipeline)))].filter(Boolean));
  flash = null;

  applyChannel();
  applyStatusHint();
  drawPhoto();
  drawPreview();
  drawQuick();
  original = snapshot();

  // ── 이벤트 ──
  const onAnyChange = () => refreshDirty();
  main.addEventListener('input', onAnyChange);
  main.addEventListener('change', onAnyChange);
  channel.addEventListener('change', applyChannel);
  status.addEventListener('change', applyStatusHint);
  body.addEventListener('input', drawPreviewSoon);
  saveBtn.addEventListener('click', save);
  const onKey = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      save();
    }
  };
  document.addEventListener('keydown', onKey);
  if (isNew) title.focus();

  const api_ = {
    isDirty,
    destroy() {
      document.removeEventListener('keydown', onKey);
    },
  };
  return api_;
}
