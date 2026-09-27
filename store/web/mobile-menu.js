// store/web/mobile-menu.js
/**
 * CogniCraft Mobile Menu
 * - Hamburger button tự động inject
 * - Drawer slide từ phải (như DOL)
 * - Auto float-in card animation
 */
(function () {
  'use strict';

  const isMobile = () => window.innerWidth <= 768;

  // ============================================================
  // CONFIG
  // ============================================================
  const MENU_ITEMS = [
    { href: 'index.html',        icon: '🏪', label: 'Store',        badge: null },
    { href: 'marketplace.html',  icon: '🎨', label: 'Marketplace',  badge: 'themes' },
    { href: 'upload.html',       icon: '📤', label: 'Publish',      badge: null },
    { href: 'theme-editor.html', icon: '🖌️', label: 'Theme Editor', badge: null },
    { href: 'dashboard.html',    icon: '📊', label: 'Dashboard',    badge: null },
    { href: 'settings.html',     icon: '⚙️', label: 'Settings',     badge: null },
  ];

  const currentPage = location.pathname.split('/').pop() || 'index.html';

  // ============================================================
  // TOKEN / USER HELPERS
  // ============================================================
  function getToken() {
    return localStorage.getItem('cognicraft_token') ||
           localStorage.getItem('token') ||
           localStorage.getItem('cogni_token') || '';
  }

  function getUserInfo() {
    try {
      const token = getToken();
      if (!token) return null;
      const payload = JSON.parse(atob(token.split('.')[1]));
      return {
        name: payload.name || 'User',
        email: payload.email || '',
      };
    } catch {
      return null;
    }
  }

  // ============================================================
  // HAMBURGER BUTTON
  // ============================================================
  function injectHamburger() {
    if (document.getElementById('mobile-hamburger')) return;

    const btn = document.createElement('button');
    btn.id = 'mobile-hamburger';
    btn.className = 'mobile-hamburger';
    btn.setAttribute('aria-label', 'Menu');
    btn.innerHTML = '<span></span><span></span><span></span>';
    btn.onclick = openDrawer;

    document.body.appendChild(btn);
  }

  // ============================================================
  // DRAWER
  // ============================================================
  function injectDrawer() {
    if (document.getElementById('mobile-drawer')) return;

    const user = getUserInfo();
    const userName = user?.name || 'Khách';
    const userEmail = user?.email || 'Chưa đăng nhập';

    const drawer = document.createElement('div');
    drawer.id = 'mobile-drawer';
    drawer.className = 'mobile-drawer';
    drawer.innerHTML = `
      <div class="mobile-drawer-backdrop" onclick="closeDrawer()"></div>
      <aside class="mobile-drawer-panel">
        <button class="mobile-drawer-close" onclick="closeDrawer()" aria-label="Đóng">✕</button>

        <div class="mobile-drawer-user">
          <div class="mobile-drawer-avatar">${user ? '👤' : '👤'}</div>
          <div class="mobile-drawer-userinfo">
            <div class="mobile-drawer-username">${userName}</div>
            <div class="mobile-drawer-email">${userEmail}</div>
          </div>
        </div>

        <nav class="mobile-drawer-nav">
          ${MENU_ITEMS.map(item => `
            <a href="${item.href}"
               class="mobile-drawer-item ${currentPage === item.href ? 'active' : ''}"
               data-nav-href="${item.href}">
              <span class="mobile-drawer-icon">${item.icon}</span>
              <span class="mobile-drawer-label">${item.label}</span>
              ${item.badge === 'themes' ? '<span class="mobile-drawer-badge" id="mobile-theme-count">0</span>' : ''}
            </a>
          `).join('')}
        </nav>

        <div class="mobile-drawer-footer">
          ${user ? `
            <button class="mobile-drawer-item mobile-drawer-logout" onclick="mobileLogout()">
              <span class="mobile-drawer-icon">🚪</span>
              <span class="mobile-drawer-label">Đăng xuất</span>
            </button>
          ` : `
            <a href="index.html" class="mobile-drawer-item mobile-drawer-login">
              <span class="mobile-drawer-icon">🔑</span>
              <span class="mobile-drawer-label">Đăng nhập</span>
            </a>
          `}
        </div>
      </aside>
    `;

    document.body.appendChild(drawer);
    updateThemeBadge();
  }

  // ============================================================
  // UPDATE THEME BADGE
  // ============================================================
  async function updateThemeBadge() {
    try {
      const API_BASE = window.COGNI_API_BASE ||
        (location.hostname === 'localhost'
          ? 'http://localhost:8001'
          : 'https://web-production-8b760.up.railway.app');

      const res = await fetch(API_BASE + '/api/marketplace/themes?per_page=1');
      const data = await res.json();

      const badge = document.getElementById('mobile-theme-count');
      if (badge) badge.textContent = data.total || 0;
    } catch (_) {}
  }

  // ============================================================
  // OPEN / CLOSE
  // ============================================================
  window.openDrawer = function () {
    const drawer = document.getElementById('mobile-drawer');
    if (drawer) {
      drawer.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
  };

  window.closeDrawer = function () {
    const drawer = document.getElementById('mobile-drawer');
    if (drawer) {
      drawer.classList.remove('open');
      document.body.style.overflow = '';
    }
  };

  window.mobileLogout = function () {
    if (!confirm('Đăng xuất khỏi CogniCraft?')) return;

    ['cognicraft_token', 'token', 'cogni_token', 'cognicraft_author_name'].forEach((k) => {
      localStorage.removeItem(k);
    });

    location.href = 'index.html';
  };

  // ============================================================
  // ESC CLOSE
  // ============================================================
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
  });

  // ============================================================
  // FLOAT-IN ANIMATION FOR CARDS
  // ============================================================
  function initFloatCards() {
    if (!('IntersectionObserver' in window)) {
      // Fallback: hiển thị tất cả cards
      document.querySelectorAll('.plugin-card, .theme-card').forEach((c) => {
        c.classList.add('in-view');
      });
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('.plugin-card, .theme-card').forEach((card) => {
      observer.observe(card);
    });

    // Re-observe khi cards được render lại (filter, search)
    const observerCallback = () => {
      document.querySelectorAll('.plugin-card:not(.in-view), .theme-card:not(.in-view)').forEach((card) => {
        observer.observe(card);
      });
    };

    // Watch for DOM changes
    const mutationObserver = new MutationObserver(observerCallback);
    mutationObserver.observe(document.body, { childList: true, subtree: true });
  }

  // ============================================================
  // INIT
  // ============================================================
  function init() {
    // Luôn init float animation (cả desktop + mobile)
    setTimeout(initFloatCards, 500);

    if (!isMobile()) return;

    injectHamburger();
    injectDrawer();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Re-init on resize
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (isMobile()) {
        injectHamburger();
        injectDrawer();
      } else {
        document.getElementById('mobile-hamburger')?.remove();
        document.getElementById('mobile-drawer')?.remove();
        document.body.style.overflow = '';
      }
    }, 200);
  });

  console.log('📱 Mobile menu loaded');
})();