// ============================================================
// PLUGIN HUB - Frontend
// ============================================================

async function loadPlugins() {
    try {
        const r = await fetch("/plugins/api/list");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();

        // KPIs
        document.getElementById("kpi-total").textContent = data.total;
        document.getElementById("kpi-installed").textContent = data.installed;
        document.getElementById("kpi-available").textContent = data.total - data.installed;
        document.getElementById("kpi-categories").textContent = data.categories;

        // Render plugins
        const grid = document.getElementById("plugins-grid");
        grid.innerHTML = "";

        if (data.plugins.length === 0) {
            grid.innerHTML = '<div class="loading-state">📦 Chưa có plugin nào</div>';
            return;
        }

        data.plugins.forEach(p => {
            const card = document.createElement("div");
            card.className = `plugin-card ${p.installed ? 'installed' : ''}`;

            const badge = p.installed
                ? '<span class="plugin-badge badge-installed">✅ INSTALLED</span>'
                : '<span class="plugin-badge badge-available">⚪ AVAILABLE</span>';

            const openBtn = p.installed
                ? `<a href="/plugins/${p.id}/" class="btn-action btn-open">🔍 Open UI</a>`
                : '';

            const actionBtn = p.installed
                ? `<button class="btn-action btn-uninstall" onclick="uninstallPlugin('${p.id}')">🗑 Uninstall</button>`
                : `<button class="btn-action btn-install" onclick="installPlugin('${p.id}')">📥 Install</button>`;

            card.innerHTML = `
                <div class="plugin-header">
                    <div>
                        <div class="plugin-name">${p.name}</div>
                        <div class="plugin-version">v${p.version} · ${p.author}</div>
                    </div>
                    ${badge}
                </div>
                <div class="plugin-desc">${p.description}</div>
                <div class="plugin-meta">
                    <span>📁 ${p.category}</span>
                    <span>📦 ${p.size_kb} KB</span>
                    <span>⭐ ${p.rating}</span>
                </div>
                <div class="plugin-actions">
                    ${openBtn}
                    ${actionBtn}
                </div>
            `;
            grid.appendChild(card);
        });

        document.getElementById("last-update").textContent =
            "Cập nhật: " + new Date().toLocaleTimeString("vi-VN");
    } catch (e) {
        console.error(e);
        document.getElementById("plugins-grid").innerHTML =
            `<div class="loading-state" style="color: #ff3355;">❌ Lỗi: ${e.message}</div>`;
    }
}

async function installPlugin(pluginId) {
    if (!confirm(`Cài đặt plugin "${pluginId}"?`)) return;
    try {
        const r = await fetch(`/plugins/api/install/${pluginId}`, { method: "POST" });
        const data = await r.json();
        if (data.success) {
            alert(`✅ Đã cài ${pluginId}!\n\nRestart bot để load plugin.`);
            loadPlugins();
        } else {
            alert(`❌ Lỗi: ${data.message}`);
        }
    } catch (e) {
        alert(`❌ Lỗi: ${e.message}`);
    }
}

async function uninstallPlugin(pluginId) {
    if (!confirm(`Gỡ plugin "${pluginId}"?`)) return;
    try {
        const r = await fetch(`/plugins/api/uninstall/${pluginId}`, { method: "POST" });
        const data = await r.json();
        if (data.success) {
            alert(`✅ Đã gỡ ${pluginId}!`);
            loadPlugins();
        } else {
            alert(`❌ Lỗi: ${data.message}`);
        }
    } catch (e) {
        alert(`❌ Lỗi: ${e.message}`);
    }
}

// Auto load
loadPlugins();
setInterval(loadPlugins, 10000);