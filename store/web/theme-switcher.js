// ============================================================
// COGNICRAFT STORE - THEME SWITCHER v5 (VIP EDITION)
// Theme + Sakura + Cyberpunk scene + Cursor trail + Ripple
// ============================================================
(function () {
    'use strict';

    const THEMES = [
        { id: 'auto-light', name: 'Auto',      icon: '🌗' },
        { id: 'cyberpunk',  name: 'Cyberpunk', icon: '🌃' },
        { id: 'matrix',     name: 'Matrix',    icon: '🟢' },
        { id: 'vaporwave',  name: 'Vaporwave', icon: '🌸' },
        { id: 'terminal',   name: 'Terminal',  icon: '📟' },
        { id: 'nord',       name: 'Nord',      icon: '❄️' },
        { id: 'solarized',  name: 'Solarized', icon: '☀️' },
        { id: 'auto-dark',  name: 'Dark',      icon: '🌙' },
    ];

    const STORAGE_KEY = 'cognicraft-theme';
    const DEFAULT_THEME = 'cyberpunk';

    // ============================================================
    // THEME STATE
    // ============================================================
    function getSavedTheme() {
        try { return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME; }
        catch (e) { return DEFAULT_THEME; }
    }

    function setTheme(id) {
        document.documentElement.setAttribute('data-theme', id);
        try { localStorage.setItem(STORAGE_KEY, id); } catch (e) {}
    }

    function currentTheme() {
        return document.documentElement.getAttribute('data-theme') || DEFAULT_THEME;
    }

    // Apply ngay lập tức
    setTheme(getSavedTheme());

    // ============================================================
    // CURSOR TRAIL (chỉ Cyberpunk + Vaporwave)
    // ============================================================
    function initCursorTrail() {
        const trail = [];
        const MAX = 12;
        let lastX = 0, lastY = 0, lastTime = 0;

        document.addEventListener('mousemove', (e) => {
            const theme = currentTheme();
            if (theme !== 'cyberpunk' && theme !== 'vaporwave') return;

            const now = Date.now();
            if (now - lastTime < 30) return;
            lastTime = now;

            const dist = Math.hypot(e.clientX - lastX, e.clientY - lastY);
            if (dist < 8) return;
            lastX = e.clientX;
            lastY = e.clientY;

            const dot = document.createElement('div');
            dot.className = `cursor-trail cursor-trail-${theme}`;
            dot.style.left = e.clientX + 'px';
            dot.style.top = e.clientY + 'px';
            document.body.appendChild(dot);
            trail.push(dot);

            setTimeout(() => dot.classList.add('fade'), 100);
            setTimeout(() => { dot.remove(); trail.shift(); }, 800);

            if (trail.length > MAX) {
                const old = trail.shift();
                if (old) old.remove();
            }
        });
    }

    // ============================================================
    // CLICK RIPPLE
    // ============================================================
    function initRipple() {
        document.addEventListener('click', (e) => {
            const theme = currentTheme();
            const colors = {
                cyberpunk: 'rgba(0, 255, 249, 0.6)',
                matrix:    'rgba(0, 255, 65, 0.6)',
                vaporwave: 'rgba(255, 113, 206, 0.6)',
                terminal:  'rgba(255, 176, 0, 0.6)',
                nord:      'rgba(136, 192, 208, 0.5)',
                solarized: 'rgba(38, 139, 210, 0.5)',
            };
            const color = colors[theme] || 'rgba(255, 255, 255, 0.4)';

            const ripple = document.createElement('div');
            ripple.className = 'click-ripple';
            ripple.style.left = e.clientX + 'px';
            ripple.style.top = e.clientY + 'px';
            ripple.style.borderColor = color;
            ripple.style.boxShadow = `0 0 20px ${color}`;
            document.body.appendChild(ripple);

            setTimeout(() => ripple.remove(), 800);
        });
    }

    // ============================================================
    // 3D TILT cho plugin card
    // ============================================================
    function initCardTilt() {
        document.addEventListener('mousemove', (e) => {
            const card = e.target.closest('.plugin-card');
            if (!card) return;

            const rect = card.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width - 0.5;
            const y = (e.clientY - rect.top) / rect.height - 0.5;

            card.style.transform = `
                perspective(1000px)
                rotateY(${x * 8}deg)
                rotateX(${-y * 8}deg)
                translateY(-4px)
                scale(1.01)
            `;

            // Spotlight effect
            const px = (e.clientX - rect.left);
            const py = (e.clientY - rect.top);
            card.style.setProperty('--mx', px + 'px');
            card.style.setProperty('--my', py + 'px');
        });

        document.addEventListener('mouseleave', (e) => {
            const card = e.target.closest && e.target.closest('.plugin-card');
            if (card) card.style.transform = '';
        }, true);
    }

    // ============================================================
    // PARALLAX theo chuột (Cyberpunk scene)
    // ============================================================
    function initParallax() {
        document.addEventListener('mousemove', (e) => {
            if (currentTheme() !== 'cyberpunk') return;

            const cx = (e.clientX / window.innerWidth - 0.5) * 2;
            const cy = (e.clientY / window.innerHeight - 0.5) * 2;

            const far = document.querySelector('.cyber-layer-far');
            const mid = document.querySelector('.cyber-layer-mid');
            const near = document.querySelector('.cyber-layer-near');
            const moon = document.querySelector('.cyber-moon');

            if (far) far.style.transform = `translate(${cx * -6}px, ${cy * -4}px)`;
            if (mid) mid.style.transform = `translate(${cx * -12}px, ${cy * -6}px)`;
            if (near) near.style.transform = `translate(${cx * -20}px, ${cy * -8}px)`;
            if (moon) moon.style.transform = `translate(${cx * 15}px, ${cy * 10}px)`;
        });
    }

    // ============================================================
    // CYBERPUNK SCENE
    // ============================================================
    function makeSkyline(opts) {
        const {
            count = 30, minW = 40, maxW = 120, minH = 80, maxH = 280,
            viewW = 1600, viewH = 300,
            bodyTop = '#0a1018', bodyBot = '#050810',
            winColors = ['#00fff9', '#ff2b5e', '#b537f2', '#ffb000'],
            winOpacity = 0.75, antennaChance = 0.4,
            billboardChance = 0.15,
            billboardTexts = ['15 OKA', 'ORBITAL', '2077', 'NEON'],
            id = 'lyr',
        } = opts;

        let svg = `<svg viewBox="0 0 ${viewW} ${viewH}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">`;

        // Defs
        svg += `<defs>
            <linearGradient id="bg-${id}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="${bodyTop}"/>
                <stop offset="100%" stop-color="${bodyBot}"/>
            </linearGradient>`;
        winColors.forEach((c, i) => {
            svg += `<pattern id="w-${id}-${i}" width="10" height="14" patternUnits="userSpaceOnUse">
                <rect width="10" height="14" fill="transparent"/>
                <rect x="2" y="3" width="3" height="5" fill="${c}" opacity="${winOpacity}"/>
                <rect x="7" y="7" width="2" height="4" fill="${c}" opacity="${winOpacity * 0.5}"/>
            </pattern>`;
        });
        svg += `</defs>`;

        // Buildings
        let x = -20;
        for (let i = 0; i < count; i++) {
            const w = minW + Math.random() * (maxW - minW);
            const h = minH + Math.random() * (maxH - minH);
            const y = viewH - h;
            if (x + w > viewW + 20) break;

            svg += `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="url(#bg-${id})" stroke="${bodyTop}" stroke-width="0.5"/>`;

            const winIdx = Math.floor(Math.random() * winColors.length);
            svg += `<rect x="${x + 3}" y="${y + 5}" width="${w - 6}" height="${h - 8}" fill="url(#w-${id}-${winIdx})"/>`;
            svg += `<rect x="${x}" y="${y}" width="${w}" height="2" fill="${winColors[winIdx]}" opacity="0.5"/>`;

            if (Math.random() < antennaChance) {
                const ax = x + w / 2;
                const ah = 15 + Math.random() * 30;
                svg += `<line x1="${ax}" y1="${y}" x2="${ax}" y2="${y - ah}" stroke="${bodyTop}" stroke-width="1.5"/>`;
                svg += `<circle cx="${ax}" cy="${y - ah}" r="1.8" fill="#ff2b5e">
                    <animate attributeName="opacity" values="1;0.2;1" dur="1.5s" repeatCount="indefinite"/>
                </circle>`;
            }

            if (Math.random() < billboardChance) {
                const bw = w * 0.7, bh = 22;
                const bx = x + (w - bw) / 2, by = y - bh - 5;
                const txt = billboardTexts[Math.floor(Math.random() * billboardTexts.length)];
                const bc = winColors[Math.floor(Math.random() * winColors.length)];
                svg += `<rect x="${bx}" y="${by}" width="${bw}" height="${bh}" fill="${bc}" opacity="0.85" rx="1"/>`;
                svg += `<text x="${bx + bw / 2}" y="${by + bh / 2 + 4}" font-family="Orbitron, sans-serif" font-size="9" font-weight="900" fill="#000" text-anchor="middle" letter-spacing="1">${txt}</text>`;
            }

            x += w + 2 + Math.random() * 4;
        }

        svg += `</svg>`;
        return svg;
    }

    function spawnCyberpunk() {
        const container = document.getElementById('cyberpunk-scene');
        if (!container) return;
        container.innerHTML = '';
        if (currentTheme() !== 'cyberpunk') return;

        // SKY
        const sky = document.createElement('div');
        sky.className = 'cyber-sky';
        const moon = document.createElement('div');
        moon.className = 'cyber-moon';
        sky.appendChild(moon);
        container.appendChild(sky);

        // FAR skyline
        const far = document.createElement('div');
        far.className = 'cyber-layer cyber-layer-far';
        far.innerHTML = makeSkyline({
            count: 40, minW: 30, maxW: 70, minH: 60, maxH: 180,
            bodyTop: '#0d1a28', bodyBot: '#050810',
            winColors: ['#00fff9', '#ff2b5e', '#b537f2'],
            winOpacity: 0.5, antennaChance: 0.2, billboardChance: 0.05,
            id: 'far',
        });
        container.appendChild(far);

        // MID skyline
        const mid = document.createElement('div');
        mid.className = 'cyber-layer cyber-layer-mid';
        mid.innerHTML = makeSkyline({
            count: 30, minW: 50, maxW: 110, minH: 100, maxH: 260,
            bodyTop: '#0a141f', bodyBot: '#03060b',
            winColors: ['#00fff9', '#ff2b5e', '#b537f2', '#ffb000', '#ffffff'],
            winOpacity: 0.85, antennaChance: 0.5, billboardChance: 0.2,
            billboardTexts: ['15 OKA', 'ORBITAL AIR', 'FEEL FREE', '2077', 'NEON', '覚醒'],
            id: 'mid',
        });
        container.appendChild(mid);

        // Floating billboards
        const bb = document.createElement('div');
        bb.className = 'cyber-billboards';
        bb.innerHTML = `
            <div class="billboard billboard-1">NEON CITY</div>
            <div class="billboard billboard-2">覚醒</div>
            <div class="billboard billboard-3">ORBITAL AIR</div>
        `;
        container.appendChild(bb);

        // Rain
        const rain = document.createElement('div');
        rain.className = 'cyber-rain';
        for (let i = 0; i < 50; i++) {
            const d = document.createElement('div');
            d.className = 'rain-drop' + (Math.random() > 0.7 ? ' pink' : '');
            d.style.left = `${Math.random() * 100}%`;
            d.style.animationDuration = `${0.6 + Math.random() * 0.8}s`;
            d.style.animationDelay = `${Math.random() * -2}s`;
            d.style.opacity = 0.3 + Math.random() * 0.5;
            rain.appendChild(d);
        }
        container.appendChild(rain);

        // Near skyline
        const near = document.createElement('div');
        near.className = 'cyber-layer cyber-layer-near';
        near.innerHTML = `
            <svg viewBox="0 0 1600 300" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
                <g fill="#000">
                    <rect x="0" y="180" width="120" height="120"/>
                    <rect x="110" y="140" width="90" height="160"/>
                    <rect x="195" y="200" width="140" height="100"/>
                    <rect x="320" y="160" width="80" height="140"/>
                    <rect x="1350" y="150" width="100" height="150"/>
                    <rect x="1440" y="190" width="160" height="110"/>
                </g>
                <g opacity="0.9">
                    <rect x="130" y="160" width="3" height="5" fill="#ff2b5e"/>
                    <rect x="150" y="180" width="3" height="5" fill="#00fff9"/>
                    <rect x="170" y="200" width="3" height="5" fill="#ffb000"/>
                    <rect x="220" y="220" width="3" height="5" fill="#00fff9"/>
                    <rect x="1380" y="170" width="3" height="5" fill="#00fff9"/>
                    <rect x="1480" y="210" width="3" height="5" fill="#ff2b5e"/>
                </g>
            </svg>
        `;
        container.appendChild(near);

        // Overpass
        const op = document.createElement('div');
        op.className = 'cyber-overpass';
        op.innerHTML = `
            <svg viewBox="0 0 1600 300" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="op-g" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#0a0e15"/>
                        <stop offset="100%" stop-color="#000"/>
                    </linearGradient>
                    <linearGradient id="nl" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stop-color="#ff2b5e" stop-opacity="0.2"/>
                        <stop offset="50%" stop-color="#ff2b5e" stop-opacity="1"/>
                        <stop offset="100%" stop-color="#ff2b5e" stop-opacity="0.2"/>
                    </linearGradient>
                </defs>
                <path d="M 900 300 Q 950 240 1050 230 L 1600 210 L 1600 300 Z" fill="url(#op-g)" stroke="#1a2433" stroke-width="1"/>
                <path d="M 950 245 Q 1000 240 1080 232 L 1600 212" fill="none" stroke="url(#nl)" stroke-width="3" style="filter: drop-shadow(0 0 8px #ff2b5e)"/>
                <rect x="1080" y="230" width="12" height="70" fill="#030608" stroke="#1a2433" stroke-width="0.5"/>
                <rect x="1320" y="220" width="14" height="80" fill="#030608" stroke="#1a2433" stroke-width="0.5"/>
                <rect x="1082" y="240" width="3" height="40" fill="#ff2b5e" opacity="0.9" style="filter: drop-shadow(0 0 6px #ff2b5e)"/>
                <rect x="1324" y="230" width="3" height="45" fill="#ff2b5e" opacity="0.9" style="filter: drop-shadow(0 0 6px #ff2b5e)"/>
                <g transform="translate(120, 250)">
                    <path d="M 0 0 L 20 -10 L 20 10 Z" fill="#ffb000" style="filter: drop-shadow(0 0 8px #ffb000)"/>
                    <path d="M 30 0 L 50 -10 L 50 10 Z" fill="#ffb000" style="filter: drop-shadow(0 0 8px #ffb000)"/>
                    <path d="M 60 0 L 80 -10 L 80 10 Z" fill="#ffb000" style="filter: drop-shadow(0 0 8px #ffb000)"/>
                </g>
                <g transform="translate(1200, 130)">
                    <rect x="0" y="0" width="80" height="100" fill="#ff0066" opacity="0.85" rx="2" style="filter: drop-shadow(0 0 15px #ff0066)"/>
                    <text x="40" y="55" font-family="Orbitron, sans-serif" font-size="14" font-weight="900" fill="#fff" text-anchor="middle" letter-spacing="2">街</text>
                </g>
                <g transform="translate(1150, 170)">
                    <rect x="0" y="0" width="140" height="20" fill="#00fff9" opacity="0.9" rx="1" style="filter: drop-shadow(0 0 10px #00fff9)"/>
                    <text x="70" y="14" font-family="Orbitron, sans-serif" font-size="9" font-weight="900" fill="#000" text-anchor="middle" letter-spacing="2">EXPRESS WAY</text>
                </g>
                <path d="M 950 260 Q 1000 255 1080 245 L 1600 225" fill="none" stroke="#00fff9" stroke-width="1.5" opacity="0.7" style="filter: drop-shadow(0 0 6px #00fff9)"/>
            </svg>
        `;
        container.appendChild(op);

        // Fog
        const fog = document.createElement('div');
        fog.className = 'cyber-fog';
        container.appendChild(fog);

        console.log(`[Cyberpunk v5] Deep scene — no crows, parallax enabled`);
    }

    // ============================================================
    // SAKURA (Vaporwave)
    // ============================================================
    function spawnSakura() {
        const c = document.getElementById('sakura-container');
        if (!c) return;
        c.innerHTML = '';
        if (currentTheme() !== 'vaporwave') return;

        for (let i = 0; i < 28; i++) {
            const p = document.createElement('div');
            p.className = 'sakura-petal';
            const size = 8 + Math.random() * 12;
            const dur = 8 + Math.random() * 8;
            const delay = Math.random() * -16;
            const drift = (Math.random() - 0.5) * 300;
            const hue = 320 + Math.random() * 60;

            p.style.left = `${Math.random() * 100}%`;
            p.style.width = `${size}px`;
            p.style.height = `${size}px`;
            p.style.animationDuration = `${dur}s`;
            p.style.animationDelay = `${delay}s`;
            p.style.setProperty('--drift', `${drift}px`);
            p.style.background = `radial-gradient(circle at 30% 30%, hsl(${hue}, 100%, 85%), hsl(${hue}, 100%, 65%) 60%, hsl(${hue + 20}, 90%, 55%))`;
            c.appendChild(p);
        }
    }

    function applyEffects() {
        spawnSakura();
        spawnCyberpunk();
    }

    function applyTheme(id) {
        setTheme(id);
        applyEffects();
    }

    // ============================================================
    // SWITCHER UI
    // ============================================================
    function buildSwitcher() {
        const container = document.getElementById('theme-switcher');
        if (!container) return;

        const current = getSavedTheme();
        const cur = THEMES.find(t => t.id === current) || THEMES[0];

        container.innerHTML = `
            <button class="theme-btn" id="theme-btn" type="button" aria-label="Chọn theme">
                <span>🎨</span>
                <span id="theme-label">${cur.name}</span>
                <span style="opacity: 0.5; font-size: 0.7rem;">▼</span>
            </button>
            <div class="theme-dropdown" id="theme-dropdown">
                ${THEMES.map(t => `
                    <button class="theme-option ${t.id === current ? 'active' : ''}"
                            data-theme-id="${t.id}" type="button">
                        <div class="theme-swatch" data-swatch="${t.id}"></div>
                        <span>${t.icon} ${t.name}</span>
                    </button>
                `).join('')}
            </div>
        `;

        const btn = document.getElementById('theme-btn');
        const dd = document.getElementById('theme-dropdown');

        const open = () => dd.classList.add('open');
        const close = () => dd.classList.remove('open');

        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            dd.classList.contains('open') ? close() : open();
        });

        container.querySelectorAll('.theme-option').forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                const id = opt.dataset.themeId;
                if (!id) return;

                applyTheme(id);

                const t = THEMES.find(x => x.id === id);
                const lbl = document.getElementById('theme-label');
                if (t && lbl) lbl.textContent = t.name;

                container.querySelectorAll('.theme-option')
                    .forEach(o => o.classList.remove('active'));
                opt.classList.add('active');
                close();
            });
        });

        document.addEventListener('click', (e) => {
            if (!container.contains(e.target)) close();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') close();
        });
    }

    // ============================================================
    // INIT
    // ============================================================
    function init() {
        buildSwitcher();
        applyEffects();
        initCursorTrail();
        initRipple();
        initCardTilt();
        initParallax();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        setTimeout(init, 50);
    }
})();