// store/web/admin-button.js
/**
 * Auto-inject Admin button vào navbar
 * Chỉ hiện khi user hiện tại là admin
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

  async function checkAdmin() {
    const token = getToken();
    if (!token) return false;

    try {
      const res = await fetch(API_BASE + '/api/admin/me', {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (!res.ok) return false;
      const data = await res.json();
      return data.is_admin === true;
    } catch (e) {
      return false;
    }
  }

  function injectAdminButton() {
    if (document.getElementById('admin-nav-btn')) return;

    // Tìm nav links — thử nhiều selector
    const navLinks =
      document.querySelector('.mk-nav-links') ||
      document.querySelector('.status-bar') ||
      document.querySelector('.nav-links') ||
      document.querySelector('.header .status-bar');

    if (!navLinks) {
      // Retry sau 500ms nếu chưa có DOM
      setTimeout(injectAdminButton, 500);
      return;
    }

    const btn = document.createElement('a');
    btn.id = 'admin-nav-btn';
    btn.href = 'admin.html';
    btn.innerHTML = '🛡️ Admin';
    btn.style.cssText = `
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 8px 14px;
      margin-left: 8px;
      background: linear-gradient(135deg, rgba(181, 55, 242, 0.2), rgba(236, 72, 153, 0.2));
      border: 1px solid rgba(181, 55, 242, 0.5);
      border-radius: 8px;
      color: #c084fc;
      text-decoration: none;
      font-size: 13px;
      font-weight: 700;
      transition: all 0.2s;
      text-shadow: 0 0 8px rgba(181, 55, 242, 0.5);
    `;

    btn.addEventListener('mouseenter', () => {
      btn.style.background = 'linear-gradient(135deg, rgba(181, 55, 242, 0.4), rgba(236, 72, 153, 0.4))';
      btn.style.color = '#fff';
      btn.style.borderColor = '#c084fc';
      btn.style.boxShadow = '0 0 20px rgba(181, 55, 242, 0.5)';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.background = 'linear-gradient(135deg, rgba(181, 55, 242, 0.2), rgba(236, 72, 153, 0.2))';
      btn.style.color = '#c084fc';
      btn.style.borderColor = 'rgba(181, 55, 242, 0.5)';
      btn.style.boxShadow = 'none';
    });

    navLinks.appendChild(btn);
    console.log('🛡️ Admin button injected');
  }

  async function init() {
    const isAdmin = await checkAdmin();
    if (isAdmin) {
      setTimeout(injectAdminButton, 300);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();