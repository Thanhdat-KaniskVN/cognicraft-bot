/**
 * Moderation panel - Duyet theme/plugin
 */
(function() {
  var API_BASE = (window.CONFIG && window.CONFIG.API_BASE) ||
    (location.hostname === 'localhost' || location.hostname === '127.0.0.1'
      ? 'http://localhost:8001'
      : 'https://web-production-8b760.up.railway.app');

  function getToken() {
    return localStorage.getItem('cognicraft_token') || '';
  }

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, function(c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function toast(msg, type) {
    type = type || 'info';
    var el = document.createElement('div');
    el.className = 'mod-toast mod-toast-' + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function() { el.classList.add('show'); }, 10);
    setTimeout(function() {
      el.classList.remove('show');
      setTimeout(function() { el.remove(); }, 300);
    }, 3000);
  }

  async function loadQueue() {
    var container = document.getElementById('queue-list');
    if (!container) return;
    container.innerHTML = '<div class="mod-loading">Đang tải...</div>';

    try {
      var res = await fetch(API_BASE + '/api/admin/moderation/queue', {
        headers: { 'Authorization': 'Bearer ' + getToken() },
      });
      if (res.status === 401 || res.status === 403) {
        container.innerHTML = '<div class="mod-empty">🚫 Không có quyền admin</div>';
        return;
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      renderQueue(container, data.items || []);
      document.getElementById('queue-count').textContent = data.count || 0;
    } catch (e) {
      console.warn('loadQueue:', e);
      container.innerHTML = '<div class="mod-empty">❌ Lỗi tải: ' + escapeHtml(e.message) + '</div>';
    }
  }

  function renderQueue(container, items) {
    if (!items.length) {
      container.innerHTML = '<div class="mod-empty">✅ Không có item nào chờ duyệt</div>';
      return;
    }
    var html = '';
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      var price = it.is_paid ? (it.price_vnd.toLocaleString('vi-VN') + 'đ') : 'FREE';
      html += '<div class="mod-card">' +
        '<div class="mod-card-header">' +
          '<div class="mod-card-title">' + (it.icon || '🎨') + ' ' + escapeHtml(it.name) + '</div>' +
          '<div class="mod-card-type">' + escapeHtml(it.type || 'theme') + '</div>' +
        '</div>' +
        '<div class="mod-card-meta">' +
          '<span>👤 ' + escapeHtml(it.author || '?') + '</span>' +
          '<span>💰 ' + price + '</span>' +
          '<span>🏷️ ' + escapeHtml((it.tags || []).join(', ') || 'no tags') + '</span>' +
        '</div>' +
        '<div class="mod-card-desc">' + escapeHtml(it.description || '') + '</div>' +
        '<div class="mod-card-actions">' +
          '<button class="mod-btn mod-btn-approve" data-slug="' + escapeHtml(it.slug) + '">✅ Duyệt</button>' +
          '<button class="mod-btn mod-btn-changes" data-slug="' + escapeHtml(it.slug) + '">✏️ Yêu cầu sửa</button>' +
          '<button class="mod-btn mod-btn-reject" data-slug="' + escapeHtml(it.slug) + '">❌ Từ chối</button>' +
        '</div>' +
      '</div>';
    }
    container.innerHTML = html;

    container.querySelectorAll('.mod-btn-approve').forEach(function(b) {
      b.addEventListener('click', function() { approve(b.dataset.slug); });
    });
    container.querySelectorAll('.mod-btn-reject').forEach(function(b) {
      b.addEventListener('click', function() { reject(b.dataset.slug); });
    });
    container.querySelectorAll('.mod-btn-changes').forEach(function(b) {
      b.addEventListener('click', function() { requestChanges(b.dataset.slug); });
    });
  }

  async function approve(slug) {
    if (!confirm('Duyệt ' + slug + '?')) return;
    try {
      var res = await fetch(API_BASE + '/api/admin/moderation/' + slug + '/approve', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + getToken() },
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      toast('✅ Đã duyệt ' + slug, 'success');
      loadQueue();
    } catch (e) {
      toast('❌ Lỗi: ' + e.message, 'error');
    }
  }

  async function reject(slug) {
    var note = prompt('Lý do từ chối (bắt buộc):');
    if (!note || !note.trim()) return;
    try {
      var res = await fetch(API_BASE + '/api/admin/moderation/' + slug + '/reject', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + getToken(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ note: note.trim() }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      toast('❌ Đã từ chối ' + slug, 'success');
      loadQueue();
    } catch (e) {
      toast('❌ Lỗi: ' + e.message, 'error');
    }
  }

  async function requestChanges(slug) {
    var note = prompt('Ghi chú yêu cầu sửa (bắt buộc):');
    if (!note || !note.trim()) return;
    try {
      var res = await fetch(API_BASE + '/api/admin/moderation/' + slug + '/request-changes', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + getToken(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ note: note.trim() }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      toast('✏️ Đã yêu cầu sửa ' + slug, 'success');
      loadQueue();
    } catch (e) {
      toast('❌ Lỗi: ' + e.message, 'error');
    }
  }

  async function loadHistory() {
    var container = document.getElementById('history-list');
    if (!container) return;
    try {
      var res = await fetch(API_BASE + '/api/admin/moderation/history', {
        headers: { 'Authorization': 'Bearer ' + getToken() },
      });
      if (!res.ok) return;
      var data = await res.json();
      var html = '';
      (data.items || []).forEach(function(it) {
        var statusColor = it.moderation_status === 'approved' ? '#16a34a' :
                          it.moderation_status === 'rejected' ? '#dc2626' : '#fbbf24';
        html += '<div class="mod-history-row">' +
          '<span style="color:' + statusColor + ';font-weight:bold;">' + it.moderation_status.toUpperCase() + '</span>' +
          ' <b>' + escapeHtml(it.name) + '</b>' +
          ' <small style="color:#888;">' + escapeHtml(it.moderated_at || '') + '</small>' +
        '</div>';
      });
      container.innerHTML = html || '<div class="mod-empty">Chưa có lịch sử</div>';
    } catch (e) {
      console.warn('loadHistory:', e);
    }
  }

  window.loadQueue = loadQueue;
  window.loadHistory = loadHistory;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      loadQueue();
      loadHistory();
    });
  } else {
    loadQueue();
    loadHistory();
  }
})();