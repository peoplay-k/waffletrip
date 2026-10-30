// 발행 상태 — GitHub Actions '매일 발행'(daily.yml) 최근 실행.

import { h, clear, api, banner, confirmBox, toast, when, ago } from './core.js';

const EVENT = { push: '저장해서', schedule: '예약(매일 아침)', workflow_dispatch: '수동' };

function runState(r) {
  if (r.status !== 'completed') return { label: r.status === 'queued' || r.status === 'waiting' || r.status === 'pending' ? '대기' : '발행 중', cls: 's-approved' };
  if (r.conclusion === 'success') return { label: '완료', cls: 's-published' };
  if (r.conclusion === 'cancelled' || r.conclusion === 'skipped') return { label: '취소', cls: 's-draft' };
  return { label: '실패', cls: 's-hidden' };
}

export async function renderDeploys(ctx) {
  const { main, me } = ctx;
  const now = h('div', { class: 'card', id: 'deploy-now' }, h('div', { class: 'loading' }, h('span', { class: 'spinner' }), ' 불러오는 중…'));
  const list = h('div', { class: 'card' });
  const dispatchBtn = me.role === 'admin' ? h('button', {
    type: 'button', id: 'dispatch',
    on: {
      click: async () => {
        if (!(await confirmBox('지금 발행', '\'매일 발행\'을 지금 한 번 돌립니다. 발행대기 기사와 구조 변경이 10분 안팎에 지면에 반영됩니다.', { ok: '발행 시작' }))) return;
        dispatchBtn.disabled = true;
        try {
          await api('POST', '/api/deploys');
          toast('발행을 시작했습니다. 몇 초 뒤 목록에 나옵니다.');
          setTimeout(load, 3000);
        } catch (e) {
          toast(e.message, { bad: true });
        } finally {
          dispatchBtn.disabled = false;
        }
      },
    },
  }, '지금 발행') : null;
  main.append(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, '발행 상태'),
    h('p', {}, '기사를 저장하면 GitHub 의 \'매일 발행\'이 돌아 10분 안팎에 지면(waffletrip.com)에 반영됩니다.')),
  h('div', { class: 'spacer' }),
  h('button', { type: 'button', on: { click: () => load() } }, '새로 고침'), dispatchBtn), now, list);

  let timer = null;
  let alive = true;
  async function load() {
    clearTimeout(timer);
    if (!alive) return;
    let data;
    try {
      data = await api('GET', '/api/deploys');
      if (!alive) return;
    } catch (e) {
      if (!alive) return;
      clear(now).append(banner('bad', `발행 상태를 읽지 못했습니다: ${e.message}`));
      timer = setTimeout(load, 30000);
      return;
    }
    const runs = data.runs || [];
    const latest = runs[0];
    clear(now);
    if (!latest) now.append(h('div', { class: 'deploy-now' }, h('span', { class: 'big-dot' }), '아직 발행 기록이 없습니다'));
    else if (data.running) {
      const r = runs.find((x) => x.status !== 'completed');
      now.append(h('div', { class: 'deploy-now running', id: 'deploy-state' }, h('span', { class: 'big-dot' }), `발행 중 — ${ago(r.run_started_at)} 시작`),
        h('p', { class: 'muted small' }, '끝나면 이 화면이 저절로 바뀝니다.'));
    } else {
      const st = runState(latest);
      const ok = st.label === '완료';
      // DOM 의 append 는 null 을 'null' 글자로 붙인다 — 실패했을 때만 안내 문장을 넣는다
      now.append(h('div', { class: `deploy-now ${ok ? 'ok' : 'bad'}`, id: 'deploy-state' }, h('span', { class: 'big-dot' }),
        ok ? `발행 완료 — ${ago(latest.updated_at)}` : `마지막 발행 ${st.label} — ${ago(latest.updated_at)}`));
      if (!ok) now.append(h('p', { class: 'muted small' }, '실패했으면 지면이 안 바뀌었을 수 있습니다. GitHub 에서 기록을 보거나 관리자에게 알리세요.'));
    }
    clear(list).append(h('h2', {}, '최근 실행'),
      runs.length ? h('div', { class: 'table-wrap' }, h('table', { class: 'data', id: 'runs' },
        h('thead', {}, h('tr', {}, ['상태', '시작', '계기', '내용', ''].map((t) => h('th', {}, t)))),
        h('tbody', {}, runs.map((r) => {
          const st = runState(r);
          return h('tr', {},
            h('td', {}, h('span', { class: `badge ${st.cls}` }, st.label)),
            h('td', { class: 'nowrap small' }, when(r.run_started_at), h('div', { class: 'muted' }, ago(r.run_started_at))),
            h('td', { class: 'small' }, EVENT[r.event] || r.event),
            h('td', {}, r.title),
            h('td', {}, r.url ? h('a', { href: r.url, target: '_blank', rel: 'noopener noreferrer' }, 'GitHub 에서 보기') : null));
        })))) : h('p', { class: 'muted' }, '기록이 없습니다.'));
    // 발행 중이면 자주, 아니면 가끔 다시 본다
    timer = setTimeout(load, data.running ? 10000 : 60000);
  }
  await load();
  return {
    destroy() {
      alive = false;
      clearTimeout(timer);
    },
  };
}
