// store/web/theme-3d-scenes.js
/**
 * CogniCraft — ZOMBIE APOCALYPSE
 * Thành phố đổ nát · Trực thăng · Zombie · Quạ đen · Máu tro bay
 */
(function (global) {
  'use strict';

  const PALETTE = {
    skyTop:     '#0a0205',
    skyMid:     '#1a0a10',
    skyHoriz:   '#3a0f15',
    skyFire:    '#5a1a10',
    fire:       ['#ff2a00', '#ff6a00', '#ffb000', '#ff4400'],
    smoke:      'rgba(30, 15, 20, 0.7)',
    blood:      '#8a0a0a',
    brick:      ['#0a0508', '#12080c', '#1a0a0e', '#221015', '#2a181d'],
    moon:       '#c85a4a',
  };

  function rand(seed) {
    let s = seed;
    return () => ((s = (s * 9301 + 49297) % 233280), s / 233280);
  }

  // ============================================================
  // VẼ TÒA NHÀ ĐỔ NÁT — có cửa sổ vỡ, tường nứt
  // ============================================================
  function drawBuilding(ctx, x, y, w, h, r) {
    // Thân tòa nhà
    const grd = ctx.createLinearGradient(x, 0, x + w, 0);
    const baseColor = PALETTE.brick[Math.floor(r() * PALETTE.brick.length)];
    grd.addColorStop(0, '#050203');
    grd.addColorStop(0.5, baseColor);
    grd.addColorStop(1, '#050203');
    ctx.fillStyle = grd;
    ctx.fillRect(x, y, w, h);

    // Đường viền nứt dọc
    ctx.strokeStyle = 'rgba(0,0,0,0.5)';
    ctx.lineWidth = 0.6;
    for (let i = 0; i < 4; i++) {
      const crackX = x + r() * w;
      const crackY = y + r() * h * 0.5;
      ctx.beginPath();
      ctx.moveTo(crackX, crackY);
      ctx.lineTo(crackX + (r() - 0.5) * 15, crackY + 20 + r() * 30);
      ctx.stroke();
    }

    // Cửa sổ
    const cols = Math.max(2, Math.floor(w / 8));
    const rows = Math.max(3, Math.floor(h / 15));
    const winW = w / (cols * 2 + 1);
    const winH = h / (rows * 2 + 1);

    for (let cx = 0; cx < cols; cx++) {
      for (let cy = 0; cy < rows; cy++) {
        const wx = x + winW * (cx * 2 + 1);
        const wy = y + winH * (cy * 2 + 1);

        const state = r();
        if (state < 0.15) {
          // Cửa sổ sáng đèn (có người sống sót)
          ctx.fillStyle = `rgba(255, 200, 100, ${0.4 + r() * 0.4})`;
          ctx.fillRect(wx, wy, winW, winH);
          // Bóng người trong cửa sổ
          ctx.fillStyle = 'rgba(30, 15, 10, 0.8)';
          ctx.fillRect(wx + winW * 0.3, wy + winH * 0.3, winW * 0.4, winH * 0.7);
        } else if (state < 0.35) {
          // Cửa sổ vỡ — đen tối
          ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
          ctx.fillRect(wx, wy, winW, winH);
          // Mảnh vỡ
          ctx.strokeStyle = 'rgba(80, 40, 40, 0.6)';
          ctx.lineWidth = 0.4;
          ctx.beginPath();
          ctx.moveTo(wx, wy);
          ctx.lineTo(wx + winW * 0.5, wy + winH * 0.5);
          ctx.lineTo(wx + winW, wy);
          ctx.stroke();
        } else if (state < 0.5) {
          // Cửa sổ tối đen
          ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
          ctx.fillRect(wx, wy, winW, winH);
        }
      }
    }

    // Vệt máu chảy xuống tường
    if (r() < 0.4) {
      const bx = x + r() * w;
      const by = y + r() * h * 0.4;
      const bh = 10 + r() * 40;
      const bg = ctx.createLinearGradient(bx, by, bx, by + bh);
      bg.addColorStop(0, 'rgba(140, 20, 20, 0.7)');
      bg.addColorStop(1, 'rgba(140, 20, 20, 0)');
      ctx.fillStyle = bg;
      ctx.fillRect(bx, by, 1 + r() * 2, bh);
    }
  }

  // ============================================================
  // VẼ ZOMBIE SILHOUETTE — gù lưng, tay duỗi về trước
  // ============================================================
  function drawZombie(ctx, x, y, size, phase, dirX) {
    const s = size / 40;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(dirX * s, s);

    // Bob khi đi — lắc lư
    const bob = Math.sin(phase * 4) * 1.5;
    const legSwing = Math.sin(phase * 4);

    ctx.fillStyle = '#000';
    ctx.strokeStyle = '#000';
    ctx.lineCap = 'round';

    // Chân sau (xa, mờ hơn)
    ctx.lineWidth = 2.2;
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.6)';
    ctx.beginPath();
    ctx.moveTo(-1, 0);
    ctx.lineTo(-2 + legSwing * 3, 12);
    ctx.lineTo(-1 + legSwing * 4, 20);
    ctx.stroke();

    // Thân — gù về trước
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.ellipse(0, -8 + bob, 4, 8, -0.3, 0, Math.PI * 2);
    ctx.fill();

    // Chân trước
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(1 - legSwing * 3, 12);
    ctx.lineTo(0 - legSwing * 4, 20);
    ctx.stroke();

    // Đầu — nhô về trước
    ctx.beginPath();
    ctx.arc(3, -18 + bob, 3.5, 0, Math.PI * 2);
    ctx.fill();

    // Tay duỗi thẳng về trước (đặc trưng zombie)
    ctx.lineWidth = 2;
    ctx.beginPath();
    // Tay xa
    ctx.moveTo(2, -12 + bob);
    ctx.lineTo(12, -12 + bob + Math.sin(phase * 3) * 1);
    ctx.stroke();
    // Tay gần
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(3, -10 + bob);
    ctx.lineTo(14, -9 + bob + Math.sin(phase * 3 + 1) * 1.5);
    ctx.stroke();

    // Bàn tay — hơi cong quặp
    ctx.beginPath();
    ctx.arc(14, -9 + bob, 1.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  // ============================================================
  // VẼ QUẠ ĐEN
  // ============================================================
  function drawCrow(ctx, x, y, size, dirX, wingPhase) {
    const s = size / 40;
    const wingUp = Math.sin(wingPhase);

    ctx.save();
    ctx.translate(x, y);
    ctx.scale(dirX * s, s);

    ctx.fillStyle = '#0a0a0a';
    ctx.strokeStyle = '#0a0a0a';

    // Thân
    ctx.beginPath();
    ctx.ellipse(0, 0, 8, 3, 0, 0, Math.PI * 2);
    ctx.fill();

    // Đầu
    ctx.beginPath();
    ctx.arc(8, -1, 2.5, 0, Math.PI * 2);
    ctx.fill();

    // Mỏ nhọn
    ctx.beginPath();
    ctx.moveTo(10, -1);
    ctx.lineTo(14, 0);
    ctx.lineTo(10, 1);
    ctx.closePath();
    ctx.fill();

    // Mắt đỏ
    ctx.fillStyle = '#ff2020';
    ctx.beginPath();
    ctx.arc(8.5, -1.5, 0.5, 0, Math.PI * 2);
    ctx.fill();

    // Cánh sau (mờ)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.quadraticCurveTo(-3, -3 - wingUp * 5, -8, -4 - wingUp * 8);
    ctx.quadraticCurveTo(-6, -1 - wingUp * 3, -3, 0);
    ctx.closePath();
    ctx.fill();

    // Cánh trước — rộng
    ctx.fillStyle = '#0a0a0a';
    ctx.beginPath();
    ctx.moveTo(2, -1);
    ctx.quadraticCurveTo(-3, -5 - wingUp * 8, -12, -6 - wingUp * 14);
    ctx.quadraticCurveTo(-15, -4 - wingUp * 10, -8, -1 - wingUp * 3);
    ctx.quadraticCurveTo(-3, 0, 2, 0);
    ctx.closePath();
    ctx.fill();

    // Đuôi
    ctx.beginPath();
    ctx.moveTo(-8, 0);
    ctx.lineTo(-14, 0.5);
    ctx.lineTo(-14, 2);
    ctx.lineTo(-8, 1);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
  }

  // ============================================================
  // VẼ TRỰC THĂNG QUÂN SỰ
  // ============================================================
  function drawHelicopter(ctx, x, y, size, dirX, rotorPhase) {
    const s = size / 80;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(dirX * s, s);

    ctx.fillStyle = '#0a0a0a';

    // Thân
    ctx.beginPath();
    ctx.ellipse(0, 0, 15, 7, 0, 0, Math.PI * 2);
    ctx.fill();

    // Buồng lái (trong suốt)
    ctx.fillStyle = '#1a1a2a';
    ctx.beginPath();
    ctx.ellipse(10, 0, 6, 6, 0, 0, Math.PI * 2);
    ctx.fill();

    // Kính buồng lái viền
    ctx.strokeStyle = 'rgba(80, 100, 120, 0.6)';
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.arc(10, 0, 6, 0, Math.PI * 2);
    ctx.stroke();

    // Đuôi
    ctx.fillStyle = '#0a0a0a';
    ctx.beginPath();
    ctx.moveTo(-13, -3);
    ctx.lineTo(-30, -3);
    ctx.lineTo(-32, -1);
    ctx.lineTo(-30, 1);
    ctx.lineTo(-13, 2);
    ctx.closePath();
    ctx.fill();

    // Cánh quạt đuôi (quay)
    ctx.save();
    ctx.translate(-31, -1);
    ctx.rotate(rotorPhase * 8);
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(-3, 0);
    ctx.lineTo(3, 0);
    ctx.stroke();
    ctx.restore();

    // Cánh quạt chính (quay nhanh — vẽ mờ)
    ctx.save();
    ctx.translate(0, -8);
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.4)';
    ctx.lineWidth = 1.5;
    const bladeCount = 4;
    for (let i = 0; i < bladeCount; i++) {
      const a = rotorPhase * 15 + (i * Math.PI * 2) / bladeCount;
      ctx.save();
      ctx.rotate(a);
      ctx.beginPath();
      ctx.moveTo(-22, 0);
      ctx.lineTo(22, 0);
      ctx.stroke();
      ctx.restore();
    }
    ctx.restore();

    // Chân đáp
    ctx.strokeStyle = '#0a0a0a';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(-8, 6);
    ctx.lineTo(-12, 10);
    ctx.moveTo(8, 6);
    ctx.lineTo(12, 10);
    ctx.stroke();

    ctx.restore();
  }

  // ============================================================
  // VẼ LỬA CHÁY
  // ============================================================
  function drawFire(ctx, x, y, size, phase) {
    const flicker = 0.85 + Math.sin(phase * 8) * 0.15;

    // Outer glow
    const glow = ctx.createRadialGradient(x, y, 0, x, y, size * 3);
    glow.addColorStop(0, 'rgba(255, 100, 0, 0.5)');
    glow.addColorStop(0.4, 'rgba(255, 60, 0, 0.2)');
    glow.addColorStop(1, 'rgba(255, 60, 0, 0)');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, size * 3, 0, Math.PI * 2);
    ctx.fill();

    // Flame shape
    ctx.fillStyle = '#ff4400';
    ctx.beginPath();
    ctx.moveTo(x - size * 0.6, y);
    ctx.quadraticCurveTo(
      x - size * 0.5, y - size * 1.4 * flicker,
      x, y - size * 2 * flicker
    );
    ctx.quadraticCurveTo(
      x + size * 0.5, y - size * 1.4 * flicker,
      x + size * 0.6, y
    );
    ctx.closePath();
    ctx.fill();

    // Inner hot core
    ctx.fillStyle = '#ffb000';
    ctx.beginPath();
    ctx.moveTo(x - size * 0.3, y);
    ctx.quadraticCurveTo(
      x - size * 0.2, y - size * 0.9 * flicker,
      x, y - size * 1.2 * flicker
    );
    ctx.quadraticCurveTo(
      x + size * 0.2, y - size * 0.9 * flicker,
      x + size * 0.3, y
    );
    ctx.closePath();
    ctx.fill();
  }

  // ============================================================
  // VẼ TÒA NHÀ SKYLINE LAYER
  // ============================================================
  function drawCityLayer(ctx, w, h, opts) {
    const { seed, baseY, maxH, minW, maxW, color } = opts;
    const r = rand(seed);

    let x = 0;
    while (x < w) {
      const bw = minW + r() * (maxW - minW);
      const bh = 40 + r() * maxH;
      drawBuilding(ctx, x, baseY - bh, bw, bh, r);
      // Khoảng trống giữa tòa nhà
      x += bw + r() * 15;
    }

    // Silhouette overlay (làm tối)
    ctx.fillStyle = `rgba(0, 0, 0, ${color})`;
    ctx.fillRect(0, baseY - maxH, w, maxH + 100);
  }

  // ============================================================
  // SCENE
  // ============================================================
  const scene_zombie = {
    id: 'zombie_apocalypse',
    name: 'Zombie Apocalypse',
    icon: '🧟',
    description: 'Thành phố đổ nát · Trực thăng · Zombie · Máu tro bay',
    configSchema: [
      { key: 'zombies', label: 'Số zombie', type: 'range', min: 5,  max: 50, default: 15 },
      { key: 'crows',   label: 'Số quạ',    type: 'range', min: 3,  max: 30, default: 12 },
      { key: 'speed',   label: 'Tốc độ',    type: 'range', min: 0.3, max: 2,  default: 1 },
    ],

    init(canvas, config) {
      const ctx = canvas.getContext('2d');
      const speed = config.speed ?? 1;
      const zombieCount = config.zombies ?? 15;
      const crowCount = config.crows ?? 12;

      let W = window.innerWidth;
      let H = window.innerHeight;
      const DPR = Math.min(window.devicePixelRatio || 1, 2);

      function resize() {
        W = window.innerWidth;
        H = window.innerHeight;
        canvas.width = W * DPR;
        canvas.height = H * DPR;
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(DPR, DPR);
      }
      resize();

      // ============================================================
      // LAYER CACHE
      // ============================================================
      let layerCache = [];
      let fires = []; // vị trí lửa cháy

      function buildCache() {
        layerCache = [];
        fires = [];

        // ---- SKY ----
        const sky = document.createElement('canvas');
        sky.width = W; sky.height = H;
        const sctx = sky.getContext('2d');
        const grd = sctx.createLinearGradient(0, 0, 0, H);
        grd.addColorStop(0, PALETTE.skyTop);
        grd.addColorStop(0.4, PALETTE.skyMid);
        grd.addColorStop(0.7, PALETTE.skyHoriz);
        grd.addColorStop(0.85, PALETTE.skyFire);
        grd.addColorStop(1, '#2a0510');
        sctx.fillStyle = grd;
        sctx.fillRect(0, 0, W, H);

        // Mặt trời máu (đỏ, mờ)
        const sunX = W * 0.72;
        const sunY = H * 0.32;
        const sunR = Math.min(W, H) * 0.08;
        const sunHalo = sctx.createRadialGradient(sunX, sunY, sunR * 0.5, sunX, sunY, sunR * 6);
        sunHalo.addColorStop(0, 'rgba(255, 80, 40, 0.5)');
        sunHalo.addColorStop(0.3, 'rgba(200, 40, 20, 0.25)');
        sunHalo.addColorStop(0.6, 'rgba(140, 20, 10, 0.08)');
        sunHalo.addColorStop(1, 'rgba(140, 20, 10, 0)');
        sctx.fillStyle = sunHalo;
        sctx.beginPath();
        sctx.arc(sunX, sunY, sunR * 6, 0, Math.PI * 2);
        sctx.fill();

        // Sun body
        const sunBody = sctx.createRadialGradient(
          sunX - sunR * 0.3, sunY - sunR * 0.3, 0,
          sunX, sunY, sunR
        );
        sunBody.addColorStop(0, '#ffa090');
        sunBody.addColorStop(0.5, '#d04030');
        sunBody.addColorStop(1, '#8a2010');
        sctx.fillStyle = sunBody;
        sctx.beginPath();
        sctx.arc(sunX, sunY, sunR, 0, Math.PI * 2);
        sctx.fill();

        // Vệt mây đen ngang
        for (let i = 0; i < 15; i++) {
          const cx = Math.random() * W;
          const cy = H * 0.15 + Math.random() * H * 0.4;
          const cw = 100 + Math.random() * 300;
          const ch = 20 + Math.random() * 30;
          const cg = sctx.createRadialGradient(cx, cy, 0, cx, cy, cw);
          cg.addColorStop(0, `rgba(20, 5, 10, ${0.3 + Math.random() * 0.3})`);
          cg.addColorStop(1, 'rgba(20, 5, 10, 0)');
          sctx.fillStyle = cg;
          sctx.fillRect(cx - cw, cy - ch, cw * 2, ch * 2);
        }

        layerCache.push({ canvas: sky, parallax: 0.02 });

        // ---- STARS mờ ----
        const stars = document.createElement('canvas');
        stars.width = W; stars.height = H;
        const stctx = stars.getContext('2d');
        for (let i = 0; i < 80; i++) {
          const sx = Math.random() * W;
          const sy = Math.random() * H * 0.4;
          const sr = 0.3 + Math.random() * 0.8;
          stctx.fillStyle = `rgba(200, 180, 180, ${0.2 + Math.random() * 0.4})`;
          stctx.beginPath();
          stctx.arc(sx, sy, sr, 0, Math.PI * 2);
          stctx.fill();
        }
        layerCache.push({ canvas: stars, parallax: 0.03, twinkle: true });

        // ---- CITY FAR (xa, mờ) ----
        const farCity = document.createElement('canvas');
        farCity.width = W; farCity.height = H;
        const fcCtx = farCity.getContext('2d');
        drawCityLayer(fcCtx, W, H, {
          seed: 1.2,
          baseY: H * 0.72,
          maxH: H * 0.35,
          minW: 25,
          maxW: 60,
          color: 0.65,
        });
        layerCache.push({ canvas: farCity, parallax: 0.08 });

        // ---- CITY MID ----
        const midCity = document.createElement('canvas');
        midCity.width = W; midCity.height = H;
        const mcCtx = midCity.getContext('2d');
        drawCityLayer(mcCtx, W, H, {
          seed: 3.7,
          baseY: H * 0.82,
          maxH: H * 0.42,
          minW: 40,
          maxW: 90,
          color: 0.4,
        });
        layerCache.push({ canvas: midCity, parallax: 0.15 });

        // ---- CITY NEAR (gần, rõ nét) ----
        const nearCity = document.createElement('canvas');
        nearCity.width = W; nearCity.height = H;
        const ncCtx = nearCity.getContext('2d');
        drawCityLayer(ncCtx, W, H, {
          seed: 5.9,
          baseY: H * 0.95,
          maxH: H * 0.4,
          minW: 60,
          maxW: 130,
          color: 0.1,
        });
        layerCache.push({ canvas: nearCity, parallax: 0.22 });

        // ---- GROUND (đường phố vỡ) ----
        const ground = document.createElement('canvas');
        ground.width = W; ground.height = H;
        const gctx = ground.getContext('2d');
        // Nền đường
        const gg = gctx.createLinearGradient(0, H * 0.92, 0, H);
        gg.addColorStop(0, '#1a0a0e');
        gg.addColorStop(1, '#050203');
        gctx.fillStyle = gg;
        gctx.fillRect(0, H * 0.92, W, H * 0.08);

        // Đường nứt
        gctx.strokeStyle = 'rgba(0,0,0,0.9)';
        gctx.lineWidth = 1;
        for (let i = 0; i < 30; i++) {
          const cx = Math.random() * W;
          const cy = H * 0.92 + Math.random() * H * 0.08;
          gctx.beginPath();
          gctx.moveTo(cx, cy);
          gctx.lineTo(cx + (Math.random() - 0.5) * 40, cy + (Math.random() - 0.5) * 10);
          gctx.stroke();
        }
        // Vệt máu dưới đường
        for (let i = 0; i < 8; i++) {
          const bx = Math.random() * W;
          const by = H * 0.94;
          const bg = gctx.createRadialGradient(bx, by, 0, bx, by, 20 + Math.random() * 30);
          bg.addColorStop(0, 'rgba(140, 10, 10, 0.6)');
          bg.addColorStop(1, 'rgba(140, 10, 10, 0)');
          gctx.fillStyle = bg;
          gctx.beginPath();
          gctx.arc(bx, by, 30, 0, Math.PI * 2);
          gctx.fill();
        }
        layerCache.push({ canvas: ground, parallax: 0.28 });

        // ---- SINH VỊ TRÍ LỬA CHÁY (trên các tòa nhà) ----
        const numFires = 5 + Math.floor(Math.random() * 3);
        for (let i = 0; i < numFires; i++) {
          fires.push({
            x: 50 + Math.random() * (W - 100),
            y: H * (0.65 + Math.random() * 0.25),
            size: 8 + Math.random() * 12,
            phase: Math.random() * Math.PI * 2,
          });
        }
      }
      buildCache();

      // ============================================================
      // ZOMBIES — đi lang thang dưới đất
      // ============================================================
      const zombies = [];
      for (let i = 0; i < zombieCount; i++) {
        const layerZ = Math.random();
        zombies.push({
          x: Math.random() * W,
          y: H * 0.94 + layerZ * 15,
          size: 25 + layerZ * 15, // xa nhỏ, gần to
          speed: (10 + Math.random() * 15) * speed * (Math.random() > 0.5 ? 1 : -1),
          phase: Math.random() * Math.PI * 2,
          layer: layerZ,
        });
      }

      // ============================================================
      // CROWS — quạ bay
      // ============================================================
      const crows = [];
      for (let i = 0; i < crowCount; i++) {
        crows.push({
          x: Math.random() * W * 1.5 - W * 0.25,
          y: H * 0.1 + Math.random() * H * 0.4,
          size: 20 + Math.random() * 20,
          speedX: (40 + Math.random() * 50) * speed * (Math.random() > 0.3 ? 1 : -1),
          bobPhase: Math.random() * Math.PI * 2,
          bobSpeed: 0.8 + Math.random() * 0.6,
          wingPhase: Math.random() * Math.PI * 2,
          wingSpeed: 4 + Math.random() * 2,
          layerIdx: 1 + Math.random() * 2,
        });
      }

      // ============================================================
      // HELICOPTER — trực thăng bay qua
      // ============================================================
      const heli = {
        x: -200,
        y: H * 0.15 + Math.random() * 50,
        speed: 40 * speed,
        rotorPhase: 0,
        dirX: 1,
        active: true,
        respawnTimer: 0,
      };

      // ============================================================
      // EMBERS — tro/máu bay
      // ============================================================
      const embers = [];
      for (let i = 0; i < 80; i++) {
        embers.push({
          x: Math.random() * W,
          y: Math.random() * H,
          vx: -10 - Math.random() * 20,
          vy: -5 - Math.random() * 15,
          size: 0.5 + Math.random() * 1.5,
          color: Math.random() < 0.6 ? '#ff6030' : '#8a1010',
          life: 1,
        });
      }

      // ============================================================
      // MOUSE
      // ============================================================
      const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
      const onMove = (e) => {
        mouse.tx = (e.clientX / W - 0.5) * 2;
        mouse.ty = (e.clientY / H - 0.5) * 2;
      };
      window.addEventListener('mousemove', onMove);

      const onResize = () => { resize(); buildCache(); };
      window.addEventListener('resize', onResize);

      // ============================================================
      // ANIMATE
      // ============================================================
      let t = 0;
      let raf;

      function animate() {
        t += 0.016 * speed;

        mouse.x += (mouse.tx - mouse.x) * 0.04;
        mouse.y += (mouse.ty - mouse.y) * 0.04;

        // ============================================================
        // BG LAYERS
        // ============================================================
        ctx.fillStyle = '#050203';
        ctx.fillRect(0, 0, W, H);

        layerCache.forEach((layer) => {
          const px = -mouse.x * layer.parallax * 60;
          const py = -mouse.y * layer.parallax * 30;
          if (layer.twinkle) {
            ctx.globalAlpha = 0.7 + Math.sin(t * 3) * 0.3;
          }
          ctx.drawImage(layer.canvas, px, py);
        });
        ctx.globalAlpha = 1;

        // ============================================================
        // FIRES — lửa cháy trên tòa nhà
        // ============================================================
        fires.forEach((f) => {
          const px = -mouse.x * 0.2 * 60;
          const py = -mouse.y * 0.2 * 30;
          drawFire(ctx, f.x + px, f.y + py, f.size, t + f.phase);
        });

        // ============================================================
        // SMOKE — khói từ lửa cuồn lên
        // ============================================================
        fires.forEach((f) => {
          const px = -mouse.x * 0.2 * 60;
          const py = -mouse.y * 0.2 * 30;
          for (let i = 0; i < 3; i++) {
            const smokeT = (t * 0.3 + f.phase * 0.1 + i * 0.5) % 1;
            const smokeY = f.y + py - smokeT * 200;
            const smokeX = f.x + px + Math.sin(t * 0.5 + i + f.phase) * 30;
            const smokeR = 30 + smokeT * 60;
            const sa = (1 - smokeT) * 0.4;

            const sg = ctx.createRadialGradient(smokeX, smokeY, 0, smokeX, smokeY, smokeR);
            sg.addColorStop(0, `rgba(40, 20, 20, ${sa})`);
            sg.addColorStop(1, 'rgba(40, 20, 20, 0)');
            ctx.fillStyle = sg;
            ctx.beginPath();
            ctx.arc(smokeX, smokeY, smokeR, 0, Math.PI * 2);
            ctx.fill();
          }
        });

        // ============================================================
        // HELICOPTER
        // ============================================================
        heli.x += heli.speed * 0.016;
        heli.rotorPhase += 0.5;

        // Searchlight dưới trực thăng
        if (heli.x > -100 && heli.x < W + 100) {
          const slAngle = Math.sin(t * 0.8) * 0.3;
          const slLength = 350;
          const slX = heli.x + Math.sin(slAngle) * slLength;
          const slY = heli.y + Math.cos(slAngle) * slLength * 2;

          ctx.save();
          ctx.globalCompositeOperation = 'lighter';
          const slGrd = ctx.createLinearGradient(heli.x, heli.y, slX, slY);
          slGrd.addColorStop(0, 'rgba(255, 255, 200, 0.35)');
          slGrd.addColorStop(0.5, 'rgba(255, 255, 150, 0.15)');
          slGrd.addColorStop(1, 'rgba(255, 255, 100, 0)');

          ctx.fillStyle = slGrd;
          ctx.beginPath();
          ctx.moveTo(heli.x - 10, heli.y + 5);
          ctx.lineTo(heli.x + 10, heli.y + 5);
          ctx.lineTo(slX + 80, slY);
          ctx.lineTo(slX - 80, slY);
          ctx.closePath();
          ctx.fill();
          ctx.restore();
        }

        drawHelicopter(ctx, heli.x, heli.y, 80, 1, heli.rotorPhase);

        // Reset khi bay ra ngoài
        if (heli.x > W + 300) {
          heli.x = -300;
          heli.y = H * 0.1 + Math.random() * 100;
        }

        // ============================================================
        // CROWS
        // ============================================================
        crows.forEach((crow) => {
          crow.x += crow.speedX * 0.016;
          crow.wingPhase += crow.wingSpeed * 0.016;

          if (crow.speedX > 0 && crow.x > W + 100) crow.x = -100;
          if (crow.speedX < 0 && crow.x < -100) crow.x = W + 100;

          const yBob = Math.sin(t * crow.bobSpeed + crow.bobPhase) * 8;
          const parallaxX = -mouse.x * crow.layerIdx * 8;
          const parallaxY = -mouse.y * crow.layerIdx * 4;

          drawCrow(
            ctx,
            crow.x + parallaxX,
            crow.y + yBob + parallaxY,
            crow.size,
            crow.speedX,
            crow.wingPhase
          );
        });

        // ============================================================
        // ZOMBIES
        // ============================================================
        zombies.forEach((z) => {
          z.x += z.speed * 0.016;

          if (z.speed > 0 && z.x > W + 50) z.x = -50;
          if (z.speed < 0 && z.x < -50) z.x = W + 50;

          const parallaxX = -mouse.x * (0.28 + z.layer * 0.1) * 20;
          const parallaxY = -mouse.y * (0.28 + z.layer * 0.1) * 10;

          drawZombie(
            ctx,
            z.x + parallaxX,
            z.y + parallaxY,
            z.size,
            t + z.phase,
            z.speed > 0 ? 1 : -1
          );
        });

        // ============================================================
        // EMBERS — tro bay
        // ============================================================
        embers.forEach((e) => {
          e.x += e.vx * 0.016;
          e.y += e.vy * 0.016;

          // Wrap
          if (e.x < -20) {
            e.x = W + 20;
            e.y = Math.random() * H;
          }
          if (e.y < -20) {
            e.y = H + 20;
          }

          // Fade
          e.life = Math.min(1, e.life + 0.005);

          const px = -mouse.x * 40;
          const py = -mouse.y * 20;

          ctx.fillStyle = e.color;
          ctx.globalAlpha = e.life * (0.6 + Math.sin(t * 5 + e.x) * 0.3);
          ctx.shadowColor = e.color;
          ctx.shadowBlur = 8;
          ctx.beginPath();
          ctx.arc(e.x + px, e.y + py, e.size, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
          ctx.globalAlpha = 1;
        });

        // ============================================================
        // VIGNETTE — làm tối viền
        // ============================================================
        const vg = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.3, W / 2, H / 2, Math.max(W, H) * 0.7);
        vg.addColorStop(0, 'rgba(0, 0, 0, 0)');
        vg.addColorStop(1, 'rgba(0, 0, 0, 0.6)');
        ctx.fillStyle = vg;
        ctx.fillRect(0, 0, W, H);

        // ============================================================
        // CẢNH BÁO NHẤP NHÁY — góc trên
        // ============================================================
        const alertAlpha = 0.5 + Math.sin(t * 3) * 0.5;
        if (alertAlpha > 0.7) {
          ctx.save();
          ctx.globalAlpha = (alertAlpha - 0.7) / 0.3;
          ctx.fillStyle = '#ff2020';
          ctx.shadowColor = '#ff2020';
          ctx.shadowBlur = 20;
          ctx.font = 'bold 14px system-ui, sans-serif';
          ctx.textAlign = 'right';
          ctx.fillText('⚠ OUTBREAK ALERT', W - 30, 40);
          ctx.restore();
        }

        raf = requestAnimationFrame(animate);
      }
      animate();

      // ============================================================
      // CLEANUP
      // ============================================================
      return () => {
        cancelAnimationFrame(raf);
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('resize', onResize);
      };
    },
  };

  // ============================================================
  // REGISTRY
  // ============================================================
  global.CogniScenes = {
    zombie_apocalypse: scene_zombie,
    list() { return [this.zombie_apocalypse]; },
    get(id) { return this[id] || null; },
  };

  console.log('🧟 Zombie Apocalypse registered');
})(window);