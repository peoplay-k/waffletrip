// 계정(관리자: 만들기·역할·비밀번호 재설정·중지·지우기 / 모두: 내 비밀번호 바꾸기)과 변경 기록.

import { h, clear, api, toast, banner, modal, confirmBox, ROLE, when, randomPassword, field, select } from './core.js';

function passwordForm(onDone) {
  const cur = h('input', { type: 'password', id: 'pw-current', autocomplete: 'current-password' });
  const next = h('input', { type: 'password', id: 'pw-next', autocomplete: 'new-password', minlength: '8' });
  const next2 = h('input', { type: 'password', id: 'pw-next2', autocomplete: 'new-password', minlength: '8' });
  const msg = h('div');
  const btn = h('button', { type: 'submit', class: 'primary' }, '비밀번호 바꾸기');
  return h('form', {
    class: 'card', id: 'my-password',
    on: {
      submit: async (e) => {
        e.preventDefault();
        clear(msg);
        if (next.value.length < 10) return msg.append(banner('bad', '새 비밀번호는 10자 이상이어야 합니다'));
        if (next.value !== next2.value) return msg.append(banner('bad', '새 비밀번호 두 칸이 서로 다릅니다'));
        btn.disabled = true;
        try {
          await api('POST', '/api/me/password', { current: cur.value, next: next.value });
          cur.value = next.value = next2.value = '';
          msg.append(banner('ok', '비밀번호를 바꿨습니다. 다른 기기의 로그인은 끊겼습니다.'));
          if (onDone) onDone();
        } catch (ex) {
          msg.append(banner('bad', ex.message));
        } finally {
          btn.disabled = false;
        }
      },
    },
  },
  h('h2', {}, '내 비밀번호 바꾸기'),
  msg,
  h('div', { class: 'grid3' },
    field('지금 비밀번호', cur),
    field('새 비밀번호', next, { hint: '10자 이상' }),
    field('새 비밀번호 확인', next2)),
  btn);
}

export async function renderAccounts(ctx) {
  const { main, me } = ctx;
  main.append(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, '계정'),
    h('p', {}, me.role === 'admin' ? '편집실을 쓰는 사람을 만들고 관리합니다. 기자는 자기가 만든 기사만, 작성중·검토요청 상태일 때만 고칠 수 있습니다.' : `${me.name}(${me.username}) · ${ROLE[me.role]}`))));
  if (me.role !== 'admin') {
    main.append(passwordForm());
    return {};
  }

  const listBox = h('div', { class: 'card' }, h('div', { class: 'loading' }, h('span', { class: 'spinner' }), ' 계정을 불러오는 중…'));
  const createMsg = h('div');
  const u = h('input', { type: 'text', id: 'new-username', autocapitalize: 'none', spellcheck: 'false', placeholder: '예: kimts' });
  const n = h('input', { type: 'text', id: 'new-name', placeholder: '예: 김태성' });
  const role = select([{ value: 'reporter', label: '기자 — 자기 기사만' }, { value: 'admin', label: '관리자 — 모든 권한' }], 'reporter', { id: 'new-role' });
  const pw = h('input', { type: 'text', id: 'new-password', autocomplete: 'off', spellcheck: 'false', class: 'mono' });
  const gen = h('button', { type: 'button', class: 'small', on: { click: () => { pw.value = randomPassword(); } } }, '무작위로 만들기');
  const createBtn = h('button', { type: 'submit', class: 'primary', id: 'create-user' }, '계정 만들기');
  const createForm = h('form', {
    class: 'card', id: 'create-user-form',
    on: {
      submit: async (e) => {
        e.preventDefault();
        clear(createMsg);
        createBtn.disabled = true;
        try {
          await api('POST', '/api/users', { username: u.value.trim().toLowerCase(), name: n.value.trim(), role: role.value, password: pw.value });
          createMsg.append(banner('ok', `${n.value.trim()}(${u.value.trim().toLowerCase()}) 계정을 만들었습니다. 처음 비밀번호를 본인에게 직접 알려 주고, 로그인한 뒤 바꾸라고 하세요.`));
          u.value = n.value = pw.value = '';
          role.value = 'reporter';
          await loadUsers();
        } catch (ex) {
          createMsg.append(banner('bad', ex.message));
        } finally {
          createBtn.disabled = false;
        }
      },
    },
  },
  h('h2', {}, '계정 만들기'),
  createMsg,
  h('div', { class: 'grid2' },
    field('아이디', u, { hint: '영문 소문자·숫자 2~24자. 나중에 못 바꿉니다.' }),
    field('이름', n, { hint: '화면에 보이는 이름' }),
    field('역할', role),
    h('div', { class: 'field' }, h('label', { for: 'new-password' }, '처음 비밀번호'), h('div', { class: 'row' }, pw, gen), h('div', { class: 'hint' }, '10자 이상. 본인에게 직접 알려 줍니다(채팅방에 남기지 않습니다).'))),
  createBtn);

  main.append(listBox, createForm, passwordForm());

  async function act(username, body, okText) {
    try {
      await api('PUT', `/api/users/${encodeURIComponent(username)}`, body);
      toast(okText);
      await loadUsers();
    } catch (e) {
      toast(e.message, { bad: true });
      await loadUsers();
    }
  }

  async function resetPassword(user) {
    const input = h('input', { type: 'text', id: 'reset-password', class: 'mono', value: randomPassword(), spellcheck: 'false' });
    const err = h('div');
    await modal({
      title: `${user.name}(${user.username}) 비밀번호 재설정`,
      body: h('div', {}, err, field('새 비밀번호', input, { hint: '10자 이상. 본인에게 직접 알려 주세요. 그 사람의 로그인은 모두 끊깁니다.' })),
      buttons: [{ label: '취소', value: false }, { label: '재설정', kind: 'primary', value: true }],
      onButton: async (v, ctl) => {
        if (!v) return true;
        clear(err);
        if (input.value.length < 10) {
          err.append(banner('bad', '비밀번호는 10자 이상이어야 합니다'));
          return false;
        }
        ctl.setBusy(true);
        try {
          await api('PUT', `/api/users/${encodeURIComponent(user.username)}`, { password: input.value });
          toast('비밀번호를 새로 정했습니다');
          return true;
        } catch (e) {
          err.append(banner('bad', e.message));
          ctl.setBusy(false);
          return false;
        }
      },
    });
  }

  async function loadUsers() {
    let users;
    try {
      users = (await api('GET', '/api/users')).users;
    } catch (e) {
      clear(listBox).append(banner('bad', `계정을 읽지 못했습니다: ${e.message}`, h('button', { type: 'button', on: { click: loadUsers } }, '다시 시도')));
      return;
    }
    const rows = users.map((user) => {
      const self = user.username === me.username;
      const roleSel = select([{ value: 'reporter', label: '기자' }, { value: 'admin', label: '관리자' }], user.role, { disabled: self, 'aria-label': `${user.username} 역할` });
      roleSel.addEventListener('change', async () => {
        const to = roleSel.value;
        if (await confirmBox('역할 바꾸기', `${user.name}의 역할을 ${ROLE[to]}(으)로 바꿉니다. 그 사람은 다시 로그인해야 합니다.`)) act(user.username, { role: to }, '역할을 바꿨습니다');
        else roleSel.value = user.role;
      });
      return h('tr', { dataset: { user: user.username } },
        h('td', { class: 'mono' }, user.username),
        h('td', {}, user.name, self ? h('span', { class: 'badge neutral' }, ' 나') : null),
        h('td', {}, roleSel),
        h('td', {}, user.disabled ? h('span', { class: 'badge s-hidden' }, '중지') : h('span', { class: 'badge s-published' }, '사용')),
        h('td', { class: 'small muted nowrap' }, when(user.created_at)),
        h('td', {}, h('div', { class: 'row' },
          h('button', { type: 'button', class: 'small', on: { click: () => resetPassword(user) } }, '비밀번호 재설정'),
          self ? null : h('button', {
            type: 'button', class: 'small',
            on: {
              click: async () => {
                if (user.disabled) act(user.username, { disabled: false }, '다시 쓸 수 있게 했습니다');
                else if (await confirmBox('사용 중지', `${user.name}(${user.username})은 더 이상 로그인할 수 없고, 지금 로그인도 끊깁니다. 만든 기사는 그대로 남습니다.`, { ok: '중지', kind: 'danger' })) act(user.username, { disabled: true }, '사용을 중지했습니다');
              },
            },
          }, user.disabled ? '다시 사용' : '사용 중지'),
          self ? null : h('button', {
            type: 'button', class: 'small danger',
            on: {
              click: async () => {
                if (!(await confirmBox('계정 지우기', `${user.name}(${user.username}) 계정을 지웁니다. 되돌릴 수 없습니다. 잠깐 막을 거라면 '사용 중지'를 쓰세요. 만든 기사는 그대로 남습니다.`, { ok: '지우기', kind: 'danger' }))) return;
                try {
                  await api('DELETE', `/api/users/${encodeURIComponent(user.username)}`);
                  toast('계정을 지웠습니다');
                } catch (e) {
                  toast(e.message, { bad: true });
                }
                loadUsers();
              },
            },
          }, '지우기'))));
    });
    clear(listBox).append(h('h2', {}, `계정 ${users.length}개`),
      h('div', { class: 'table-wrap' }, h('table', { class: 'data', id: 'users-table' },
        h('thead', {}, h('tr', {}, ['아이디', '이름', '역할', '상태', '만든 때', ''].map((t) => h('th', {}, t)))),
        h('tbody', {}, rows))));
  }

  await loadUsers();
  return {};
}

export async function renderLog(ctx) {
  const { main } = ctx;
  main.append(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, '변경 기록'),
    h('p', {}, '편집실에서 누가 언제 무엇을 바꿨는지입니다. 기사·구조 변경은 저장소 커밋으로도 남습니다.'))));
  const tbody = h('tbody');
  const more = h('button', { type: 'button', hidden: true }, '더 보기');
  const box = h('div', { class: 'card' }, h('div', { class: 'table-wrap' }, h('table', { class: 'data', id: 'log-table' },
    h('thead', {}, h('tr', {}, ['때', '누가', '무엇', '대상', '자세히'].map((t) => h('th', {}, t)))), tbody)), h('div', { class: 'list-foot' }, more));
  const msg = h('div');
  main.append(msg, box);
  let last = 0;
  async function load() {
    more.disabled = true;
    try {
      const { log } = await api('GET', `/api/log?limit=100${last ? `&before=${last}` : ''}`);
      if (!last && !log.length) tbody.append(h('tr', {}, h('td', { colspan: '5', class: 'empty' }, '아직 기록이 없습니다.')));
      for (const r of log) {
        tbody.append(h('tr', {},
          h('td', { class: 'nowrap small' }, when(r.ts, true)),
          h('td', { class: 'mono' }, r.username),
          h('td', {}, r.action),
          h('td', { class: 'mono small' }, r.target),
          h('td', { class: 'detail' }, r.detail)));
        last = r.id;
      }
      more.hidden = log.length < 100;
    } catch (e) {
      msg.append(banner('bad', e.message));
    } finally {
      more.disabled = false;
    }
  }
  more.addEventListener('click', load);
  await load();
  return {};
}
