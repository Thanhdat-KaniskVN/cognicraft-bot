// store/web/floating-balloons.js
/**
 * CogniCraft Floating Balloons
 * - Bóng bay lơ lửng như bong bóng
 * - Tương tác: hover nhẹ nhàng, click bật lên
 * - Tự động spawn + reset
 * - Performance optimized (requestAnimationFrame)
 */
(function () {
  'use strict';

  const CONFIG = {
    COUNT: 8,                    // Số bóng bay
    MIN_SIZE: 36,                // px
    MAX_SIZE: 72,                // px
    MIN_SPEED: 0.15,             // px/frame — nổi lên
    MAX_SPEED: 0.35,
    DRIFT_AMPLITUDE: 30,         // px — dao động ngang
    DRIFT_SPEED: 0.5,            // rad/s
    COLORS: [
      { from: '#a855f7', to: '#ec4899', glow: 'rgba(168, 85, 247, 0.5)' },
      { from: '#06b6d4', to: '#22d3ee', glow: 'rgba(6, 182, 212, 0.5)' },
      { from: '#ec4899', to: '#f472b6', glow: 'rgba(236, 72, 153, 0.5)' },
      { from: '#22c55e', to: '#4ade80', glow: 'rgba(34, 197, 94, 0.5)' },
      { from: '#fbbf24', to: '#f59e0b', glow: 'rgba(251, 191, 36, 0.5)' },
    ],
    SHAPES: ['circle', 'heart', 'star', 'blob'],
  };

  // ============================================================
  // HELPERS
  // ============================================================
  const rand = (min, max) => Math.random() * (max - min) + min;
  const randInt = (min, max) => Math.floor(rand(min, max + 1));
  const pick = (arr) => arr[randInt(0, arr.length - 1)];

  // ============================================================
  // SVG BALLOON
  // ============================================================
  function makeBalloonSVG(shape, color) {
    const id = 'grad_' + Math.random().toString(36).substring(2, 9);

    if (shape === 'circle') {
      return `
        <svg viewBox="0 0 100 120" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <radialGradient id="${id}" cx="35%" cy="30%">
              <stop offset="0%" stop-color="${color.from}" stop-opacity="1"/>
              <stop offset="100%" stop-color="${color.to}" stop-opacity="0.9"/>
            </radialGradient>
          </defs>
          <ellipse cx="50" cy="50" rx="40" ry="48" fill="url(#${id})"/>
          <ellipse cx="38" cy="32" rx="8" ry="12" fill="rgba(255,255,255,0.55)" opacity="0.7"/>
          <ellipse cx="60" cy="25" rx="4" ry="6" fill="rgba(255,255,255,0.4)" opacity="0.6"/>
          <polygon points="50,98 46,104 54,104" fill="${color.to}" opacity="0.85"/>
          <path d="M 50 104 Q 55 112 48 118" stroke="${color.to}" stroke-width="1.5" fill="none" opacity="0.6"/>
        </svg>
      `;
    }

    if (shape === 'heart') {
      return `
        <svg viewBox="0 0 100 120" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <radialGradient id="${id}" cx="35%" cy="35%">
              <stop offset="0%" stop-color="${color.from}"/>
              <stop offset="100%" stop-color="${color.to}"/>
            </radialGradient>
          </defs>
          <path d="M 50 95 C 50 95 12 68 12 42 C 12 24 26 14 40 14 C 47 14 53 18 57 24 C 61 18 67 14 74 14 C 88 14 92 24 92 42 C 92 68 50 95 50 95 Z"
                fill="url(#${id})" transform="translate(0, -5)"/>
          <ellipse cx="35" cy="35" rx="7" ry="5" fill="rgba(255,255,255,0.5)" opacity="0.7"/>
          <path d="M 50 95 Q 55 105 48 112" stroke="${color.to}" stroke-width="1.5" fill="none" opacity="0.6"/>
        </svg>
      `;
    }

    if (shape === 'star') {
      return `
        <svg viewBox="0 0 100 120" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <radialGradient id="${id}" cx="40%" cy="40%">
              <stop offset="0%" stop-color="${color.from}"/>
              <stop offset="100%" stop-color="${color.to}"/>
            </radialGradient>
          </defs>
          <polygon points="50,10 61,40 92,42 68,62 76,92 50,76 24,92 32,62 8,42 39,40"
                   fill="url(#${id})"/>
          <circle cx="42" cy="38" r="3" fill="rgba(255,255,255,0.6)"/>
          <path d="M 50 92 Q 55 102 48 110" stroke="${color.to}" stroke-width="1.5" fill="none" opacity="0.6"/>
        </svg>
      `;
    }

    // blob (default)
    return `
      <svg viewBox="0 0 100 120" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="${id}" cx="35%" cy="30%">
            <stop offset="0%" stop-color="${color.from}"/>
            <stop offset="100%" stop-color="${color.to}"/>
          </radialGradient>
        </defs>
        <path d="M 50 8 C 70 8 88 20 88 40 C 90 60 78 78 60 92 C 52 98 48 98 40 92 C 22 78 10 60 12 40 C 12 20 30 8 50 8 Z"
              fill="url(#${id})"/>
        <ellipse cx="38" cy="32" rx="8" ry="10" fill="rgba(255,255,255,0.5)" opacity="0.7"/>
        <path d="M 50 92 Q 55 102 48 110" stroke="${color.to}" stroke-width="1.5" fill="none" opacity="0.6"/>
      </svg>
    `;
  }

  // ============================================================
  // BALLOON CLASS
  // ============================================================
  class Balloon {
    constructor(container) {
      this.el = document.createElement('div');
      this.el.className = 'floating-balloon';

      const size = rand(CONFIG.MIN_SIZE, CONFIG.MAX_SIZE);
      const color = pick(CONFIG.COLORS);
      const shape = pick(CONFIG.SHAPES);

      this.size = size;
      this.color = color;
      this.x = rand(0, window.innerWidth - size);
      this.y = window.innerHeight + rand(50, 300);
      this.vy = -rand(CONFIG.MIN_SPEED, CONFIG.MAX_SPEED);
      this.vx = rand(-0.1, 0.1);
      this.driftPhase = rand(0, Math.PI * 2);
      this.driftSpeed = rand(CONFIG.DRIFT_SPEED * 0.5, CONFIG.DRIFT_SPEED * 1.5);
      this.rotation = rand(-8, 8);
      this.rotationSpeed = rand(-0.05, 0.05);
      this.baseX = this.x;
      this.opacity = rand(0.35, 0.7);
      this.popped = false;

      this.el.style.cssText = `
        position: absolute;
        left: 0;
        top: 0;
        width: ${size}px;
        height: ${size * 1.2}px;
        pointer-events: auto;
        cursor: pointer;
        will-change: transform;
        opacity: ${this.opacity};
        filter: drop-shadow(0 8px 20px ${color.glow});
        transition: opacity 0.4s, filter 0.4s;
      `;

      this.el.innerHTML = makeBalloonSVG(shape, color);

      // Tap/click → bật lên
      this.el.addEventListener('click', (e) => {
        e.stopPropagation();
        this.bounce();
      });

      container.appendChild(this.el);
      this.updateTransform();
    }

    bounce() {
      // Bật mạnh lên trên
      this.vy = -2.5;
      this.el.style.filter = `drop-shadow(0 0 30px ${this.color.glow}) drop-shadow(0 0 60px ${this.color.glow})`;
      this.opacity = Math.min(1, this.opacity + 0.3);
      this.el.style.opacity = this.opacity;

      setTimeout(() => {
        this.el.style.filter = `drop-shadow(0 8px 20px ${this.color.glow})`;
        this.opacity = rand(0.35, 0.7);
        this.el.style.opacity = this.opacity;
        // Reset velocity về bình thường
        this.vy = -rand(CONFIG.MIN_SPEED, CONFIG.MAX_SPEED);
      }, 800);
    }

    update(dt) {
      if (this.popped) return;

      // Vertical drift
      this.y += this.vy * dt * 60;

      // Horizontal drift (sin wave)
      this.driftPhase += this.driftSpeed * dt;
      const drift = Math.sin(this.driftPhase) * CONFIG.DRIFT_AMPLITUDE;

      // Rotation
      this.rotation += this.rotationSpeed * dt * 60;

      // Reset khi bay khỏi màn hình
      if (this.y < -this.size * 2) {
        this.reset();
      }

      this.updateTransform(drift);
    }

    updateTransform(drift = 0) {
      const currentX = this.baseX + drift;
      const currentY = this.y;

      this.el.style.transform = `
        translate3d(${currentX}px, ${currentY}px, 0)
        rotate(${this.rotation}deg)
      `;
    }

    reset() {
      this.baseX = rand(0, window.innerWidth - this.size);
      this.y = window.innerHeight + rand(50, 200);
      this.vy = -rand(CONFIG.MIN_SPEED, CONFIG.MAX_SPEED);
      this.driftPhase = rand(0, Math.PI * 2);
      this.driftSpeed = rand(CONFIG.DRIFT_SPEED * 0.5, CONFIG.DRIFT_SPEED * 1.5);
      this.rotation = rand(-8, 8);
      this.rotationSpeed = rand(-0.05, 0.05);
      this.updateTransform();
    }

    destroy() {
      this.popped = true;
      this.el.remove();
    }
  }

  // ============================================================
  // INIT
  // ============================================================
  let container = null;
  let balloons = [];
  let rafId = null;
  let lastTime = 0;
  let paused = false;

  function shouldShow() {
    // Tôn trọng prefers-reduced-motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return false;
    }
    return true;
  }

  function createContainer() {
    if (container) return container;

    container = document.createElement('div');
    container.id = 'floating-balloons-container';
    container.style.cssText = `
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 3;
      overflow: hidden;
    `;
    document.body.appendChild(container);
    return container;
  }

  function loop(timestamp) {
    if (!paused) {
      const dt = lastTime ? Math.min((timestamp - lastTime) / 1000, 0.05) : 0.016;
      lastTime = timestamp;

      balloons.forEach((b) => b.update(dt));
    } else {
      lastTime = timestamp;
    }

    rafId = requestAnimationFrame(loop);
  }

  function init() {
    if (!shouldShow()) {
      console.log('🎈 Balloons skipped (reduced motion)');
      return;
    }

    // Chỉ chạy trên page cho phép
    const allowedPages = [
      'index.html', 'marketplace.html', 'plugin.html',
      'user.html', 'author.html', 'settings.html',
      'upload.html', 'dashboard.html', 'theme-editor.html',
      '', // root
    ];
    const currentPage = location.pathname.split('/').pop() || '';
    if (!allowedPages.includes(currentPage)) return;

    createContainer();

    // Tạo balloons
    for (let i = 0; i < CONFIG.COUNT; i++) {
      setTimeout(() => {
        balloons.push(new Balloon(container));
      }, i * 400); // Stagger để tự nhiên
    }

    // Start loop
    lastTime = performance.now();
    rafId = requestAnimationFrame(loop);

    // Pause khi tab ẩn
    document.addEventListener('visibilitychange', () => {
      paused = document.hidden;
    });

    // Handle resize
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        balloons.forEach((b) => {
          if (b.baseX > window.innerWidth - b.size) {
            b.baseX = rand(0, window.innerWidth - b.size);
          }
        });
      }, 200);
    });

    console.log('🎈 Floating balloons loaded:', CONFIG.COUNT);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();