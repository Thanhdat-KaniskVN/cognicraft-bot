// store/web/presence.js
/**
 * CogniCraft Presence Widget
 * - Auto-inject floating widget
 * - Heartbeat mỗi 30s
 * - Hiển thị list online/offline
 * - Toggle status: online / away / invisible
 */
(function () {
  'use strict';

  // ============================================================
  // CONFIG
  // ============================================================
  const API_BASE =
    window.COGNI_API_BASE ||
    (window.location.hostname === 'localhost'
      ? 'http://localhost:8001'
      : 'https://web-production-8b760.up.railway.app');

  const HEARTBEAT_MS = 30_000;   // 30s
  const REFRESH_MS   = 20_000;   // refresh list mỗi 20s

  // ============================================================
  // TOKEN HELPERS — thử nhiều key để tương thích
  // ============================================================
  function getToken() {
    return (
      localStorage.getItem('cognicraft_token') ||
      localStorage.getItem('token') ||
      localStorage.getItem('cogni_token') ||
      null
    );
  }

  function isLoggedIn() {
    return !!getToken();
  }

  // ============================================================
  // API
  // ============================================================
  async function api(path, options = {}) {
    const token = getToken();
    if (!token) throw new Error('NO_TOKEN');

    const res = await fetch(API_BASE + path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + token,
        ...(options.headers || {}),
      },
    });

    if (res.status === 401) throw new Error('UNAUTHORIZED');
    if (!res.ok) throw new Error('API_ERROR_' + res.status);
    return res.json();
  }

  async function ping() {
    return api('/api/presence/ping', { method: 'POST' });
  }

  async function fetchList() {
    return api('/api/presence/list');
  }

  async function fetchMe() {
    return api('/api/presence/me');
  }

  async function updateStatus(payload) {
    return api('/api/presence/status', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async function goOffline() {
    return api('/api/presence/offline', { method: 'POST' });
  }

  // ============================================================
  // CSS — inject 1 lần
  // ============================================================
  function injectStyles() {
    if (document.getElementById('presence-styles')) return;

    const style = document.createElement('style');
    style.id = 'presence-styles';
    style.textContent = `
      .presence-widget {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }

      .presence-toggle {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 16px;
        background: linear-gradient(135deg, #6d28d9 0%, #a855f7 100%);
        color: white;
        border: none;
        border-radius: 999px;
        cursor: pointer;
        box-shadow: 0 8px 24px rgba(168, 85, 247, 0.4);
        font-size: 14px;
        font-weight: 600;
        transition: transform 0.2s, box-shadow 0.2s;
      }

      .presence-toggle:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(168, 85, 247, 0.55);
      }

      .presence-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #22c55e;
        box-shadow: 0 0 8px #22c55e;
        animation: presence-pulse 2s infinite;
      }

      @keyframes presence-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
      }

      .presence-panel {
        position: absolute;
        bottom: 60px;
        right: 0;
        width: 320px;
        max-height: 480px;
        background: #1a0b2e;
        border: 1px solid rgba(168, 85, 247, 0.3);
        border-radius: 16px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
        overflow: hidden;
        display: none;
        flex-direction: column;
        animation: presence-slide 0.2s ease-out;
      }

      @keyframes presence-slide {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
      }

      .presence-panel.open {
        display: flex;
      }

      .presence-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 16px;
        border-bottom: 1px solid rgba(168, 85, 247, 0.2);
      }

      .presence-title {
        color: #fff;
        font-weight: 700;
        font-size: 14px;
      }

      .presence-settings-btn {
        background: transparent;
        border: none;
        color: #a855f7;
        cursor: pointer;
        font-size: 18px;
        padding: 4px 8px;
        border-radius: 6px;
      }

      .presence-settings-btn:hover {
        background: rgba(168, 85, 247, 0.15);
      }

      .presence-settings {
        display: none;
        padding: 12px 16px;
        border-bottom: 1px solid rgba(168, 85, 247, 0.2);
        background: rgba(168, 85, 247, 0.05);
      }

      .presence-settings.open { display: block; }

      .presence-settings label {
        display: block;
        color: #c4b5fd;
        font-size: 12px;
        margin-bottom: 8px;
        font-weight: 600;
      }

      .presence-settings select,
      .presence-settings input[type=checkbox] {
        width: 100%;
        padding: 8px 10px;
        background: #2d1b4e;
        color: #fff;
        border: 1px solid rgba(168, 85, 247, 0.3);
        border-radius: 8px;
        font-size: 13px;
        margin-bottom: 12px;
      }

      .presence-settings input[type=checkbox] {
        width: auto;
        margin-right: 6px;
      }

      .presence-list {
        flex: 1;
        overflow-y: auto;
        padding: 8px 0;
      }

      .presence-section-title {
        padding: 8px 16px 4px;
        color: #a855f7;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
      }

      .presence-user {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 16px;
        cursor: pointer;
        transition: background 0.15s;
      }

      .presence-user:hover {
        background: rgba(168, 85, 247, 0.1);
      }

      .presence-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        object-fit: cover;
        border: 2px solid #4c1d95;
      }

      .presence-avatar.online { border-color: #22c55e; }
      .presence-avatar.offline { border-color: #4c1d95; opacity: 0.5; }

      .presence-user-info {
        flex: 1;
        min-width: 0;
      }

      .presence-user-name {
        color: #fff;
        font-size: 13px;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .presence-user-sub {
        color: #a78bfa;
        font-size: 11px;
      }

      .presence-empty {
        padding: 20px 16px;
        text-align: center;
        color: #6d28d9;
        font-size: 13px;
      }

      .presence-list::-webkit-scrollbar { width: 6px; }
      .presence-list::-webkit-scrollbar-thumb {
        background: #6d28d9;
        border-radius: 3px;
      }
    `;
    document.head.appendChild(style);
  }

  // ============================================================
  // RENDER
  // ============================================================
  let panelOpen = false;
  let settingsOpen = false;

  function timeAgo(isoStr) {
    if (!isoStr) return '';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'vừa xong';
    if (diff < 3600) return Math.floor(diff / 60) + ' phút trước';
    if (diff < 86400) return Math.floor(diff / 3600) + ' giờ trước';
    return Math.floor(diff / 86400) + ' ngày trước';
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function renderPanel(data, me) {
    const panel = document.querySelector('.presence-panel');
    if (!panel) return;

    const online = data.online || [];
    const offline = data.offline || [];

    let html = `
      <div class="presence-header">
        <div class="presence-title">👥 Cộng đồng CogniCraft</div>
        <button class="presence-settings-btn" id="presence-settings-btn" title="Cài đặt">⚙️</button>
      </div>

      <div class="presence-settings" id="presence-settings">
        <label>Trạng thái của em</label>
        <select id="presence-status-select">
          <option value="online"    ${me.status === 'online' ? 'selected' : ''}>🟢 Online</option>
          <option value="away"      ${me.status === 'away' ? 'selected' : ''}>🟡 Away</option>
          <option value="invisible" ${me.status === 'invisible' ? 'selected' : ''}>⚫ Ẩn danh</option>
        </select>

        <label style="display:flex;align-items:center;color:#c4b5fd;">
          <input type="checkbox" id="presence-show-toggle" ${me.show_online ? 'checked' : ''}>
          Hiện trong danh sách
        </label>
      </div>

      <div class="presence-list">
    `;

    if (online.length > 0) {
      html += `<div class="presence-section-title">🟢 Đang online (${online.length})</div>`;
      online.forEach((u) => {
        html += `
          <div class="presence-user" data-user-id="${esc(u.id)}">
            <img class="presence-avatar online" src="${esc(u.avatar_url || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + u.id)}" alt="">
            <div class="presence-user-info">
              <div class="presence-user-name">${esc(u.name)}</div>
              <div class="presence-user-sub">${u.github_username ? '@' + esc(u.github_username) : 'Đang hoạt động'}</div>
            </div>
          </div>
        `;
      });
    } else {
      html += `<div class="presence-empty">Chưa có ai online 🌙</div>`;
    }

    if (offline.length > 0) {
      html += `<div class="presence-section-title">⚫ Offline</div>`;
      offline.slice(0, 20).forEach((u) => {
        html += `
          <div class="presence-user" data-user-id="${esc(u.id)}">
            <img class="presence-avatar offline" src="${esc(u.avatar_url || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + u.id)}" alt="">
            <div class="presence-user-info">
              <div class="presence-user-name">${esc(u.name)}</div>
              <div class="presence-user-sub">${timeAgo(u.last_seen)}</div>
            </div>
          </div>
        `;
      });
    }

    html += `</div>`;
    panel.innerHTML = html;

    // Bind events
    const settingsBtn = document.getElementById('presence-settings-btn');
    const settingsEl  = document.getElementById('presence-settings');
    const statusSel   = document.getElementById('presence-status-select');
    const showToggle  = document.getElementById('presence-show-toggle');

    settingsBtn?.addEventListener('click', () => {
      settingsOpen = !settingsOpen;
      settingsEl.classList.toggle('open', settingsOpen);
    });

    statusSel?.addEventListener('change', async (e) => {
      try {
        await updateStatus({ status: e.target.value });
      } catch (err) {
        console.error('presence updateStatus:', err);
      }
    });

    showToggle?.addEventListener('change', async (e) => {
      try {
        await updateStatus({ show_online: e.target.checked });
      } catch (err) {
        console.error('presence show_online:', err);
      }
    });

    // Click user → mở profile
    panel.querySelectorAll('.presence-user').forEach((el) => {
      el.addEventListener('click', () => {
        const uid = el.dataset.userId;
        const u = [...online, ...offline].find((x) => x.id === uid);
        if (u?.github_username) {
          window.open('/author.html?u=' + encodeURIComponent(u.github_username), '_blank');
        } else if (u?.id) {
          window.open('/user.html?id=' + encodeURIComponent(u.id), '_blank');
        }
      });
    });
  }

  function updateToggleCount(onlineCount) {
    const countEl = document.getElementById('presence-toggle-count');
    if (countEl) countEl.textContent = onlineCount;
  }

  // ============================================================
  // INJECT WIDGET
  // ============================================================
  function injectWidget() {
    if (document.getElementById('presence-widget')) return;

    const wrap = document.createElement('div');
    wrap.className = 'presence-widget';
    wrap.id = 'presence-widget';
    wrap.innerHTML = `
      <div class="presence-panel" id="presence-panel"></div>
      <button class="presence-toggle" id="presence-toggle-btn">
        <span class="presence-dot"></span>
        <span><span id="presence-toggle-count">0</span> online</span>
      </button>
    `;
    document.body.appendChild(wrap);

    document.getElementById('presence-toggle-btn').addEventListener('click', () => {
      panelOpen = !panelOpen;
      document.getElementById('presence-panel').classList.toggle('open', panelOpen);
      if (panelOpen) refreshData();
    });
  }

  // ============================================================
  // REFRESH DATA
  // ============================================================
  let meCache = { status: 'online', show_online: true };

  async function refreshData() {
    try {
      const [list, me] = await Promise.all([fetchList(), fetchMe()]);
      meCache = me;
      renderPanel(list, me);
      updateToggleCount(list.online_count || 0);
    } catch (err) {
      if (err.message === 'UNAUTHORIZED' || err.message === 'NO_TOKEN') {
        // Không login → ẩn widget
        const w = document.getElementById('presence-widget');
        if (w) w.style.display = 'none';
        return;
      }
      console.error('presence refreshData:', err);
    }
  }

  // ============================================================
  // INIT
  // ============================================================
  async function init() {
    if (!isLoggedIn()) return;   // Chỉ chạy khi đã login

    injectStyles();
    injectWidget();

    // Ping lần đầu
    try {
      await ping();
    } catch (err) {
      console.warn('presence ping first time:', err.message);
    }

    // Heartbeat mỗi 30s
    setInterval(async () => {
      try { await ping(); } catch (_) {}
    }, HEARTBEAT_MS);

    // Refresh list mỗi 20s
    setInterval(refreshData, REFRESH_MS);

    // Lần đầu load list sau 1s
    setTimeout(refreshData, 1000);

    // Khi rời trang → báo offline
    window.addEventListener('beforeunload', () => {
      try {
        const token = getToken();
        if (!token) return;
        const blob = new Blob([], { type: 'application/json' });
        // sendBeacon không set được header → dùng fetch keepalive
        fetch(API_BASE + '/api/presence/offline', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + token },
          keepalive: true,
        }).catch(() => {});
      } catch (_) {}
    });

    console.log('✅ Presence widget loaded');
  }

  // Chạy sau khi DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();