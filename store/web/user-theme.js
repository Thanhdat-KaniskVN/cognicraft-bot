// store/web/user-theme.js
/**
 * Auto-load user custom theme
 * - Chạy trên mọi page (sau khi login)
 * - Fetch CSS từ /api/theme/me → inject vào <style id="user-theme">
 * - Không ảnh hưởng user khác
 */
(function () {
  'use strict';

  const API_BASE =
    window.COGNI_API_BASE ||
    (window.location.hostname === 'localhost'
      ? 'http://localhost:8001'
      : 'https://web-production-8b760.up.railway.app');

  function getToken() {
    return (
      localStorage.getItem('cognicraft_token') ||
      localStorage.getItem('token') ||
      localStorage.getItem('cogni_token') ||
      null
    );
  }

  async function loadTheme() {
    const token = getToken();
    if (!token) return;

    try {
      const res = await fetch(API_BASE + '/api/theme/me', {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (!res.ok) return;

      const data = await res.json();

      // Xóa style cũ (nếu có)
      const old = document.getElementById('user-theme');
      if (old) old.remove();

      // Nếu không có theme hoặc inactive → không inject
      if (!data.css_content || !data.is_active) {
        console.log('🎨 User theme: none active');
        return;
      }

      // Inject CSS
      const style = document.createElement('style');
      style.id = 'user-theme';
      style.textContent = data.css_content;
      document.head.appendChild(style);

      console.log('🎨 User theme loaded:', data.css_content.length, 'chars');
    } catch (err) {
      console.warn('User theme load failed:', err);
    }
  }

  // Hàm public để page khác trigger reload sau khi save
  window.reloadUserTheme = loadTheme;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadTheme);
  } else {
    loadTheme();
  }
})();