// store/web/marketplace.js
/**
 * CogniCraft Marketplace 3D (v2 — Fixed)
 * - Particle background
 * - 3D tilt cards
 * - Live hover preview
 * - Modal detail
 * - Filter + search
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

  let state = {
    themes: [],
    featured: [],
    currentFilter: { search: '', sort: 'downloads', tag: '' },
    currentPage: 1,
    total: 0,
  };

  let carouselIdx = 0;
  let carouselTimer = null;

  // ============================================================
  // PARTICLE CANVAS
  // ============================================================
  function initParticles() {
    const canvas = document.getElementById('bg-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let W = (canvas.width = window.innerWidth);
    let H = (canvas.height = window.innerHeight);

    const particles = [];
    const COUNT = Math.min(80, Math.floor(W / 20));

    for (let i = 0; i < COUNT; i++) {
      particles.push({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r: Math.random() * 1.5 + 0.5,
        hue: 260 + Math.random() * 60,
      });
    }

    function draw() {
      ctx.fillStyle = 'rgba(10, 1, 24, 0.15)';
      ctx.fillRect(0, 0, W, H);

      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.strokeStyle = `hsla(${particles[i].hue}, 80%, 60%, ${0.15 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 80%, 70%, 0.6)`;
        ctx.fill();
      });

      requestAnimationFrame(draw);
    }

    draw();

    window.addEventListener('resize', () => {
      W = canvas.width = window.innerWidth;
      H = canvas.height = window.innerHeight;
    });
  }

  // ============================================================
  // CURSOR GLOW
  // ============================================================
  function initCursorGlow() {
    const glow = document.createElement('div');
    glow.className = 'cursor-glow';
    document.body.appendChild(glow);

    document.addEventListener('mousemove', (e) => {
      glow.style.transform = `translate(${e.clientX}px, ${e.clientY}px) translate(-50%, -50%)`;
    });
  }

  // ============================================================
  // HERO 3D TILT
  // ============================================================
  function initHeroTilt() {
    const heroContent = document.querySelector('.hero-content');
    if (!heroContent) return;

    document.addEventListener('mousemove', (e) => {
      const x = (e.clientX / window.innerWidth - 0.5) * 15;
      const y = (e.clientY / window.innerHeight - 0.5) * 15;
      heroContent.style.transform = `rotateX(${-y}deg) rotateY(${x}deg)`;
    });
  }

  // ============================================================
  // API
  // ============================================================
  async function api(path, options = {}) {
    const res = await fetch(API_BASE + path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });
    if (!res.ok) throw new Error('API ' + res.status);
    return res.json();
  }

  // ============================================================
  // FETCH THEMES
  // ============================================================
  async function fetchThemes() {
    const p = new URLSearchParams();
    if (state.currentFilter.search) p.set('search', state.currentFilter.search);
    if (state.currentFilter.sort) p.set('sort', state.currentFilter.sort);
    if (state.currentFilter.tag) p.set('tag', state.currentFilter.tag);
    p.set('page', state.currentPage);
    p.set('per_page', 24);

    const data = await api('/api/marketplace/themes?' + p.toString());
    state.themes = data.themes || [];
    state.total = data.total || 0;

    // Featured: ưu tiên theme có featured=true, fallback 5 theme đầu
    state.featured = state.themes.filter((t) => t.featured);
    if (state.featured.length === 0) {
      state.featured = state.themes.slice(0, Math.min(5, state.themes.length));
    }

    renderFeatured();
    renderGrid();
  }

  // ============================================================
  // FETCH TAGS
  // ============================================================
  async function fetchTags() {
    try {
      const data = await api('/api/marketplace/tags');
      renderTags(data.tags || []);
    } catch (e) {
      console.warn('Tags fetch failed:', e);
    }
  }

  // ============================================================
  // RENDER: TAGS
  // ============================================================
  function renderTags(tags) {
    const el = document.getElementById('tag-chips');
    if (!el) return;

    if (!tags || tags.length === 0) {
      el.innerHTML = '<span style="color:var(--text-muted);font-size:12px;padding:0 40px;">Chưa có tag nào</span>';
      return;
    }

    el.innerHTML = tags
      .slice(0, 20)
      .map((t) => `<span class="tag-chip" data-tag="${escapeHtml(t.tag)}">#${escapeHtml(t.tag)} <span style="opacity:0.6">${t.count}</span></span>`)
      .join('');

    el.querySelectorAll('.tag-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        const tag = chip.dataset.tag;
        if (state.currentFilter.tag === tag) {
          state.currentFilter.tag = '';
          chip.classList.remove('active');
        } else {
          state.currentFilter.tag = tag;
          el.querySelectorAll('.tag-chip').forEach((c) => c.classList.remove('active'));
          chip.classList.add('active');
        }
        state.currentPage = 1;
        fetchThemes();
      });
    });
  }

  // ============================================================
  // RENDER: FEATURED CAROUSEL (auto-adapt 1/2/3+ themes)
  // ============================================================
   function renderFeatured() {
    const stage = document.getElementById('carousel-stage');
    if (!stage) return;

    const section = stage.closest('.featured-3d');

    // Nhánh 1: Không có theme → ẩn section
    if (state.featured.length === 0) {
      stage.innerHTML = '';
      if (section) section.style.display = 'none';
      return;
    }

    if (section) section.style.display = '';

    // Nhánh 2: 1-2 theme → grid layout
    if (state.featured.length < 3) {
      if (section) section.classList.add('grid-mode');

      stage.style.position = 'relative';
      stage.style.display = 'grid';
      stage.style.gridTemplateColumns = `repeat(${state.featured.length}, minmax(280px, 360px))`;
      stage.style.gap = '24px';
      stage.style.justifyContent = 'center';
      stage.style.padding = '20px';
      stage.style.height = 'auto';

      stage.innerHTML = state.featured
        .map((t) => `
          <div class="theme-card ${t.featured ? 'featured' : ''}" 
               data-slug="${escapeHtml(t.slug)}"
               style="position:relative;width:100%;height:360px;">
            <div class="card-glow"></div>
            <div class="theme-preview" style="height:200px;background-image:url('${escapeAttr(t.preview_image || '')}');background-size:cover;">
              <div class="mock-ui">
                <div class="mock-bar w80"></div>
                <div class="mock-bar w60"></div>
                <div class="mock-bar w40"></div>
                <div class="mock-dots">
                  <div class="mock-dot"></div>
                  <div class="mock-dot"></div>
                  <div class="mock-dot"></div>
                </div>
              </div>
            </div>
            <div class="card-info">
              <div class="card-name">${escapeHtml(t.name)}</div>
              <div class="card-desc">${escapeHtml(t.description || '')}</div>
              <div class="card-meta">
                <div class="card-author">
                  <img src="${escapeAttr(t.author_avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + t.author_name)}" alt="">
                  <span>${escapeHtml(t.author_name || 'Anon')}</span>
                </div>
                <div class="card-stats">
                  <span class="stat">⬇ ${t.downloads || 0}</span>
                  <span class="stat">❤ ${t.likes || 0}</span>
                </div>
              </div>
            </div>
          </div>
        `)
        .join('');

      stage.querySelectorAll('.theme-card').forEach((card) => {
        setupCardTilt(card);
        card.addEventListener('click', () => openModal(card.dataset.slug));
      });

      return;
    }

    // Nhánh 3: ≥3 themes → carousel 3D
    if (section) section.classList.remove('grid-mode');

    stage.style.display = 'flex';
    stage.style.position = 'absolute';
    stage.style.gridTemplateColumns = '';
    stage.style.padding = '';
    stage.style.height = '';
    stage.style.gap = '';

    stage.innerHTML = state.featured
      .map(
        (t, i) => `
        <div class="carousel-item" data-idx="${i}" data-slug="${escapeHtml(t.slug)}">
          <div class="preview" style="background-image: url('${escapeAttr(t.preview_image || '')}');"></div>
          <div class="info">
            <div class="name">${escapeHtml(t.name)}</div>
            <div class="author">by ${escapeHtml(t.author_name || 'Anonymous')}</div>
            <div class="stats">
              <span>⬇ ${t.downloads || 0}</span>
              <span>❤ ${t.likes || 0}</span>
            </div>
          </div>
        </div>
      `
      )
      .join('');

    updateCarousel();

    stage.querySelectorAll('.carousel-item').forEach((item) => {
      item.addEventListener('click', () => {
        if (item.classList.contains('center')) {
          openModal(item.dataset.slug);
        } else {
          carouselIdx = parseInt(item.dataset.idx);
          updateCarousel();
        }
      });
    });

    if (carouselTimer) clearInterval(carouselTimer);
    carouselTimer = setInterval(() => {
      carouselIdx = (carouselIdx + 1) % state.featured.length;
      updateCarousel();
    }, 4000);
  }

  function updateCarousel() {
    const items = document.querySelectorAll('.carousel-item');
    const len = items.length;
    items.forEach((item, i) => {
      item.classList.remove('center', 'left', 'right', 'hidden');

      const diff = (i - carouselIdx + len) % len;
      if (diff === 0) item.classList.add('center');
      else if (diff === 1 || (len > 2 && diff === len - 1)) {
        if (diff === 1) item.classList.add('right');
        else item.classList.add('left');
      } else {
        item.classList.add('hidden');
      }
    });
  }

  // ============================================================
  // RENDER: GRID
  // ============================================================
  function renderGrid() {
    const grid = document.getElementById('theme-grid');
    if (!grid) return;

    if (state.themes.length === 0) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <div class="icon">🌌</div>
          <h3 style="margin-bottom:8px;color:#fff;">Chưa có theme nào</h3>
          <p>Hãy là người đầu tiên publish theme lên marketplace!</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = state.themes
      .map(
        (t) => `
        <div class="theme-card ${t.featured ? 'featured' : ''} ${t.verified ? 'verified' : ''}"
             data-slug="${escapeHtml(t.slug)}">
          <div class="card-glow"></div>
          <div class="theme-preview">
            <div class="mock-ui">
              <div class="mock-bar w80"></div>
              <div class="mock-bar w60"></div>
              <div class="mock-bar w40"></div>
              <div class="mock-dots">
                <div class="mock-dot"></div>
                <div class="mock-dot"></div>
                <div class="mock-dot"></div>
              </div>
            </div>
          </div>
          <div class="card-info">
            <div class="card-name">${escapeHtml(t.name)}</div>
            <div class="card-desc">${escapeHtml(t.description || 'Không có mô tả')}</div>
            <div class="card-meta">
              <div class="card-author">
                <img src="${escapeAttr(t.author_avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + t.author_name)}" alt="">
                <span>${escapeHtml(t.author_name || 'Anon')}</span>
              </div>
              <div class="card-stats">
                <span class="stat">⬇ ${t.downloads || 0}</span>
                <span class="stat">❤ ${t.likes || 0}</span>
              </div>
            </div>
          </div>
        </div>
      `
      )
      .join('');

    grid.querySelectorAll('.theme-card').forEach((card) => {
      setupCardTilt(card);
      card.addEventListener('click', () => openModal(card.dataset.slug));
    });
  }

  // ============================================================
  // CARD 3D TILT
  // ============================================================
  function setupCardTilt(card) {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const cx = rect.width / 2;
      const cy = rect.height / 2;

      const rx = ((y - cy) / cy) * -8;
      const ry = ((x - cx) / cx) * 8;

      card.style.transform = `perspective(1000px) rotateX(${rx}deg) rotateY(${ry}deg) translateZ(10px) scale(1.02)`;
      card.style.setProperty('--mx', (x / rect.width) * 100 + '%');
      card.style.setProperty('--my', (y / rect.height) * 100 + '%');
    });

    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  }

  // ============================================================
  // MODAL
  // ============================================================
  async function openModal(slug) {
    const modal = document.getElementById('modal');
    const content = modal.querySelector('.mk-modal-content');

    modal.classList.add('open');
    document.body.style.overflow = 'hidden';

    content.querySelector('.modal-info').innerHTML = `
      <div class="skeleton" style="height:32px;margin-bottom:16px;"></div>
      <div class="skeleton" style="height:60px;margin-bottom:24px;"></div>
      <div class="skeleton" style="height:120px;margin-bottom:24px;"></div>
      <div class="skeleton" style="height:60px;"></div>
    `;

    try {
      const data = await api('/api/marketplace/themes/' + slug);
      renderModal(data.theme, data.other_themes || []);
    } catch (e) {
      content.querySelector('.modal-info').innerHTML = `<p style="color:#f87171;">Lỗi tải theme: ${e.message}</p>`;
    }
  }

  function renderModal(theme, otherThemes) {
    const modal = document.getElementById('modal');
    const info = modal.querySelector('.modal-info');
    const previewFrame = document.getElementById('modal-preview-frame');

    const previewHtml = `
      <!DOCTYPE html>
      <html>
      <head>
        <style>${theme.css_content || ''}</style>
        <style>
          * { box-sizing: border-box; }
          body { margin: 0; padding: 24px; font-family: system-ui; min-height: 100vh; }
          .demo-card { padding: 20px; border-radius: 12px; margin: 16px 0; border: 1px solid rgba(150,150,150,0.2); }
          button { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-weight: 600; }
        </style>
      </head>
      <body>
        <h1>Demo Theme</h1>
        <p>Đây là preview trực tiếp của theme. Bạn có thể xem hiệu ứng ngay tại đây.</p>
        <div class="demo-card">
          <h3>Card Title</h3>
          <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>
          <button>Demo Button</button>
        </div>
        <a href="#">Demo Link →</a>
      </body>
      </html>
    `;

    previewFrame.srcdoc = previewHtml;

    const tags = (theme.tags || []).map((t) => `<span class="modal-tag">#${escapeHtml(t)}</span>`).join('');

    info.innerHTML = `
      <div class="modal-title">${escapeHtml(theme.name)}</div>
      <div class="modal-author">
        <img src="${escapeAttr(theme.author_avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + theme.author_name)}" alt="">
        <div>
          <div class="name">${escapeHtml(theme.author_name || 'Anonymous')}</div>
          <div class="role">Theme Creator</div>
        </div>
      </div>
      <div class="modal-desc">${escapeHtml(theme.description || 'Không có mô tả.')}</div>
      ${tags ? `<div class="modal-tags">${tags}</div>` : ''}
      <div class="modal-stats">
        <div class="modal-stat"><span class="num">${theme.downloads || 0}</span><span class="label">Lượt tải</span></div>
        <div class="modal-stat"><span class="num">${theme.likes || 0}</span><span class="label">Lượt thích</span></div>
      </div>
      <div class="modal-actions">
        <button class="btn-modal primary" id="btn-apply">✨ Áp dụng theme</button>
        <button class="btn-modal secondary" id="btn-like">❤️ Thích</button>
      </div>
    `;

    document.getElementById('btn-apply').addEventListener('click', () => applyTheme(theme.slug));
    document.getElementById('btn-like').addEventListener('click', () => likeTheme(theme.slug));
  }

  function closeModal() {
    const modal = document.getElementById('modal');
    modal.classList.remove('open');
    document.body.style.overflow = '';
  }

  // ============================================================
  // ACTIONS
  // ============================================================
  async function applyTheme(slug) {
    try {
      const res = await fetch(API_BASE + '/api/marketplace/themes/' + slug + '/apply', {
        method: 'POST',
        headers: {
          Authorization: 'Bearer ' + getToken(),
          'Content-Type': 'application/json',
        },
      });
      const data = await res.json();

      if (!res.ok) {
        toast(data.detail || 'Lỗi apply theme', 'error');
        return;
      }

      toast('✨ Đã áp dụng theme! Reload trang để thấy.', 'success');

      if (window.reloadUserTheme) {
        setTimeout(() => window.reloadUserTheme(), 500);
      }
    } catch (e) {
      toast('Lỗi: ' + e.message, 'error');
    }
  }

  async function likeTheme(slug) {
    try {
      const res = await fetch(API_BASE + '/api/marketplace/themes/' + slug + '/like', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + getToken() },
      });
      const data = await res.json();

      if (!res.ok) {
        toast(data.detail || 'Lỗi like', 'error');
        return;
      }

      toast('❤️ Đã thích theme!', 'success');
    } catch (e) {
      toast('Lỗi: ' + e.message, 'error');
    }
  }

  // ============================================================
  // TOAST — INLINE STYLES (không bị user theme override)
  // ============================================================
  function toast(msg, type = 'success') {
    document.querySelectorAll('.mk-toast-fixed').forEach(el => el.remove());

    const el = document.createElement('div');
    el.className = 'mk-toast-fixed';

    const colors = {
      success: 'linear-gradient(135deg, #22c55e, #16a34a)',
      error: 'linear-gradient(135deg, #ef4444, #dc2626)',
      info: 'linear-gradient(135deg, #a855f7, #ec4899)',
    };

    el.style.cssText = `
      position: fixed !important;
      top: 90px !important;
      right: 30px !important;
      left: auto !important;
      bottom: auto !important;
      padding: 16px 24px !important;
      border-radius: 14px !important;
      background: ${colors[type] || colors.info} !important;
      color: #fff !important;
      font-weight: 700 !important;
      font-size: 14px !important;
      font-family: system-ui, -apple-system, sans-serif !important;
      z-index: 999999 !important;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5) !important;
      max-width: 400px !important;
      width: auto !important;
      height: auto !important;
      opacity: 1 !important;
      transform: translateX(0) !important;
      transition: all 0.3s ease-out !important;
      pointer-events: none !important;
    `;
    el.textContent = msg;
    document.body.appendChild(el);

    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateX(400px)';
      setTimeout(() => el.remove(), 300);
    }, 3000);
  }

  // ============================================================
  // HELPERS
  // ============================================================
  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function escapeAttr(s) {
    return String(s || '').replace(/[<>"'&]/g, '');
  }

  // ============================================================
  // FILTER EVENTS
  // ============================================================
  function initFilters() {
    const searchInput = document.getElementById('mk-search');
    const sortSelect = document.getElementById('mk-sort');

    let debounce;
    searchInput?.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        state.currentFilter.search = searchInput.value.trim();
        state.currentPage = 1;
        fetchThemes();
      }, 400);
    });

    sortSelect?.addEventListener('change', () => {
      state.currentFilter.sort = sortSelect.value;
      state.currentPage = 1;
      fetchThemes();
    });
  }

  // ============================================================
  // INIT
  // ============================================================
  async function init() {
    initParticles();
    initCursorGlow();
    initHeroTilt();
    initFilters();

    const modal = document.getElementById('modal');
    if (modal) {
      modal.querySelector('.mk-modal-backdrop').addEventListener('click', closeModal);
      modal.querySelector('.modal-close').addEventListener('click', closeModal);
    }

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeModal();
    });

    document.getElementById('cta-explore')?.addEventListener('click', () => {
      document.getElementById('section-grid')?.scrollIntoView({ behavior: 'smooth' });
    });

    try {
      await fetchThemes();
      await fetchTags();
    } catch (e) {
      console.error('Marketplace init:', e);
      toast('Lỗi kết nối API', 'error');
    }

    console.log('✨ Marketplace 3D loaded');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();