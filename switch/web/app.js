
// ============================================================
// SWITCH BOARD · Live Controller
// ============================================================

const API = ""; // Same origin
let feedEvents = [];

// ============================================================
// CLOCK
// ============================================================
function updateClock() {
    const now = new Date();
    const time = now.toLocaleTimeString("vi-VN", { hour12: false });
    const el = document.getElementById("clock");
    if (el) el.textContent = time;
}
setInterval(updateClock, 1000);
updateClock();

// ============================================================
// LOAD ALL DATA
// ============================================================
async function loadAll() {
    try {
        await Promise.all([
            loadStatus(),
            loadWires(),
            loadHistory(),
        ]);
        document.getElementById("last-update").textContent =
            "Cập nhật: " + new Date().toLocaleTimeString("vi-VN");
    } catch (e) {
        console.error("Load error:", e);
        addFeed("error", "❌ Không kết nối được board");
    }
}

// ============================================================
// LOAD STATUS
// ============================================================
async function loadStatus() {
    const r = await fetch(`${API}/panel/status`);
    if (!r.ok) throw new Error("Status failed");
    const data = await r.json();

    // KPIs
    let totalCalls = 0;
    let totalFailed = 0;
    data.sockets.forEach(s => {
        totalCalls += s.stats.calls || 0;
        totalFailed += s.stats.failed || 0;
    });

    document.getElementById("kpi-total").textContent = data.total;
    document.getElementById("kpi-on").textContent = data.by_status.on || 0;
    document.getElementById("kpi-calls").textContent = totalCalls;
    document.getElementById("kpi-failed").textContent = totalFailed;

    // Socket cards
    renderSockets(data.sockets);
    document.getElementById("socket-count").textContent = `${data.total} sockets`;
}

// ============================================================
// RENDER SOCKETS
// ============================================================
function renderSockets(sockets) {
    const grid = document.getElementById("sockets-grid");
    grid.innerHTML = "";

    sockets.forEach(s => {
        const card = document.createElement("div");
        card.className = `socket-card ${s.status}`;

        const successRate = s.stats.calls > 0
            ? ((s.stats.success / s.stats.calls) * 100).toFixed(0)
            : 100;

        card.innerHTML = `
            <div class="socket-top">
                <div>
                    <div class="socket-name">${s.name}</div>
                    <div class="socket-type">${s.type} · v${s.version}</div>
                </div>
                <div class="socket-led ${s.status}"></div>
            </div>
            <div class="socket-stats">
                <div class="stat-item">
                    <div class="stat-label">CALLS</div>
                    <div class="stat-value normal">${s.stats.calls}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">FAILED</div>
                    <div class="stat-value ${s.stats.failed > 0 ? 'bad' : 'good'}">${s.stats.failed}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">SUCCESS</div>
                    <div class="stat-value good">${successRate}%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">STATUS</div>
                    <div class="stat-value ${s.status === 'on' ? 'good' : 'bad'}">${s.status.toUpperCase()}</div>
                </div>
            </div>
            <div class="socket-actions">
                <button class="action-btn" onclick="toggleSocket('${s.name}', '${s.status === 'on' ? 'stop' : 'start'}')">
                    ${s.status === 'on' ? '⏸ STOP' : '▶ START'}
                </button>
                <button class="action-btn" onclick="healthCheck('${s.name}')">
                    ♥ CHECK
                </button>
            </div>
        `;
        grid.appendChild(card);
    });
}

// ============================================================
// SOCKET ACTIONS
// ============================================================
async function toggleSocket(name, action) {
    try {
        const r = await fetch(`${API}/panel/socket/${name}/${action}`, { method: "POST" });
        const data = await r.json();
        addFeed("info", `🔌 ${name}: ${action === 'start' ? 'BẬT' : 'TẮT'} → ${data.status}`);
        setTimeout(loadAll, 500);
    } catch (e) {
        addFeed("error", `❌ ${name}: ${e.message}`);
    }
}

async function healthCheck(name) {
    try {
        const r = await fetch(`${API}/panel/socket/${name}/health`);
        const data = await r.json();
        const icon = data.healthy ? "💚" : "💔";
        addFeed("info", `${icon} ${name}: ${data.healthy ? 'HEALTHY' : 'UNHEALTHY'}`);
    } catch (e) {
        addFeed("error", `❌ ${name}: ${e.message}`);
    }
}

// ============================================================
// LOAD WIRES
// ============================================================
async function loadWires() {
    const r = await fetch(`${API}/panel/wires`);
    if (!r.ok) return;
    const data = await r.json();

    const list = document.getElementById("wires-list");
    list.innerHTML = "";

    let count = 0;
    Object.entries(data).forEach(([event, targets]) => {
        targets.forEach(t => {
            count++;
            const item = document.createElement("div");
            item.className = "wire-item";
            item.innerHTML = `
                <span class="wire-event">${event}</span>
                <span class="wire-arrow">→</span>
                <span class="wire-target">${t.socket}.${t.action}()</span>
            `;
            list.appendChild(item);
        });
    });

    if (count === 0) {
        list.innerHTML = '<div class="feed-item dim">Chưa có dây nào</div>';
    }
}

// ============================================================
// LOAD HISTORY (Live Feed)
// ============================================================
async function loadHistory() {
    const r = await fetch(`${API}/panel/history?limit=20`);
    if (!r.ok) return;
    const data = await r.json();

    // Only add new events
    const list = document.getElementById("feed-list");
    const existing = list.querySelectorAll(".feed-item:not(.dim)").length;

    if (data.history.length > existing) {
        const newEvents = data.history.slice(0, data.history.length - existing);
        newEvents.reverse().forEach(ev => {
            addFeed("info", `⚡ ${ev.event} → ${ev.listeners} socket(s)`);
        });
    }
}

// ============================================================
// FEED
// ============================================================
function addFeed(type, message) {
    const list = document.getElementById("feed-list");

    // Remove dim placeholder
    const dim = list.querySelector(".dim");
    if (dim) dim.remove();

    const time = new Date().toLocaleTimeString("vi-VN", { hour12: false });

    const item = document.createElement("div");
    item.className = `feed-item ${type === 'error' ? 'error' : ''}`;
    item.innerHTML = `
        <div class="feed-time">${time}</div>
        <div class="feed-content">${message}</div>
    `;

    list.insertBefore(item, list.firstChild);

    // Keep max 30
    while (list.children.length > 30) {
        list.removeChild(list.lastChild);
    }
}

function clearFeed() {
    document.getElementById("feed-list").innerHTML =
        '<div class="feed-item dim">Đã clear. Đang chờ events...</div>';
}

// ============================================================
// AUTO REFRESH
// ============================================================
loadAll();
setInterval(loadAll, 5000); // 5s