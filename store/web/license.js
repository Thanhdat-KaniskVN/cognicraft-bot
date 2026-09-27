/**
 * License UI - Hien thi licenses cua user tren dashboard
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

  async function loadLicenses() {
    var token = getToken();
    var container = document.getElementById('licenses-container');
    if (!container) return;

    if (!token) {
      container.innerHTML = '<p style="color:#888;text-align:center;padding:20px;">Dang nhap de xem licenses</p>';
      return;
    }

    try {
      var res = await fetch(API_BASE + '/api/license/me', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      renderLicenses(container, data.licenses || []);
    } catch (e) {
      console.warn('loadLicenses:', e);
      container.innerHTML = '<p style="color:#dc2626;text-align:center;padding:20px;">Khong tai duoc licenses</p>';
    }
  }

  function renderLicenses(container, licenses) {
    if (!licenses.length) {
      container.innerHTML = '<div style="text-align:center;padding:30px;color:#888;">' +
        '<div style="font-size:48px;margin-bottom:10px;">\uD83D\uDD11</div>' +
        '<p>Chua co license nao</p>' +
        '<p style="font-size:13px;">Mua theme tra phi de nhan license key</p>' +
        '</div>';
      return;
    }

    var html = '';
    for (var i = 0; i < licenses.length; i++) {
      var l = licenses[i];
      var icon = l.theme_icon || '\uD83C\uDFA8';
      var name = escapeHtml(l.theme_name || l.theme_slug);
      var statusColor = l.status === 'active' ? '#16a34a' : '#dc2626';
      var applied = l.applied_count || 0;
      var key = escapeHtml(l.license_key);

      html += '<div style="background:rgba(20,20,40,0.6);border:1px solid #333;border-radius:10px;padding:15px;margin-bottom:10px;">' +
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;">' +
          '<div style="flex:1;min-width:200px;">' +
            '<div style="color:#0ff;font-weight:bold;font-size:15px;margin-bottom:5px;">' + icon + ' ' + name + '</div>' +
            '<div class="lic-key" style="font-family:Courier New,monospace;color:#fbbf24;font-size:13px;background:rgba(0,0,0,0.4);padding:6px 10px;border-radius:6px;display:inline-block;cursor:pointer;" ' +
                 'data-key="' + key + '" title="Click de copy">\uD83D\uDD11 ' + key + '</div>' +
          '</div>' +
          '<div style="text-align:right;font-size:12px;color:#888;">' +
            '<div style="color:' + statusColor + ';font-weight:bold;text-transform:uppercase;">' + l.status + '</div>' +
            '<div style="margin-top:4px;">Applied: ' + applied + '</div>' +
          '</div>' +
        '</div>' +
      '</div>';
    }
    container.innerHTML = html;

    // Attach copy handler
    var keys = container.querySelectorAll('.lic-key');
    keys.forEach(function(el) {
      el.addEventListener('click', function() {
        var k = el.getAttribute('data-key');
        navigator.clipboard.writeText(k).then(function() {
          var orig = el.style.background;
          el.style.background = 'rgba(22,163,74,0.3)';
          setTimeout(function() { el.style.background = orig || 'rgba(0,0,0,0.4)'; }, 800);
        });
      });
    });
  }

  // MutationObserver - doi container xuat hien roi load
  function tryLoad() {
    var el = document.getElementById('licenses-container');
    if (el && el.innerHTML.indexOf('Đang tải') !== -1) {
      loadLicenses();
      return true;
    }
    return false;
  }

  var observer = new MutationObserver(function() {
    if (tryLoad()) observer.disconnect();
  });

  function startWatch() {
    // Thu ngay lan dau
    if (tryLoad()) return;
    // Neu chua co, watch body
    observer.observe(document.body, { childList: true, subtree: true });
    // Timeout 15s
    setTimeout(function() { observer.disconnect(); }, 15000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startWatch);
  } else {
    startWatch();
  }

  window.loadLicenses = loadLicenses;
  window.tryLoadLicenses = tryLoad;
})();
