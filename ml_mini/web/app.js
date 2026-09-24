// ============================================================
// ML MINI - Mesh Visualization
// ============================================================

const API = "";
let currentNodePositions = {};

async function loadAll() {
    try {
        await Promise.all([
            loadStatus(),
            loadEvents(),
        ]);
        document.getElementById("last-update").textContent =
            "Cập nhật: " + new Date().toLocaleTimeString("vi-VN");
    } catch (e) {
        console.error("Load error:", e);
    }
}

async function loadStatus() {
    const r = await fetch(`${API}/ml/api/status`);
    if (!r.ok) throw new Error("Status failed");
    const data = await r.json();

    document.getElementById("kpi-total").textContent = data.total_sandboxes;
    document.getElementById("kpi-healthy").textContent = data.stats.healthy || 0;
    document.getElementById("kpi-links").textContent = data.total_links;
    document.getElementById("kpi-down").textContent = data.stats.down || 0;

    renderMesh(data.sandboxes, data.links, data.states);
    renderSandboxes(data.sandboxes);
}

function renderMesh(sandboxes, links, states) {
    const svg = document.getElementById("mesh-svg");
    svg.innerHTML = "";

    const sandboxIds = Object.keys(sandboxes);
    const n = sandboxIds.length;

    if (n === 0) {
        svg.innerHTML = '<text x="400" y="250" style="fill:#6b7a99;font-size:14px;text-anchor:middle;">Chưa có sandbox</text>';
        return;
    }

    const cx = 400;
    const cy = 250;
    const radius = 150;
    const positions = {};

    sandboxIds.forEach((id, i) => {
        const angle = (i / n) * 2 * Math.PI - Math.PI / 2;
        positions[id] = {
            x: cx + radius * Math.cos(angle),
            y: cy + radius * Math.sin(angle),
        };
    });
    currentNodePositions = positions;

    // Draw links
    const uniqueLinks = [];
    links.forEach(([a, b]) => {
        if (a < b) uniqueLinks.push([a, b]);
    });

    uniqueLinks.forEach(([a, b]) => {
        if (!positions[a] || !positions[b]) return;

        const aHealthy = states[a] === "healthy";
        const bHealthy = states[b] === "healthy";
        const isActive = aHealthy && bHealthy;

        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", positions[a].x);
        line.setAttribute("y1", positions[a].y);
        line.setAttribute("x2", positions[b].x);
        line.setAttribute("y2", positions[b].y);
        line.setAttribute("class", `link ${isActive ? 'active' : 'broken'}`);

        svg.appendChild(line);
    });

    // Draw nodes
    sandboxIds.forEach(id => {
        const pos = positions[id];
        const state = states[id] || "healthy";
        const sb = sandboxes[id];

        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", `node ${state}`);

        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", pos.x);
        circle.setAttribute("cy", pos.y);
        circle.setAttribute("r", 30);
        circle.setAttribute("stroke", "#06080d");
        circle.setAttribute("stroke-width", "3");
        g.appendChild(circle);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", pos.x);
        text.setAttribute("y", pos.y + 8);
        text.setAttribute("style", "font-size: 24px;");
        text.textContent = getIcon(sb.name);
        g.appendChild(text);

        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", pos.x);
        label.setAttribute("y", pos.y + 50);
        label.setAttribute("style", "font-size: 11px; fill: #8892b0;");
        label.textContent = sb.name.replace("_", " ");
        g.appendChild(label);

        svg.appendChild(g);
    });
}

function getIcon(name) {
    if (name.includes("score")) return "📊";
    if (name.includes("anomaly")) return "🚨";
    if (name.includes("token")) return "⚡";
    return "🔌";
}

function renderSandboxes(sandboxes) {
    const list = document.getElementById("sandboxes-list");
    list.innerHTML = "";

    Object.entries(sandboxes).forEach(([id, sb]) => {
        const item = document.createElement("div");
        item.className = `sandbox-item ${sb.state}`;

        const icon = {
            healthy: "🟢",
            down: "🔴",
            recovering: "🟡",
            restarting: "🔄",
        }[sb.state] || "⚪";

        item.innerHTML = `
            <div class="sandbox-name">${icon} ${sb.name}</div>
            <div class="sandbox-meta">
                Restarts: ${sb.restart_count} · HB: ${sb.heartbeat_interval}s
            </div>
        `;
        list.appendChild(item);
    });
}

async function loadEvents() {
    const r = await fetch(`${API}/ml/api/events?limit=20`);
    if (!r.ok) return;
    const data = await r.json();

    const list = document.getElementById("feed-list");
    const existing = list.querySelectorAll(".feed-item:not(.dim)").length;

    if (data.events.length > existing) {
        const newEvents = data.events.slice(-(data.events.length - existing));
        newEvents.forEach(ev => {
            let type = "info";
            if (ev.type === "down" || ev.type === "restart_error") type = "error";
            else if (ev.type === "recovered" || ev.type === "restarted") type = "recovery";
            addFeed(type, `${ev.type}: ${ev.sandbox} – ${ev.message}`);
        });
    }
}

function addFeed(type, message) {
    const list = document.getElementById("feed-list");
    const dim = list.querySelector(".dim");
    if (dim) dim.remove();

    const time = new Date().toLocaleTimeString("vi-VN", { hour12: false });

    const item = document.createElement("div");
    item.className = `feed-item ${type === "error" ? 'error' : ''} ${type === "recovery" ? 'recovery' : ''}`;
    item.innerHTML = `
        <div class="feed-time">${time}</div>
        <div class="feed-content">${message}</div>
    `;
    list.insertBefore(item, list.firstChild);

    while (list.children.length > 30) {
        list.removeChild(list.lastChild);
    }
}

function clearFeed() {
    document.getElementById("feed-list").innerHTML =
        '<div class="feed-item dim">Đã clear.</div>';
}

loadAll();
setInterval(loadAll, 5000);