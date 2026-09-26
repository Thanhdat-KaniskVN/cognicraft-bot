// store/web/theme-3d-runtime.js
/**
 * CogniCraft Cthulhu Runtime v13 — Realistic Cthulhu Eye
 * Slit pupil, blood veins, detailed iris
 */
(function () {
  'use strict';

  let currentCleanup = null;
  let currentSceneId = null;
  let overlayElements = [];
  let overlayTimers = [];
  let mouseTracker = null;

  function ensureCanvas() {
    let canvas = document.getElementById('theme-3d-canvas');
    if (canvas) return canvas;
    const oldBg = document.getElementById('bg-canvas');
    if (oldBg) oldBg.style.display = 'none';
    canvas = document.createElement('canvas');
    canvas.id = 'theme-3d-canvas';
    canvas.style.cssText = `
      position: fixed !important;
      top: 0 !important; left: 0 !important;
      width: 100vw !important; height: 100vh !important;
      z-index: 1 !important;
      display: block !important;
      pointer-events: auto !important;
    `;
    document.body.appendChild(canvas);
    return canvas;
  }

  // ============================================================
  // SVG — CTHULHU EYE (dùng làm background-image)
  // ============================================================
  function makeEyeSVG() {
    // SVG 200x200, pupil ở giữa — sẽ được dịch chuyển bằng CSS var
    return `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'>
      <defs>
        <radialGradient id='sclera' cx='50%25' cy='50%25' r='50%25'>
          <stop offset='0%25' stop-color='%23f0e0c8'/>
          <stop offset='60%25' stop-color='%23d8c0a0'/>
          <stop offset='100%25' stop-color='%23a08868'/>
        </radialGradient>
        <radialGradient id='iris' cx='50%25' cy='50%25' r='50%25'>
          <stop offset='0%25' stop-color='%23ff6040'/>
          <stop offset='35%25' stop-color='%23c81818'/>
          <stop offset='70%25' stop-color='%23780000'/>
          <stop offset='100%25' stop-color='%23300000'/>
        </radialGradient>
        <radialGradient id='irisGlow' cx='40%25' cy='35%25' r='60%25'>
          <stop offset='0%25' stop-color='%23ffb0a0' stop-opacity='0.9'/>
          <stop offset='50%25' stop-color='%23ff5040' stop-opacity='0.4'/>
          <stop offset='100%25' stop-color='%23ff2010' stop-opacity='0'/>
        </radialGradient>
        <filter id='glow'>
          <feGaussianBlur stdDeviation='4' result='b'/>
          <feMerge><feMergeNode in='b'/><feMergeNode in='SourceGraphic'/></feMerge>
        </filter>
      </defs>

      <!-- SCLERA (nền trắng-vàng) -->
      <ellipse cx='100' cy='100' rx='92' ry='88' fill='url(%23sclera)'/>

      <!-- Vệt máu từ góc mắt -->
      <g stroke='%23a02020' stroke-width='0.8' fill='none' opacity='0.65'>
        <path d='M 15 75 Q 40 80 55 90'/>
        <path d='M 10 100 Q 35 100 52 100'/>
        <path d='M 12 125 Q 38 122 55 112'/>
        <path d='M 185 78 Q 162 82 145 92'/>
        <path d='M 190 100 Q 165 102 148 100'/>
        <path d='M 188 125 Q 160 122 145 112'/>
      </g>

      <!-- IRIS (tròng đỏ) -->
      <circle cx='100' cy='100' r='58' fill='url(%23iris)' filter='url(%23glow)'/>

      <!-- Vân iris -->
      <g stroke='%23ff8060' stroke-width='0.7' fill='none' opacity='0.5'>
        <path d='M 100 45 L 100 55'/>
        <path d='M 130 50 L 125 62'/>
        <path d='M 155 75 L 142 82'/>
        <path d='M 155 125 L 142 118'/>
        <path d='M 130 150 L 125 138'/>
        <path d='M 100 155 L 100 145'/>
        <path d='M 70 150 L 75 138'/>
        <path d='M 45 125 L 58 118'/>
        <path d='M 45 75 L 58 82'/>
        <path d='M 70 50 L 75 62'/>
      </g>

      <!-- Iris highlight -->
      <circle cx='100' cy='100' r='58' fill='url(%23irisGlow)' opacity='0.6'/>

      <!-- PUPIL DỌC (SLIT) — đặc trưng Cthulhu/rồng -->
      <ellipse id='pupil' cx='100' cy='100' rx='10' ry='45' fill='%23000000'/>
      <ellipse cx='100' cy='100' rx='7' ry='40' fill='%23050505'/>

      <!-- Highlight trên pupil -->
      <ellipse cx='96' cy='85' rx='3' ry='6' fill='%23ffffff' opacity='0.7'/>
      <ellipse cx='104' cy='115' rx='2' ry='4' fill='%23ffffff' opacity='0.3'/>

      <!-- Shadow trong mắt -->
      <ellipse cx='100' cy='100' rx='92' ry='88' fill='none' stroke='%23000' stroke-width='3' opacity='0.6'/>
      <ellipse cx='100' cy='100' rx='88' ry='84' fill='none' stroke='%23000' stroke-width='1' opacity='0.8'/>
    </svg>")`;
  }

  function injectZombieCSS() {
    const existing = document.getElementById('zombie-overlay-styles');
    if (existing) existing.remove();

    const style = document.createElement('style');
    style.id = 'zombie-overlay-styles';
    style.textContent = `
      body.scene-zombie { background: #050203 !important; }

      body.scene-zombie::before {
        content: '';
        position: fixed; inset: 0;
        z-index: 9000;
        pointer-events: none;
        background: radial-gradient(ellipse at center,
          transparent 35%,
          rgba(60, 0, 0, 0.2) 75%,
          rgba(20, 0, 0, 0.6) 100%);
      }

      .z-grain {
        position: fixed; inset: 0;
        z-index: 9002;
        pointer-events: none;
        opacity: 0.12;
        mix-blend-mode: overlay;
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence baseFrequency='0.85' numOctaves='3'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.3'/></svg>");
        background-size: 200px 200px;
        animation: z-grain 0.5s steps(3) infinite;
      }
      @keyframes z-grain {
        0%   { transform: translate(0, 0); }
        33%  { transform: translate(-1%, 1%); }
        66%  { transform: translate(1%, -1%); }
        100% { transform: translate(0, 0); }
      }

      .z-tape {
        position: fixed;
        width: 260px; height: 22px;
        z-index: 9004;
        pointer-events: none;
        background: repeating-linear-gradient(45deg,
          #d4b300 0px, #d4b300 14px,
          #1a1a1a 14px, #1a1a1a 28px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.7);
        opacity: 0.7;
        font-family: system-ui, sans-serif;
        color: #1a1a1a;
        font-weight: 900;
        font-size: 11px;
        letter-spacing: 3px;
        text-align: center;
        line-height: 22px;
      }
      .z-tape.tl { top: 60px; left: -70px; transform: rotate(-42deg); }
      .z-tape.br { bottom: 80px; right: -70px; transform: rotate(-42deg); }

      .z-siren {
        position: fixed;
        width: 180px; height: 180px;
        z-index: 9005;
        pointer-events: none;
        border-radius: 50%;
        animation: z-siren 3s ease-in-out infinite;
        mix-blend-mode: screen;
      }
      .z-siren.left {
        top: 80px; left: -90px;
        background: radial-gradient(circle, rgba(220,30,20,0.5) 0%, transparent 70%);
      }
      .z-siren.right {
        top: 80px; right: -90px;
        background: radial-gradient(circle, rgba(30,70,220,0.4) 0%, transparent 70%);
        animation-delay: -1.5s;
      }
      @keyframes z-siren {
        0%, 100% { opacity: 0.15; }
        50%      { opacity: 0.5; }
      }

      .z-flicker {
        position: fixed; inset: 0;
        z-index: 9006;
        pointer-events: none;
        background: #000;
        opacity: 0;
        animation: z-flicker 10s linear infinite;
      }
      @keyframes z-flicker {
        0%, 47%, 48%, 49%, 91%, 92%, 100%   { opacity: 0; }
        48.3% { opacity: 0.06; }
        48.6% { opacity: 0; }
        91.5% { opacity: 0.1; }
      }

      .z-fog {
        position: fixed;
        bottom: 0; left: 0; right: 0;
        height: 35vh;
        z-index: 9003;
        pointer-events: none;
        background:
          radial-gradient(ellipse 60% 50% at 20% 100%, rgba(60, 20, 20, 0.5) 0%, transparent 60%),
          radial-gradient(ellipse 70% 55% at 55% 100%, rgba(80, 30, 25, 0.45) 0%, transparent 65%),
          radial-gradient(ellipse 55% 45% at 85% 100%, rgba(60, 20, 20, 0.45) 0%, transparent 60%);
        animation: z-fog-drift 15s ease-in-out infinite;
      }
      @keyframes z-fog-drift {
        0%, 100% { transform: translateX(0); }
        50%      { transform: translateX(20px); }
      }

      /* ============================================================
         TITLE
         ============================================================ */
      body.scene-zombie .hero-title,
      body.scene-zombie .mk-hero .hero-title {
        position: relative !important;
        z-index: 100 !important;
        color: transparent !important;
        background:
          linear-gradient(180deg,
            #ffffff 0%,
            #f5d5b8 20%,
            #e8a080 45%,
            #c86040 70%,
            #8a2018 100%) !important;
        -webkit-background-clip: text !important;
        background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        text-shadow: none !important;
        filter: drop-shadow(0 2px 0 #2a0000) drop-shadow(0 8px 24px rgba(0,0,0,0.85)) !important;
      }

      body.scene-zombie .hero-title::after {
        content: '';
        position: absolute;
        top: calc(100% - 2px);
        left: 8%; right: 8%;
        height: 140px;
        pointer-events: none;
        z-index: -1;
        background:
          linear-gradient(180deg, #a00000 0%, #700000 40%, #400000 75%, transparent 100%) no-repeat 8% 0 / 6px 100%,
          linear-gradient(180deg, #900000 0%, #600000 45%, transparent 100%) no-repeat 30% 0 / 4px 85%,
          linear-gradient(180deg, #b00000 0%, #780000 40%, #400000 75%, transparent 100%) no-repeat 52% 0 / 7px 100%,
          linear-gradient(180deg, #880000 0%, #580000 50%, transparent 100%) no-repeat 74% 0 / 4px 80%,
          linear-gradient(180deg, #a50000 0%, #700000 45%, transparent 100%) no-repeat 92% 0 / 6px 90%;
        animation: z-blood-grow 5s ease-in-out infinite;
        transform-origin: top center;
      }
      @keyframes z-blood-grow {
        0%, 100% { transform: scaleY(1); }
        50%      { transform: scaleY(1.08); }
      }

      /* ============================================================
         👁️ CTHULHU EYE — SLIT PUPIL
         Chỉ áp dụng cho HERO FLOAT CARDS thôi
         ============================================================ */
      body.scene-zombie .hero-float-card {
        background-color: #0a0102 !important;
        background-image: ${makeEyeSVG()} !important;
        background-size: 95% 95% !important;
        background-position: var(--pupil-x, 50%) var(--pupil-y, 50%) !important;
        background-repeat: no-repeat !important;
        overflow: hidden !important;
        border: 1px solid rgba(180, 30, 30, 0.6) !important;
        box-shadow:
          inset 0 0 60px rgba(200, 20, 20, 0.3),
          0 0 40px rgba(200, 30, 20, 0.4) !important;
      }

      body.scene-zombie .hero-float-card .mini-bar {
        display: none !important;
      }

      /* Theme preview cards — giữ style cũ nhưng đổi sang đỏ */
      body.scene-zombie .theme-preview {
        background: radial-gradient(circle at 50% 50%,
          #2a0808 0%, #1a0406 50%, #0a0102 100%) !important;
        border-bottom: 1px solid rgba(140, 20, 20, 0.5) !important;
        position: relative !important;
        overflow: hidden !important;
      }

      /* Eye mini cho theme preview */
      body.scene-zombie .theme-preview::before {
        content: '';
        position: absolute;
        inset: 8%;
        background-image: ${makeEyeSVG()};
        background-size: contain;
        background-position: center;
        background-repeat: no-repeat;
        opacity: 0.9;
        animation: cthulhu-pulse 3s ease-in-out infinite;
        pointer-events: none;
      }

      body.scene-zombie .theme-card .mock-ui {
        display: none !important;
      }

      body.scene-zombie .theme-card {
        background: #0a0102 !important;
        border: 1px solid rgba(140, 20, 20, 0.5) !important;
      }

      body.scene-zombie .theme-card:hover .theme-preview::before {
        opacity: 1;
        filter: brightness(1.3) drop-shadow(0 0 30px rgba(255,60,40,1));
      }

      @keyframes cthulhu-pulse {
        0%, 100% {
          filter: brightness(1) drop-shadow(0 0 20px rgba(255, 30, 20, 0.5));
        }
        50% {
          filter: brightness(1.2) drop-shadow(0 0 40px rgba(255, 60, 40, 0.8));
        }
      }

      /* ============================================================
         CAROUSEL
         ============================================================ */
      body.scene-zombie .carousel-item {
        background: #0a0102 !important;
        border: 1px solid rgba(140, 20, 20, 0.5) !important;
      }
      body.scene-zombie .carousel-item .preview {
        background-image: ${makeEyeSVG()} !important;
        background-size: 80% 80% !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        background-color: #0a0102 !important;
        animation: cthulhu-pulse 3s ease-in-out infinite;
      }

      /* ============================================================
         NAV / SEARCH / BUTTONS
         ============================================================ */
      body.scene-zombie .mk-nav-links a:hover {
        color: #ff4030 !important;
        text-shadow: 0 0 10px rgba(255, 40, 20, 0.8) !important;
      }

      body.scene-zombie .mk-logo,
      body.scene-zombie .logo {
        animation: nav-flicker 7s linear infinite;
      }
      @keyframes nav-flicker {
        0%, 100% { opacity: 1; }
        43%      { opacity: 0.5; }
        44%      { opacity: 1; }
        79%      { opacity: 0.7; }
        80%      { opacity: 1; }
      }

      body.scene-zombie .mk-search,
      body.scene-zombie .mk-select {
        border-color: rgba(140, 20, 20, 0.5) !important;
        box-shadow: inset 0 0 20px rgba(100, 0, 0, 0.3),
                    0 0 20px rgba(100, 0, 0, 0.2) !important;
      }

      body.scene-zombie .btn-hero.primary,
      body.scene-zombie .btn-modal.primary {
        background: linear-gradient(135deg, #7a0e0e, #b01c1c) !important;
        box-shadow: 0 8px 30px rgba(180, 20, 20, 0.5) !important;
      }

      body.scene-zombie .mk-section-title {
        color: #ffb0a0 !important;
        text-shadow: 0 0 15px rgba(200, 40, 20, 0.6) !important;
      }

      body.scene-zombie .mk-nav {
        background: rgba(10, 2, 5, 0.92) !important;
        border-bottom-color: rgba(140, 20, 20, 0.4) !important;
      }

      body.scene-zombie #bg-canvas { display: none !important; }

      /* ============================================================
         HAND
         ============================================================ */
      .z-hand-grab {
        position: fixed !important;
        z-index: 4 !important;
        pointer-events: none !important;
        width: 90px;
        height: 120px;
        transform-origin: bottom center;
        animation: z-hand-sway 4s ease-in-out infinite;
        filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.9));
      }
      @keyframes z-hand-sway {
        0%, 100% { transform: rotate(-1.5deg) translateY(0); }
        50%      { transform: rotate(1.5deg) translateY(-2px); }
      }
    `;
    document.head.appendChild(style);
  }

  // ============================================================
  // 👁️ EYE TRACKING — background-position follow mouse
  // ============================================================
  function startEyeTracking() {
    stopEyeTracking();

    let rafId = null;
    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;

    const onMove = (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        updateEyes(mouseX, mouseY);
      });
    };

    function updateEyes(mx, my) {
      const eyes = document.querySelectorAll('body.scene-zombie .hero-float-card');

      eyes.forEach((eye) => {
        const rect = eye.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;

        const dx = mx - cx;
        const dy = my - cy;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const angle = Math.atan2(dy, dx);

        // Max offset = 20% (background-position %, nên dùng đơn vị khác)
        const maxOffset = 20;
        const offsetRatio = Math.min(1, dist / 400);
        const offset = maxOffset * offsetRatio;

        const px = 50 + Math.cos(angle) * offset;
        const py = 50 + Math.sin(angle) * offset;

        eye.style.setProperty('--pupil-x', px + '%');
        eye.style.setProperty('--pupil-y', py + '%');
      });
    }

    document.addEventListener('mousemove', onMove, { passive: true });

    mouseTracker = {
      stop: () => {
        document.removeEventListener('mousemove', onMove);
        if (rafId) cancelAnimationFrame(rafId);
      }
    };

    updateEyes(mouseX, mouseY);
    console.log('👁️ Slit-pupil eye tracking started');
  }

  function stopEyeTracking() {
    if (mouseTracker) {
      mouseTracker.stop();
      mouseTracker = null;
    }
  }

  // ============================================================
  // SVG HAND
  // ============================================================
  function makeZombieHandSVG() {
    return `
      <svg viewBox="0 0 90 120" xmlns="http://www.w3.org/2000/svg" width="90" height="120">
        <defs>
          <linearGradient id="phSkin" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#6a755a"/>
            <stop offset="50%" stop-color="#3a4530"/>
            <stop offset="100%" stop-color="#1a2015"/>
          </linearGradient>
        </defs>
        <path d="M 8 120 L 6 55 Q 6 40 12 34 Q 18 30 22 38 Q 24 46 22 60 L 22 120 Z" fill="url(#phSkin)" stroke="#0a0a0a" stroke-width="0.6"/>
        <path d="M 22 120 L 20 42 Q 19 20 28 12 Q 36 8 42 16 Q 44 30 40 48 L 38 120 Z" fill="url(#phSkin)" stroke="#0a0a0a" stroke-width="0.6"/>
        <path d="M 38 120 L 38 30 Q 38 4 48 0 Q 58 0 62 14 Q 62 38 58 60 L 56 120 Z" fill="url(#phSkin)" stroke="#0a0a0a" stroke-width="0.6"/>
        <path d="M 56 120 L 58 55 Q 60 32 68 24 Q 76 22 80 30 Q 82 44 78 62 L 72 120 Z" fill="url(#phSkin)" stroke="#0a0a0a" stroke-width="0.6"/>
        <path d="M 14 120 L 12 90 Q 12 78 25 74 L 62 74 Q 76 78 76 90 L 74 120 Z" fill="url(#phSkin)" stroke="#0a0a0a" stroke-width="0.6"/>
      </svg>
    `;
  }

  // ============================================================
  // BUILD OVERLAY
  // ============================================================
  function buildZombieOverlay() {
    injectZombieCSS();
    document.body.classList.add('scene-zombie');

    const els = [];
    function makeEl(cls, html) {
      const el = document.createElement('div');
      el.className = cls;
      if (html) el.innerHTML = html;
      document.body.appendChild(el);
      els.push(el);
      return el;
    }

    makeEl('z-grain');
    makeEl('z-fog');
    const t1 = makeEl('z-tape tl'); t1.textContent = '⚠ QUARANTINE ⚠';
    const t2 = makeEl('z-tape br'); t2.textContent = '☣ BIOHAZARD ☣';
    makeEl('z-siren left');
    makeEl('z-siren right');
    makeEl('z-flicker');

    function placeHand() {
      const searchBar = document.querySelector('.mk-search') || document.querySelector('#mk-search');
      if (!searchBar) return;
      const rect = searchBar.getBoundingClientRect();
      const handEl = document.createElement('div');
      handEl.className = 'z-hand-grab';
      handEl.style.top = (rect.top - 75) + 'px';
      handEl.style.left = (rect.left + 50) + 'px';
      handEl.innerHTML = makeZombieHandSVG();
      document.body.appendChild(handEl);
      els.push(handEl);
    }
    setTimeout(placeHand, 300);
    setTimeout(startEyeTracking, 500);

    console.log('🦑 Cthulhu slit-eye overlay built');
    return els;
  }

  const sceneOverlays = {
    zombie_apocalypse: buildZombieOverlay,
  };

  function destroyScene() {
    stopEyeTracking();
    if (currentCleanup) {
      try { currentCleanup(); } catch (e) {}
      currentCleanup = null;
    }
    const canvas = document.getElementById('theme-3d-canvas');
    if (canvas) canvas.remove();
    overlayElements.forEach((el) => el.remove());
    overlayElements = [];
    overlayTimers.forEach((t) => clearInterval(t));
    overlayTimers = [];
    document.body.classList.remove('scene-zombie');
    document.body.classList.remove('attacked');
    const oldBg = document.getElementById('bg-canvas');
    if (oldBg) oldBg.style.display = '';
    currentSceneId = null;
  }

  function applyScene(sceneId, config) {
    if (!window.CogniScenes) return;
    if (currentSceneId) destroyScene();
    const scene = window.CogniScenes.get(sceneId);
    if (!scene) return;
    const canvas = ensureCanvas();
    try {
      currentCleanup = scene.init(canvas, config || {});
      currentSceneId = sceneId;
      if (sceneOverlays[sceneId]) {
        setTimeout(() => {
          overlayElements = sceneOverlays[sceneId]();
        }, 150);
      }
    } catch (e) {
      console.error('❌ Scene error:', e);
    }
  }

  window.Cogni3D = {
    apply: applyScene,
    destroy: destroyScene,
    getCurrent: () => currentSceneId,
    listScenes: () => (window.CogniScenes ? window.CogniScenes.list() : []),
  };

  console.log('🦑 Cthulhu Runtime v13 loaded');
})();