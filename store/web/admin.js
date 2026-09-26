// store/web/admin.js
/**
 * CogniCraft Admin Panel + Analytics
 */
(function () {
  'use strict';

  const API_BASE =
    window.COGNI_API_BASE ||
    (location.hostname === 'localhost'
      ? 'http://localhost:8001'
      : 'https://web-production-8b760.up.railway.app');

  const getToken = () =>
    localStorage.getItem('cognicraft_token') ||
    localStorage.getItem('token') ||
    localStorage.getItem('cogni_token') ||
    '';

  // ============================================================
  // HELPERS
  // ============================================================
  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function fmtNum(n) {
    n = n || 0;
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }

  function fmtPrice(vnd) {
    if (!vnd || vnd <= 0) return '0 đ';
    if (vnd >= 1000000) return (vnd / 1000000).toFixed(1) + 'M đ';
    if (vnd >= 1000) return (vnd / 1000).toFixed(0) + 'K đ';
    return vnd + ' đ';
  }

  function toast(msg, type = 'success') {
    const el = document.getElementById('admin-toast');
    el.textContent = msg;
    el.className = 'admin-toast ' + type + ' show';
    setTimeout(() => el.classList.remove('show'), 3000);
  }

  async function api(path, options = {}) {
    const res = await fetch(API_BASE + path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + getToken(),
        ...(options.headers || {}),
      },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'HTTP ' + res.status);
    return data;
  }

  // ============================================================
  // INIT — VERIFY ADMIN
  // ============================================================
  async function init() {
    if (!getToken()) {
      showAccessDenied();
      return;
    }

    try {
      const me = await api('/api/admin/me');
      document.getElementById('admin-name').textContent = me.name || 'Admin';

      try {
        const userMe = await api('/api/auth/me');
        if (userMe.avatar_url) {
          document.getElementById('admin-avatar').src = userMe.avatar_url;
        }
      } catch (_) {}

      document.getElementById('admin-root').style.display = 'grid';
      document.getElementById('access-denied').style.display = 'none';

      loadOverview();
      setupNav();
      setupListeners();

    } catch (e) {
      console.error('Admin verify failed:', e);
      showAccessDenied();
    }
  }

  function showAccessDenied() {
    document.getElementById('admin-root').style.display = 'none';
    document.getElementById('access-denied').style.display = 'flex';
  }

  // ============================================================
  // NAV
  // ============================================================
  function setupNav() {
    document.querySelectorAll('.admin-nav-item[data-section]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const section = btn.dataset.section;
        switchSection(section);
      });
    });
  }

  const sectionTitles = {
    overview: '📊 Tổng quan',
    analytics: '📈 Analytics',
    users: '👥 Users',
    themes: '🎨 Themes / Plugins',
    reports: '🚨 Reports',
    orders: '💰 Orders',
  };

  function switchSection(section) {
    document.querySelectorAll('.admin-nav-item').forEach((b) => b.classList.remove('active'));
    document.querySelector(`[data-section="${section}"]`)?.classList.add('active');

    document.querySelectorAll('.admin-section').forEach((s) => s.classList.remove('active'));
    document.getElementById('section-' + section)?.classList.add('active');

    document.getElementById('section-title').textContent = sectionTitles[section] || section;

    if (section === 'users') loadUsers();
    else if (section === 'themes') loadThemes();
    else if (section === 'reports') loadReports();
    else if (section === 'overview') loadOverview();
    else if (section === 'analytics') loadAnalytics();
  }

  // ============================================================
  // LISTENERS
  // ============================================================
  function setupListeners() {
    let uT;
    document.getElementById('users-search').addEventListener('input', () => {
      clearTimeout(uT);
      uT = setTimeout(loadUsers, 400);
    });
    document.getElementById('users-filter').addEventListener('change', loadUsers);

    let tT;
    document.getElementById('themes-search').addEventListener('input', () => {
      clearTimeout(tT);
      tT = setTimeout(loadThemes, 400);
    });
    document.getElementById('themes-filter').addEventListener('change', loadThemes);

    document.getElementById('reports-filter').addEventListener('change', loadReports);

    const analyticsDays = document.getElementById('analytics-days');
    if (analyticsDays) analyticsDays.addEventListener('change', loadAnalytics);
  }

  // ============================================================
  // OVERVIEW
  // ============================================================
  async function loadOverview() {
    const grid = document.getElementById('stats-grid');
    if (!grid) return;
    grid.innerHTML = '<div class="admin-loading"><div class="admin-spinner"></div></div>';

    try {
      const s = await api('/api/admin/stats');

      const stats = [
        { label: 'USERS', value: fmtNum(s.users), sub: `+${s.recent_users} tuần này`, icon: '👥' },
        { label: 'PLUGINS', value: fmtNum(s.plugins), sub: 'Đã publish', icon: '📦' },
        { label: 'THEMES', value: fmtNum(s.themes), sub: 'Đã publish', icon: '🎨' },
        { label: 'PENDING REPORTS', value: fmtNum(s.pending_reports), sub: 'Cần xử lý', icon: '🚨' },
        { label: 'ORDERS', value: fmtNum(s.orders), sub: 'Tổng đơn', icon: '📝' },
        { label: 'REVENUE', value: fmtPrice(s.revenue_vnd), sub: 'Đã thanh toán', icon: '💰' },
      ];

      grid.innerHTML = stats.map((st) => `
        <div class="stat-card">
          <div class="stat-label">${st.icon} ${st.label}</div>
          <div class="stat-value">${st.value}</div>
          <div class="stat-sub">${st.sub}</div>
        </div>
      `).join('');

      const badge = document.getElementById('reports-badge');
      if (s.pending_reports > 0) {
        badge.textContent = s.pending_reports;
        badge.style.display = 'inline-block';
      } else {
        badge.style.display = 'none';
      }

    } catch (e) {
      grid.innerHTML = `<div class="admin-empty">❌ Lỗi: ${esc(e.message)}</div>`;
    }
  }

  // ============================================================
  // 📈 ANALYTICS
  // ============================================================
  async function loadAnalytics() {
    const kpisEl = document.getElementById('analytics-kpis');
    if (!kpisEl) return;

    kpisEl.innerHTML = '<div class="admin-loading"><div class="admin-spinner"></div></div>';

    try {
      const [overview, top] = await Promise.all([
        api('/api/admin/analytics/overview'),
        api('/api/admin/analytics/top?limit=10'),
      ]);

      const days = parseInt(document.getElementById('analytics-days').value) || 30;
      const timelineData = await api('/api/admin/analytics/timeline?days=' + days);

      const growthVal = overview.users.growth_7d_pct || 0;
      const growthSign = growthVal >= 0 ? 'up' : 'down';
      const growthIcon = growthVal >= 0 ? '↑' : '↓';

      kpisEl.innerHTML = `
        <div class="kpi-card">
          <div class="kpi-label">👥 TOTAL USERS</div>
          <div class="kpi-value">${fmtNum(overview.users.total)}</div>
          <div class="kpi-sub ${growthSign}">
            ${growthIcon} ${Math.abs(growthVal)}% so với tuần trước
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">📦 CONTENT</div>
          <div class="kpi-value">${fmtNum(overview.content.themes + overview.content.plugins)}</div>
          <div class="kpi-sub">${overview.content.themes} themes · ${overview.content.plugins} plugins</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">⬇️ DOWNLOADS</div>
          <div class="kpi-value">${fmtNum(overview.engagement.downloads)}</div>
          <div class="kpi-sub">${fmtNum(overview.engagement.likes)} likes · ${overview.engagement.reviews} reviews</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">💰 REVENUE</div>
          <div class="kpi-value">${fmtPrice(overview.revenue.total_vnd)}</div>
          <div class="kpi-sub">${overview.revenue.pending_orders} orders đang chờ</div>
        </div>
      `;

            // Delay 100ms cho layout settle trước khi vẽ chart
      setTimeout(() => {
        drawTimelineChart(timelineData.timeline);
        drawRevenueChart(timelineData.timeline);
      }, 100);

      renderTopThemes(top.top_themes);
      renderTopAuthors(top.top_authors);
      renderTopTags(top.top_tags);

    } catch (e) {
      console.error('Analytics error:', e);
      kpisEl.innerHTML = `<div class="admin-empty">❌ Lỗi: ${esc(e.message)}</div>`;
    }
  }

  // ============================================================
  // 📈 TIMELINE CHART — 3 lines
  // ============================================================
  function drawTimelineChart(timeline) {
    const canvas = document.getElementById('timeline-chart');
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth || 800;
    const H = 240;

    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.height = H + 'px';

    const ctx = canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);

    ctx.fillStyle = '#0a0118';
    ctx.fillRect(0, 0, W, H);

    if (!timeline || timeline.length === 0) {
      ctx.fillStyle = '#a78bfa';
      ctx.font = '14px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('Chưa có dữ liệu', W / 2, H / 2);
      return;
    }

    const padL = 40, padR = 20, padT = 20, padB = 30;
    const chartW = W - padL - padR;
    const chartH = H - padT - padB;

    let maxVal = 1;
    timeline.forEach((d) => {
      maxVal = Math.max(maxVal, d.users || 0, d.themes || 0, d.plugins || 0);
    });

    ctx.strokeStyle = 'rgba(168, 85, 247, 0.15)';
    ctx.lineWidth = 1;
    const gridLines = 4;
    for (let i = 0; i <= gridLines; i++) {
      const y = padT + (chartH / gridLines) * i;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(W - padR, y);
      ctx.stroke();

      const val = Math.round(maxVal - (maxVal / gridLines) * i);
      ctx.fillStyle = '#6d28d9';
      ctx.font = '10px system-ui';
      ctx.textAlign = 'right';
      ctx.fillText(val, padL - 6, y + 3);
    }

    const series = [
      { key: 'users',   color: '#22c55e' },
      { key: 'themes',  color: '#06b6d4' },
      { key: 'plugins', color: '#a855f7' },
    ];

    series.forEach((s) => {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.shadowColor = s.color;
      ctx.shadowBlur = 6;
      ctx.beginPath();

      timeline.forEach((d, i) => {
        const x = padL + (chartW / Math.max(1, timeline.length - 1)) * i;
        const val = d[s.key] || 0;
        const y = padT + chartH - (val / maxVal) * chartH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.shadowBlur = 0;
    });

    ctx.fillStyle = '#6d28d9';
    ctx.font = '10px system-ui';
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(timeline.length / 6));
    timeline.forEach((d, i) => {
      if (i % step === 0 || i === timeline.length - 1) {
        const x = padL + (chartW / Math.max(1, timeline.length - 1)) * i;
        ctx.fillText(d.date.slice(5), x, H - 10);
      }
    });
  }

  // ============================================================
  // 💰 REVENUE CHART — bars
  // ============================================================
  function drawRevenueChart(timeline) {
    const canvas = document.getElementById('revenue-chart');
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth || 800;
    const H = 200;

    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.height = H + 'px';

    const ctx = canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);

    ctx.fillStyle = '#0a0118';
    ctx.fillRect(0, 0, W, H);

    if (!timeline || timeline.length === 0) return;

    const padL = 60, padR = 20, padT = 20, padB = 30;
    const chartW = W - padL - padR;
    const chartH = H - padT - padB;

    let maxRev = 0;
    timeline.forEach((d) => { maxRev = Math.max(maxRev, d.revenue || 0); });

    if (maxRev === 0) {
      ctx.fillStyle = '#6d28d9';
      ctx.font = '13px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('Chưa có doanh thu', W / 2, H / 2);
      return;
    }

    const barW = Math.max(2, chartW / timeline.length - 2);

    timeline.forEach((d, i) => {
      const rev = d.revenue || 0;
      if (rev === 0) return;
      const x = padL + (chartW / timeline.length) * i + 1;
      const barH = (rev / maxRev) * chartH;
      const y = padT + chartH - barH;

      const grd = ctx.createLinearGradient(0, y, 0, padT + chartH);
      grd.addColorStop(0, '#fbbf24');
      grd.addColorStop(1, '#f59e0b');
      ctx.fillStyle = grd;
      ctx.fillRect(x, y, barW, barH);
    });

    ctx.fillStyle = '#6d28d9';
    ctx.font = '10px system-ui';
    ctx.textAlign = 'right';
    ctx.fillText(fmtPrice(maxRev), padL - 6, padT + 10);
    ctx.fillText('0 đ', padL - 6, padT + chartH);
  }

  // ============================================================
  // TOP LISTS
  // ============================================================
  function renderTopThemes(themes) {
    const el = document.getElementById('top-themes-list');
    if (!el) return;

    if (!themes || themes.length === 0) {
      el.innerHTML = '<div class="admin-empty" style="padding:1rem;">Chưa có theme</div>';
      return;
    }

    el.innerHTML = themes.map((t, i) => {
      const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : '';
      return `
        <div class="rank-item">
          <div class="rank-num ${rankClass}">${i + 1}</div>
          <div class="rank-info">
            <div class="rank-name">${esc(t.name)}</div>
            <div class="rank-sub">${esc(t.author)} · ⭐ ${(t.rating || 0).toFixed(1)}</div>
          </div>
          <div class="rank-value">⬇ ${fmtNum(t.downloads)}</div>
        </div>
      `;
    }).join('');
  }

  function renderTopAuthors(authors) {
    const el = document.getElementById('top-authors-list');
    if (!el) return;

    if (!authors || authors.length === 0) {
      el.innerHTML = '<div class="admin-empty" style="padding:1rem;">Chưa có author</div>';
      return;
    }

    el.innerHTML = authors.map((a, i) => {
      const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : '';
      return `
        <div class="rank-item">
          <div class="rank-num ${rankClass}">${i + 1}</div>
          <div class="rank-info">
            <div class="rank-name">${esc(a.author || 'Anonymous')}</div>
            <div class="rank-sub">${a.item_count} items · ❤ ${fmtNum(a.total_likes)}</div>
          </div>
          <div class="rank-value">⬇ ${fmtNum(a.total_downloads)}</div>
        </div>
      `;
    }).join('');
  }

  function renderTopTags(tags) {
    const el = document.getElementById('top-tags-list');
    if (!el) return;

    if (!tags || tags.length === 0) {
      el.innerHTML = '<div class="admin-empty" style="padding:1rem;">Chưa có tag</div>';
      return;
    }

    const maxCount = Math.max(...tags.map((t) => t.count));

    el.innerHTML = tags.slice(0, 8).map((t) => {
      const pct = (t.count / maxCount) * 100;
      return `
        <div class="tag-bar">
          <div class="tag-name">#${esc(t.tag)}</div>
          <div class="tag-fill">
            <div class="tag-fill-inner" style="width:${pct}%"></div>
          </div>
          <div class="tag-count">${t.count}</div>
        </div>
      `;
    }).join('');
  }

  // ============================================================
  // USERS
  // ============================================================
  async function loadUsers() {
    const wrap = document.getElementById('users-table');
    wrap.innerHTML = '<div class="admin-loading"><div class="admin-spinner"></div></div>';

    const search = document.getElementById('users-search').value.trim();
    const filter = document.getElementById('users-filter').value;

    const p = new URLSearchParams();
    if (search) p.set('search', search);
    if (filter) p.set('filter', filter);

    try {
      const data = await api('/api/admin/users?' + p.toString());

      if (!data.users || data.users.length === 0) {
        wrap.innerHTML = `<div class="admin-empty">Không có user nào</div>`;
        return;
      }

      wrap.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>GitHub</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${data.users.map((u) => `
              <tr>
                <td>
                  <div class="user-cell">
                    <img src="${esc(u.avatar_url || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + u.id)}" alt="">
                    <div>
                      <div class="name">${esc(u.name || 'Anonymous')}</div>
                      <div class="email">${esc(u.email || '')}</div>
                    </div>
                  </div>
                </td>
                <td>${u.github_username ? '@' + esc(u.github_username) : '<span style="color:var(--dim)">—</span>'}</td>
                <td>
                  ${u.is_admin ? '<span class="tag-pill admin">👑 ADMIN</span>' : ''}
                  ${u.banned ? '<span class="tag-pill banned">🚫 BANNED</span>' : ''}
                  ${!u.is_admin && !u.banned ? '<span class="tag-pill active">✅ ACTIVE</span>' : ''}
                </td>
                <td style="color:var(--dim);font-size:0.75rem;">${u.created_at ? new Date(u.created_at).toLocaleDateString('vi-VN') : '—'}</td>
                <td>
                  ${u.banned 
                    ? `<button class="action-btn success" onclick="adminUnban('${u.id}')">✅ Unban</button>`
                    : `<button class="action-btn danger" onclick="adminBan('${u.id}')">🚫 Ban</button>`
                  }
                  <button class="action-btn warn" onclick="adminToggle('${u.id}')">
                    ${u.is_admin ? '👤 Bỏ admin' : '👑 Set admin'}
                  </button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

    } catch (e) {
      wrap.innerHTML = `<div class="admin-empty">❌ Lỗi: ${esc(e.message)}</div>`;
    }
  }

  window.adminBan = async function (userId) {
    const reason = prompt('Lý do ban?', 'Vi phạm điều khoản');
    if (!reason) return;
    try {
      await api('/api/admin/users/' + userId + '/ban', {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      toast('🚫 Đã ban user', 'success');
      loadUsers();
    } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
  };

  window.adminUnban = async function (userId) {
    if (!confirm('Unban user này?')) return;
    try {
      await api('/api/admin/users/' + userId + '/unban', { method: 'POST' });
      toast('✅ Đã unban', 'success');
      loadUsers();
    } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
  };

  window.adminToggle = async function (userId) {
    if (!confirm('Đổi quyền admin cho user này?')) return;
    try {
      const r = await api('/api/admin/users/' + userId + '/toggle-admin', { method: 'POST' });
      toast(r.is_admin ? '👑 Đã set admin' : '👤 Đã bỏ admin', 'success');
      loadUsers();
    } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
  };

  // ============================================================
  // THEMES / PLUGINS
  // ============================================================
  async function loadThemes() {
    const wrap = document.getElementById('themes-table');
    wrap.innerHTML = '<div class="admin-loading"><div class="admin-spinner"></div></div>';

    const search = document.getElementById('themes-search').value.trim();
    const type = document.getElementById('themes-filter').value;

    const p = new URLSearchParams();
    if (search) p.set('search', search);
    if (type) p.set('type', type);

    try {
      const data = await api('/api/admin/themes?' + p.toString());

      if (!data.items || data.items.length === 0) {
        wrap.innerHTML = `<div class="admin-empty">Không có item nào</div>`;
        return;
      }

      wrap.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Author</th>
              <th>Stats</th>
              <th>Price</th>
              <th>Flags</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${data.items.map((t) => `
              <tr>
                <td>
                  <div style="font-weight:700;">${esc(t.name)}</div>
                  <div style="font-size:0.7rem;color:var(--dim);">${esc(t.slug)}</div>
                </td>
                <td>
                  <span class="tag-pill ${t.type}">${t.type === 'theme' ? '🎨 THEME' : '📦 PLUGIN'}</span>
                </td>
                <td>${esc(t.author)}</td>
                <td style="font-size:0.75rem;color:var(--dim);">
                  ⬇ ${fmtNum(t.downloads)} · ⭐ ${t.rating?.toFixed(1) || '0.0'}
                </td>
                <td>${t.is_paid ? '<span class="tag-pill pending">💎 ' + fmtPrice(t.price_vnd) + '</span>' : '<span style="color:var(--green)">FREE</span>'}</td>
                <td>
                  ${t.featured ? '<span class="tag-pill pending">⭐</span>' : ''}
                  ${t.verified ? '<span class="tag-pill active">✓</span>' : ''}
                </td>
                <td>
                  <button class="action-btn warn" onclick="adminFeature('${esc(t.slug)}', ${!t.featured})">
                    ${t.featured ? '★ Unfeature' : '☆ Feature'}
                  </button>
                  <button class="action-btn success" onclick="adminVerify('${esc(t.slug)}', ${!t.verified})">
                    ${t.verified ? '✗ Unverify' : '✓ Verify'}
                  </button>
                  <button class="action-btn danger" onclick="adminDelete('${esc(t.slug)}')">🗑️</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

    } catch (e) {
      wrap.innerHTML = `<div class="admin-empty">❌ Lỗi: ${esc(e.message)}</div>`;
    }
  }

  window.adminFeature = async function (slug, featured) {
    try {
      await api('/api/admin/themes/' + slug + '/feature', {
        method: 'POST',
        body: JSON.stringify({ featured }),
      });
      toast(featured ? '⭐ Đã feature' : '★ Đã bỏ feature', 'success');
      loadThemes();
    } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
  };

  window.adminVerify = async function (slug, verified) {
    try {
      await api('/api/admin/themes/' + slug + '/verify', {
        method: 'POST',
        body: JSON.stringify({ verified }),
      });
      toast(verified ? '✓ Đã verify' : '✗ Đã bỏ verify', 'success');
      loadThemes();
    } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
  };

  window.adminDelete = async function (slug) {
    if (!confirm(`Xóa "${slug}"? Hành động không thể hoàn tác.`)) return;
    try {
      await api('/api/admin/themes/' + slug, { method: 'DELETE' });
      toast('🗑️ Đã xóa', 'success');
      loadThemes();
    } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
  };

  // ============================================================
  // REPORTS
  // ============================================================
  async function loadReports() {
    const wrap = document.getElementById('reports-table');
    wrap.innerHTML = '<div class="admin-loading"><div class="admin-spinner"></div></div>';

    const status = document.getElementById('reports-filter').value;
    const p = new URLSearchParams();
    if (status) p.set('status', status);

    try {
      const data = await api('/api/admin/reports?' + p.toString());

      if (!data.reports || data.reports.length === 0) {
        wrap.innerHTML = `<div class="admin-empty">Không có report nào 🎉</div>`;
        return;
      }

      wrap.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Reporter</th>
              <th>Item</th>
              <th>Reason</th>
              <th>Status</th>
              <th>Time</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${data.reports.map((r) => `
              <tr>
                <td>
                  <div style="font-weight:700;">${esc(r.reporter_name || 'Anonymous')}</div>
                  <div style="font-size:0.7rem;color:var(--dim);">${esc(r.reporter_email || '')}</div>
                </td>
                <td>
                  <div style="font-size:0.7rem;color:var(--dim);">${esc(r.reported_type)}</div>
                  <div style="font-weight:700;">${esc(r.reported_slug)}</div>
                </td>
                <td>
                  <div style="font-weight:700;color:var(--yellow);">${esc(r.reason)}</div>
                  <div style="font-size:0.75rem;color:var(--dim);">${esc(r.description || '')}</div>
                </td>
                <td>
                  <span class="tag-pill ${r.status}">
                    ${r.status === 'pending' ? '⏳ Chờ' : r.status === 'resolved' ? '✅ Đã xử lý' : '❌ Bỏ qua'}
                  </span>
                </td>
                <td style="font-size:0.75rem;color:var(--dim);">${new Date(r.created_at).toLocaleString('vi-VN')}</td>
                <td>
                  ${r.status === 'pending' ? `
                    <button class="action-btn success" onclick="adminResolveReport('${r.id}', 'resolved')">✅ Xử lý</button>
                    <button class="action-btn" onclick="adminResolveReport('${r.id}', 'dismissed')">❌ Bỏ qua</button>
                  ` : '<span style="color:var(--dim);">—</span>'}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

    } catch (e) {
      wrap.innerHTML = `<div class="admin-empty">❌ Lỗi: ${esc(e.message)}</div>`;
    }
  }

  window.adminResolveReport = async function (reportId, status) {
    try {
      await api('/api/admin/reports/' + reportId + '/resolve', {
        method: 'POST',
        body: JSON.stringify({ status }),
      });
      toast(status === 'resolved' ? '✅ Đã xử lý' : '❌ Đã bỏ qua', 'success');
      loadReports();
      loadOverview();
    } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
  };

  // ============================================================
  // INIT
  // ============================================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();