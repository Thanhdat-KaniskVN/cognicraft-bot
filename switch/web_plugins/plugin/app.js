// ============================================================
// PLUGIN UI - Individual Page
// ============================================================

// Extract plugin ID from URL: /plugins/{id}/
function getPluginId() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    // ["plugins", "{id}"] → id at index 1
    return parts[1] || "unknown";
}

async function loadPluginInfo() {
    const pluginId = getPluginId();

    try {
        const r = await fetch(`/plugins/api/info/${pluginId}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();

        // Header
        document.getElementById("plugin-name").textContent = data.name.toUpperCase();
        document.getElementById("plugin-desc").textContent = data.description;
        document.getElementById("plugin-version").textContent = `v${data.version}`;
        document.title = `${data.name} · CogniCraft OS`;

        // Info panel
        document.getElementById("plugin-info").innerHTML = `
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">VERSION</span>
                    <span class="info-value">${data.version}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">AUTHOR</span>
                    <span class="info-value">${data.author}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">CATEGORY</span>
                    <span class="info-value">${data.category}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">LICENSE</span>
                    <span class="info-value">${data.license}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">SIZE</span>
                    <span class="info-value">${data.size_kb} KB</span>
                </div>
                <div class="info-item">
                    <span class="info-label">STATUS</span>
                    <span class="info-value" style="color: ${data.installed ? '#00ff88' : '#6b7a99'}">
                        ${data.installed ? '✅ Installed' : '⚪ Not installed'}
                    </span>
                </div>
            </div>
        `;

        // Commands panel
        const commands = data.commands || [];
        const cmdsHtml = commands.length > 0
            ? commands.map(c => `
                <div class="command-item">
                    <div class="command-name">!${c.name}</div>
                    <div class="command-desc">${c.description || ''}</div>
                </div>
            `).join("")
            : '<p style="color: #6b7a99;">Không có commands.</p>';
        document.getElementById("plugin-commands").innerHTML = cmdsHtml;

        // Config panel
        const config = data.config || {};
        const configKeys = Object.keys(config);
        if (configKeys.length > 0) {
            document.getElementById("plugin-config").innerHTML = `
                <div class="info-grid">
                    ${configKeys.map(k => `
                        <div class="info-item">
                            <span class="info-label">${k.toUpperCase()}</span>
                            <span class="info-value">${config[k].default ?? '?'}</span>
                        </div>
                    `).join("")}
                </div>
            `;
        }

    } catch (e) {
        console.error(e);
        document.getElementById("plugin-info").innerHTML =
            `<p style="color: #ff3355;">❌ Lỗi: ${e.message}</p>`;
    }
}

loadPluginInfo();