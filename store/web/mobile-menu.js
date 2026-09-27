// store/web/mobile-menu.js
/**
 * CogniCraft Mobile Menu v3
 * - Hamburger LEFT, Logo RIGHT
 * - Drawer slide từ TRÁI
 * - Cards horizontal carousel (Google Play style)
 * - Haptic feedback on touch
 */
(function () {
  'use strict';

  const isMobile = () => window.innerWidth <= 768;

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
  // HELPERS
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

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  // ============================================================
  // HAMBURGER — GÓC TRÁI
  // ============================================================
  function injectHamburger() {
    if (document.getElementById('mobile-hamburger')) return;

    const btn = document.createElement('button');
    btn.id = 'mobile-hamburger';
    btn.className = 'mobile-hamburger';
    btn.setAttribute('aria-label', 'Menu');
    btn.innerHTML = `
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <path d="M2 5H20M2 11H14M2 17H20" 
              stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
      </svg>
    `;
    btn.onclick = openDrawer;

    document.body.appendChild(btn);
  }

  // ============================================================
  // DRAWER — SLIDE TỪ TRÁI
  // ============================================================
  function injectDrawer() {
    if (document.getElementById('mobile-drawer')) return;

    const user = getUserInfo();
    const userName = user?.name || 'Khách';
    const userEmail = user?.email || 'Chưa đăng nhập';
    const userInitial = userName.charAt(0).toUpperCase();

    const drawer = document.createElement('div');
    drawer.id = 'mobile-drawer';
    drawer.className = 'mobile-drawer';
    drawer.innerHTML = `
      <div class="mobile-drawer-backdrop" onclick="closeDrawer()"></div>
      <aside class="mobile-drawer-panel">
        <button class="mobile-drawer-close" onclick="closeDrawer()" aria-label="Đóng">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M4 4L14 14M14 4L4 14" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>

        <div class="mobile-drawer-header">
          <div class="mobile-drawer-logo">🏛️</div>
          <div class="mobile-drawer-brand">
            <div class="mobile-drawer-brand-title">COGNICRAFT</div>
            <div class="mobile-drawer-brand-sub">Ecosystem</div>
          </div>
        </div>

        <div class="mobile-drawer-user">
          <div class="mobile-drawer-avatar">${esc(userInitial)}</div>
          <div class="mobile-drawer-userinfo">
            <div class="mobile-drawer-username">${esc(userName)}</div>
            <div class="mobile-drawer-email">${esc(userEmail)}</div>
          </div>
        </div>

        <nav class="mobile-drawer-nav">
          ${MENU_ITEMS.map(item => `
            <a href="${item.href}"
               class="mobile-drawer-item ${currentPage === item.href ? 'active' : ''}">
              <span class="mobile-drawer-icon">${item.icon}</span>
              <span class="mobile-drawer-label">${item.label}</span>
              ${item.badge === 'themes' ? '<span class="mobile-drawer-badge" id="mobile-theme-count">0</span>' : ''}
              <span class="mobile-drawer-chevron">›</span>
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
  // THEME BADGE
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

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
  });

  // ============================================================
  // SCROLL-FADE-IN ANIMATION
  // ============================================================
  function initFloatCards() {
    if (!('IntersectionObserver' in window)) {
      document.querySelectorAll('.plugin-card, .theme-card').forEach((c) => {
        c.classList.add('in-view');
      });
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          const randomDelay = (Math.random() * 0.3).toFixed(2);
          entry.target.style.animationDelay = `${randomDelay}s`;
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.05, rootMargin: '0px 0px -20px 0px' });

    const observeCards = () => {
      document.querySelectorAll('.plugin-card:not(.in-view), .theme-card:not(.in-view)').forEach((card) => {
        observer.observe(card);
      });
    };

    observeCards();

    const mutationObserver = new MutationObserver(observeCards);
    mutationObserver.observe(document.body, { childList: true, subtree: true });
  }

  // ============================================================
  // HAPTIC FEEDBACK ON TOUCH (không tilt 3D nữa)
  // ============================================================
  function initTouchFeedback() {
    document.addEventListener('touchstart', (e) => {
      const card = e.target.closest('.plugin-card, .theme-card');
      if (!card) return;
      card.style.transform = 'scale(0.96)';
    }, { passive: true });

    document.addEventListener('touchend', () => {
      document.querySelectorAll('.plugin-card, .theme-card').forEach((card) => {
        card.style.transform = '';
      });
    }, { passive: true });

    document.addEventListener('touchcancel', () => {
      document.querySelectorAll('.plugin-card, .theme-card').forEach((card) => {
        card.style.transform = '';
      });
    }, { passive: true });
  }

  // ============================================================
  // INIT
  // ============================================================
  function init() {
    setTimeout(initFloatCards, 300);
    initTouchFeedback();

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

  console.log('📱 Mobile menu v3 loaded');
})();