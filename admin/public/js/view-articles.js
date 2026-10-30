// 기사 목록 · 검토요청 대기열.

import { h, clear, store, statusBadge, STATUS, banner, debounce, regionName, cultureName, select } from './core.js';
import { articleSiteUrl } from '../shared/article_url.js';

const PAGE = 50;
const TABS = ['', 'draft', 'review', 'approved', 'published', 'hidden', 'duplicate'];

function dateOf(a) {
  if (a.published_on) return a.published_on;
  const m = /^(\d{4})-?(\d{2})-?(\d{2})_/.exec(a.path);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : '';
}

export async function renderArticleList(ctx, { reviewQueue = false }) {
  const { main, me, query } = ctx;
  const isAdmin = me.role === 'admin';
  const f = {
    q: query.get('q') || '',
    status: reviewQueue ? 'review' : (query.get('status') || ''),
    channel: query.get('channel') || '',
    region: query.get('region') || '',
    category: query.get('category') || '',
    mine: query.get('mine') === '1',
    page: Math.max(1, Number(query.get('page')) || 1),
  };

  const head = h('div', { class: 'page-head' },
    h('div', {},
      h('h1', {}, reviewQueue ? '검토요청' : '기사'),
      h('p', {}, reviewQueue
        ? '기자가 다 썼다고 올린 기사입니다. 열어서 읽고, 상태를 \'발행대기\'로 바꿔 저장하면 다음 발행 때 지면에 나갑니다.'
        : '최신 기사가 위에 옵니다(발행일, 발행 전 원고는 만든 날 기준).')),
    h('div', { class: 'spacer' }),
    h('button', { type: 'button', on: { click: () => load(true) }, title: '저장소에서 새로 읽기' }, '새로 고침'),
    h('a', { class: 'btn primary', href: '#/new', id: 'new-article' }, '+ 새 기사'));
  const msg = h('div');
  const tabs = h('div', { class: 'tabs', role: 'tablist', 'aria-label': '상태' });
  const filters = h('div', { class: 'filters' });
  const countLine = h('div', { class: 'muted small', 'aria-live': 'polite' });
  const listEl = h('div', { class: 'list' }, ...Array.from({ length: 6 }, () => h('div', { class: 'skeleton' })));
  const foot = h('div', { class: 'list-foot' });
  main.append(...[head, msg, reviewQueue ? null : tabs, filters, countLine, listEl, foot].filter(Boolean));

  let all = [];
  let config = null;

  // 걸러 낸 조건을 주소에 남긴다 — 기사를 열었다가 뒤로 오면 같은 자리로 돌아오게
  function syncUrl() {
    const p = new URLSearchParams();
    for (const k of ['q', 'status', 'channel', 'region', 'category']) if (f[k] && !(reviewQueue && k === 'status')) p.set(k, f[k]);
    if (f.mine) p.set('mine', '1');
    if (f.page > 1) p.set('page', String(f.page));
    const base = reviewQueue ? '#/review' : '#/articles';
    const s = p.toString();
    history.replaceState(null, '', s ? `${base}?${s}` : base);
  }

  function matches(a, ignoreStatus = false) {
    if (!ignoreStatus && f.status && a.status !== f.status) return false;
    if (f.channel && (a.channel || 'travel') !== f.channel) return false;
    if (f.region && a.region !== f.region) return false;
    if (f.category && a.category !== f.category && (config?.culture_aliases || {})[a.category] !== f.category) return false;
    if (f.mine && a.author !== me.username) return false;
    if (f.q) {
      const q = f.q.toLowerCase();
      const hay = [a.title, a.path, a.author, a.source_name, a.id, a.published_id].join(' ').toLowerCase();
      if (!q.split(/\s+/).filter(Boolean).every((w) => hay.includes(w))) return false;
    }
    return true;
  }

  function buildFilters() {
    const q = h('input', { type: 'search', class: 'q', id: 'article-search', placeholder: '제목·파일 이름·필자·아이디로 찾기', value: f.q, 'aria-label': '찾기' });
    q.addEventListener('input', debounce(() => {
      f.q = q.value.trim();
      f.page = 1;
      draw();
    }, 150));
    const regions = (config?.regions || []).map((r) => ({ value: r.id, label: r.name + (r.visible === false ? ' (숨김)' : '') }));
    const cultures = (config?.culture_sections || []).map((s) => ({ value: s.id, label: s.name }));
    const mk = (key, label, options) => {
      const el = select([{ value: '', label }, ...options], f[key], { 'aria-label': label, id: `filter-${key}` });
      el.addEventListener('change', () => {
        f[key] = el.value;
        f.page = 1;
        draw();
      });
      return el;
    };
    const mine = h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: f.mine, id: 'filter-mine', on: { change: (e) => { f.mine = e.target.checked; f.page = 1; draw(); } } }), '내가 만든 기사');
    // 상태는 위의 탭으로 고른다
    clear(filters).append(q,
      mk('channel', '채널: 전체', [{ value: 'travel', label: '여행' }, { value: 'ent', label: '문화' }]),
      mk('region', '지역: 전체', regions),
      mk('category', '문화 부문: 전체', cultures),
      mine);
  }

  function drawTabs() {
    if (reviewQueue) return;
    clear(tabs);
    const base = all.filter((a) => matches(a, true));
    for (const s of TABS) {
      const n = s ? base.filter((a) => a.status === s).length : base.length;
      if (s === 'duplicate' && !n && f.status !== s) continue;
      tabs.append(h('button', {
        type: 'button', role: 'tab', class: f.status === s ? 'on' : '', 'aria-selected': String(f.status === s),
        on: {
          click: () => {
            f.status = s;
            f.page = 1;
            buildFilters();
            draw();
          },
        },
      }, s ? STATUS[s].label : '전체', h('span', { class: 'n' }, String(n))));
    }
  }

  function row(a) {
    const siteUrl = articleSiteUrl(a, store.me && store.me.site_url);
    const where = (a.channel || 'travel') === 'ent'
      ? `문화 · ${a.category ? cultureName(config, a.category) : '부문 자동'}`
      : `여행 · ${a.region ? regionName(config, a.region) : '지역 없음'}`;
    return h('a', { class: 'list-row', href: `#/edit/${encodeURIComponent(a.path)}`, dataset: { path: a.path } },
      h('div', { class: 'st' }, statusBadge(a.status)),
      h('div', { class: 'main' },
        h('div', { class: 't' }, a.title || a.path),
        a.error ? h('div', { class: 'err' }, a.error) : null,
        h('div', { class: 'm' },
          h('span', {}, where),
          h('span', {}, dateOf(a) || '날짜 없음'),
          a.source_name ? h('span', {}, `필자 ${a.source_name}`) : null,
          a.author ? h('span', {}, `만든 사람 ${a.author}`) : null,
          h('span', { class: 'mono' }, a.path),
          siteUrl ? h('button', {
            type: 'button', class: 'linkish site-link', title: '지면에서 보기',
            on: { click: (e) => { e.preventDefault(); e.stopPropagation(); window.open(siteUrl, '_blank', 'noopener'); } },
          }, '기사 보기 ↗') : null)));
  }

  function draw() {
    syncUrl();
    drawTabs();
    const rows = all.filter((a) => matches(a));
    const pages = Math.max(1, Math.ceil(rows.length / PAGE));
    if (f.page > pages) f.page = pages;
    const slice = rows.slice((f.page - 1) * PAGE, f.page * PAGE);
    countLine.textContent = rows.length === all.length ? `${all.length}건` : `${all.length}건 중 ${rows.length}건`;
    clear(listEl);
    if (!rows.length) {
      const anyFilter = f.q || f.channel || f.region || f.category || f.mine || (!reviewQueue && f.status);
      listEl.append(h('div', { class: 'empty' },
        reviewQueue && !anyFilter ? '검토를 기다리는 기사가 없습니다.' : '조건에 맞는 기사가 없습니다.',
        anyFilter ? h('div', {}, h('button', {
          type: 'button', class: 'small',
          on: {
            click: () => {
              Object.assign(f, { q: '', channel: '', region: '', category: '', mine: false, page: 1 });
              if (!reviewQueue) f.status = '';
              buildFilters();
              draw();
            },
          },
        }, '조건 지우기')) : null));
    } else listEl.append(...slice.map(row));
    clear(foot);
    if (pages > 1) {
      const go = (p) => {
        f.page = p;
        draw();
        listEl.scrollIntoView({ block: 'start' });
      };
      foot.append(
        h('button', { type: 'button', class: 'small', disabled: f.page <= 1, on: { click: () => go(1) } }, '« 처음'),
        h('button', { type: 'button', class: 'small', disabled: f.page <= 1, on: { click: () => go(f.page - 1) } }, '‹ 앞'),
        h('span', { class: 'muted small', id: 'page-info' }, `${f.page} / ${pages} 쪽`),
        h('button', { type: 'button', class: 'small', disabled: f.page >= pages, on: { click: () => go(f.page + 1) } }, '뒤 ›'),
        h('button', { type: 'button', class: 'small', disabled: f.page >= pages, on: { click: () => go(pages) } }, '끝 »'));
    }
  }

  async function load(force = false) {
    clear(msg);
    if (force) {
      clear(listEl).append(...Array.from({ length: 6 }, () => h('div', { class: 'skeleton' })));
    }
    try {
      const hadConfig = !!config;
      // 목록은 늘 새로 확인한다(다른 사람이 방금 올린 기사가 보여야 한다). 서버가 폴더 해시로 캐시해 빠르다.
      [all, config] = await Promise.all([store.loadArticles(true), store.loadSite(force).catch(() => config)]);
      if (!hadConfig || force) buildFilters();
      draw();
      if (ctx.onChange) ctx.onChange();
    } catch (e) {
      if (!all.length) clear(listEl);
      msg.append(banner('bad', `목록을 읽지 못했습니다: ${e.message}`, h('button', { type: 'button', on: { click: () => load(true) } }, '다시 시도')));
    }
  }

  // 기억해 둔 목록이 있으면 먼저 그려 두고(빠르게), 새 목록이 오면 다시 그린다
  if (store.articles) {
    all = store.articles;
    config = store.site;
    buildFilters();
    draw();
  } else buildFilters();
  await load();
  return {};
}
