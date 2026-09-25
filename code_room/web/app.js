// ============================================================
// CODE ROOM - Main App
// ============================================================

let editor = null;
let currentFile = null;
let files = [];
let snapshots = [];
let isDirty = false;
let lastSavedContent = "";

// ============================================================
// INIT MONACO EDITOR
// ============================================================
require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });

require(['vs/editor/editor.main'], function () {
    editor = monaco.editor.create(document.getElementById('editor-container'), {
        value: getWelcomeCode(),
        language: 'python',
        theme: 'vs-dark',
        fontSize: 14,
        fontFamily: 'JetBrains Mono, monospace',
        minimap: { enabled: false },
        automaticLayout: true,
        scrollBeyondLastLine: false,
        lineNumbers: 'on',
        tabSize: 4,
        insertSpaces: true,
        wordWrap: 'on',
    });

    // Track changes
    editor.onDidChangeModelContent(() => {
        const content = editor.getValue();
        isDirty = content !== lastSavedContent;
        updateEditStatus();
    });

    // Cursor position
    editor.onDidChangeCursorPosition((e) => {
        document.getElementById('line-info').textContent =
            `Ln ${e.position.lineNumber}, Col ${e.position.column}`;
    });

    // Ctrl+Enter = Run
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
        runCode();
    });

    // Ctrl+S = Save
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        saveCode();
    });

    // Load files
    loadFiles();
    loadTheme();
});

// ============================================================
// WELCOME CODE
// ============================================================
function getWelcomeCode() {
    return `# 🏛️ CODE ROOM - CogniCraft OS
# ============================================
# 
# Chào mừng đến với phòng luyện code!
# 
# ✨ Features:
#   - Monaco Editor (như VS Code)
#   - Python runtime
#   - Smart Undo (khôi phục sau khi xóa)
#   - AI Fix với tiếng Việt + English
#
# 🎯 Phím tắt:
#   Ctrl+Enter → Run code
#   Ctrl+S     → Save file
#

def hello():
    print("🏛️ Hello CogniCraft!")

if __name__ == "__main__":
    hello()
`;
}

// ============================================================
// FILE MANAGEMENT
// ============================================================
async function loadFiles() {
    try {
        const r = await fetch('/code/api/files');
        const data = await r.json();
        files = data.files || [];
        renderFiles();
    } catch (e) {
        console.error(e);
    }
}

function renderFiles() {
    const list = document.getElementById('file-list');
    if (files.length === 0) {
        list.innerHTML = '<div class="dim-text">Chưa có file. Nhấn + New</div>';
        return;
    }

    list.innerHTML = files.map(f => `
        <div class="file-item ${f === currentFile ? 'active' : ''}" onclick="openFile('${f}')">
            <span>📄 ${f}</span>
            <span class="file-delete" onclick="event.stopPropagation(); deleteFile('${f}')">×</span>
        </div>
    `).join('');
}

async function newFile() {
    const name = prompt('Tên file (VD: test.py):', 'untitled.py');
    if (!name) return;
    if (!name.endsWith('.py')) name += '.py';

    await saveFileToBackend(name, '# New file\nprint("Hello!")\n');
    await loadFiles();
    openFile(name);
}

async function openFile(name) {
    if (isDirty && !confirm('File chưa lưu. Bỏ thay đổi?')) return;

    try {
        const r = await fetch(`/code/api/load?name=${encodeURIComponent(name)}`);
        if (!r.ok) throw new Error('Không load được file');

        const data = await r.json();
        editor.setValue(data.content);

        currentFile = name;
        lastSavedContent = data.content;
        isDirty = false;

        document.getElementById('current-file').textContent = name;
        updateEditStatus();
        renderFiles();
        loadSnapshots();
    } catch (e) {
        toast(`Lỗi: ${e.message}`, 'error');
    }
}

async function deleteFile(name) {
    if (!confirm(`Xóa file "${name}"?`)) return;

    try {
        await fetch(`/code/api/delete?name=${encodeURIComponent(name)}`, { method: 'DELETE' });
        if (currentFile === name) {
            currentFile = null;
            editor.setValue(getWelcomeCode());
        }
        await loadFiles();
        toast(`Đã xóa ${name}`, 'success');
    } catch (e) {
        toast(`Lỗi: ${e.message}`, 'error');
    }
}

// ============================================================
// SAVE
// ============================================================
async function saveCode() {
    if (!currentFile) {
        const name = prompt('Đặt tên file:', 'untitled.py');
        if (!name) return;
        currentFile = name.endsWith('.py') ? name : name + '.py';
    }

    const content = editor.getValue();
    await saveFileToBackend(currentFile, content);

    lastSavedContent = content;
    isDirty = false;
    updateEditStatus();
    document.getElementById('current-file').textContent = currentFile;

    await loadFiles();
    await loadSnapshots();
    toast('✅ Đã lưu!', 'success');
}

async function saveFileToBackend(name, content) {
    try {
        await fetch('/code/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, content }),
        });
    } catch (e) {
        toast(`Lỗi lưu: ${e.message}`, 'error');
    }
}

function updateEditStatus() {
    const el = document.getElementById('edit-status');
    if (isDirty) {
        el.textContent = '● Unsaved';
        el.classList.remove('saved');
    } else {
        el.textContent = '✓ Saved';
        el.classList.add('saved');
    }
}

// ============================================================
// RUN CODE
// ============================================================
async function runCode() {
    const code = editor.getValue();
    const output = document.getElementById('output');
    output.innerHTML = '<div class="output-line info">⏳ Đang chạy...</div>';

    try {
        const r = await fetch('/code/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, timeout: 10 }),
        });

        const data = await r.json();
        renderOutput(data);
    } catch (e) {
        output.innerHTML = `<div class="output-line error">❌ Lỗi kết nối: ${e.message}</div>`;
    }
}

function renderOutput(data) {
    const output = document.getElementById('output');
    let html = '';

    if (data.stdout) {
        html += `<div class="output-line success">📤 Output:</div>`;
        html += `<pre style="color: var(--text); font-size: 0.72rem;">${escapeHtml(data.stdout)}</pre>`;
    }

    if (data.stderr) {
        html += `<div class="output-line error">❌ Stderr:</div>`;
        html += `<pre style="color: var(--red); font-size: 0.72rem;">${escapeHtml(data.stderr)}</pre>`;
    }

    if (data.error) {
        html += `<div class="output-line error">🔴 ${escapeHtml(data.error)}</div>`;
    }

    html += `<div class="output-line info">⏱️ Thời gian: ${data.duration}s | Exit code: ${data.exit_code}</div>`;

    output.innerHTML = html || '<div class="output-line info">Không có output</div>';
}

function clearOutput() {
    document.getElementById('output').innerHTML =
        '<div class="dim-text">Nhấn ▶ Run để chạy code</div>';
}

// ============================================================
// SNAPSHOTS / UNDO
// ============================================================
async function loadSnapshots() {
    if (!currentFile) return;

    try {
        const r = await fetch(`/code/api/snapshots?name=${encodeURIComponent(currentFile)}`);
        const data = await r.json();
        snapshots = data.snapshots || [];
        renderSnapshots();
    } catch (e) {
        console.error(e);
    }
}

function renderSnapshots() {
    const list = document.getElementById('snapshot-list');
    if (snapshots.length === 0) {
        list.innerHTML = '<div class="dim-text">Chưa có snapshot</div>';
        return;
    }

    list.innerHTML = snapshots.slice(-5).reverse().map(s => `
        <div class="file-item" onclick="restoreSnapshot('${s.id}')">
            <span>🕐 ${s.time_short}</span>
        </div>
    `).join('');
}

async function showHistory() {
    if (!currentFile) {
        toast('Chưa mở file nào', 'error');
        return;
    }

    await loadSnapshots();

    const modal = document.getElementById('history-modal');
    const list = document.getElementById('history-list');

    if (snapshots.length === 0) {
        list.innerHTML = '<div class="dim-text">Chưa có snapshot nào. Save để tạo snapshot.</div>';
    } else {
        list.innerHTML = snapshots.slice().reverse().map(s => `
            <div class="history-item" onclick="restoreSnapshot('${s.id}')">
                <div class="history-time">🕐 ${s.time}</div>
                <div class="history-preview">${escapeHtml(s.preview)}</div>
            </div>
        `).join('');
    }

    modal.style.display = 'flex';
}

function hideHistory() {
    document.getElementById('history-modal').style.display = 'none';
}

async function restoreSnapshot(snapshotId) {
    try {
        const r = await fetch(`/code/api/restore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: currentFile, snapshot_id: snapshotId }),
        });

        if (!r.ok) throw new Error('Không restore được');

        const data = await r.json();
        editor.setValue(data.content);
        hideHistory();
        toast('↩️ Đã khôi phục!', 'success');
    } catch (e) {
        toast(`Lỗi: ${e.message}`, 'error');
    }
}

async function undoSnapshot() {
    if (!currentFile) {
        toast('Chưa mở file nào', 'error');
        return;
    }

    try {
        const r = await fetch(`/code/api/undo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: currentFile }),
        });

        if (!r.ok) throw new Error('Không undo được');

        const data = await r.json();
        editor.setValue(data.content);
        toast('↩️ Đã khôi phục phiên bản trước!', 'success');
    } catch (e) {
        toast(`Lỗi: ${e.message}`, 'error');
    }
}

// ============================================================
// AI FIX
// ============================================================
async function askAI() {
    const code = editor.getValue();
    if (!code.trim()) {
        toast('Chưa có code để phân tích', 'error');
        return;
    }

    const aiPanel = document.getElementById('ai-suggestions');
    aiPanel.innerHTML = '<div class="dim-text">⏳ Đang phân tích code...</div>';

    try {
        const r = await fetch('/code/api/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, language: 'python' }),
        });

        if (!r.ok) throw new Error('AI không phản hồi');

        const data = await r.json();
        renderAISuggestions(data);
    } catch (e) {
        aiPanel.innerHTML = `<div class="dim-text" style="color: var(--red);">❌ ${e.message}</div>`;
    }
}

function renderAISuggestions(data) {
    const panel = document.getElementById('ai-suggestions');

    let html = '';

    // Summary
    if (data.summary) {
        html += `
            <div class="ai-suggestion">
                <div class="suggestion-section">
                    <div class="suggestion-label">📋 TÓM TẮT</div>
                    <div class="suggestion-text">${escapeHtml(data.summary)}</div>
                </div>
            </div>
        `;
    }

    // Suggestions (bilingual)
    if (data.suggestions && data.suggestions.length > 0) {
        data.suggestions.forEach((s, i) => {
            html += `
                <div class="ai-suggestion">
                    <div class="suggestion-section">
                        <div class="suggestion-label">🇻🇳 TIẾNG VIỆT</div>
                        <div class="suggestion-text">${escapeHtml(s.vn || '')}</div>
                    </div>
                    <div class="suggestion-section">
                        <div class="suggestion-label">🇬🇧 ENGLISH</div>
                        <div class="suggestion-text">${escapeHtml(s.en || '')}</div>
                    </div>
                    ${s.code ? `<div class="suggestion-code">${escapeHtml(s.code)}</div>` : ''}
                </div>
            `;
        });
    }

    if (!html) {
        html = '<div class="dim-text">✅ Code ổn, không có gợi ý nào</div>';
    }

    panel.innerHTML = html;
}

// ============================================================
// THEME SWITCHER
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    const selector = document.getElementById('theme-selector');
    if (selector) {
        selector.addEventListener('change', (e) => {
            applyTheme(e.target.value);
        });
    }
});

function applyTheme(themeName) {
    document.body.classList.remove('theme-neon', 'theme-matrix', 'theme-dracula');

    if (themeName !== 'cyberpunk') {
        document.body.classList.add(`theme-${themeName}`);
    }

    localStorage.setItem('code_room_theme', themeName);
    toast(`🎨 Theme: ${themeName}`, 'success');
}

function loadTheme() {
    const saved = localStorage.getItem('code_room_theme') || 'cyberpunk';
    document.getElementById('theme-selector').value = saved;
    applyTheme(saved);
}

// ============================================================
// CLEAR EDITOR
// ============================================================
function clearEditor() {
    if (!confirm('Xóa toàn bộ nội dung? (Có thể Undo)')) return;
    editor.setValue('');
    toast('Đã xóa. Nhấn "Undo Last" để khôi phục!', 'info');
}

// ============================================================
// UTILS
// ============================================================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toast(message, type = 'info') {
    const el = document.getElementById('toast');
    el.textContent = message;
    el.className = `toast show ${type}`;

    setTimeout(() => {
        el.classList.remove('show');
    }, 3000);
}

// Auto-load snapshots when file changes
setInterval(() => {
    if (currentFile && !isDirty) {
        loadSnapshots();
    }
}, 30000);

// ============================================================
// PHASE 3 — STORE INTEGRATION
// ============================================================

let storeSearchTimeout = null;
let installedSlugs = new Set();

// ============================================================
// OPEN / CLOSE MODAL
// ============================================================

function openStore() {
    document.getElementById('store-modal').style.display = 'flex';
    loadInstalledSlugs().then(() => {
        loadStorePlugins();
    });
}

function closeStore() {
    document.getElementById('store-modal').style.display = 'none';
}

function switchStoreTab(tab) {
    document.querySelectorAll('.store-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.store-tab[data-tab="${tab}"]`).classList.add('active');

    document.getElementById('store-panel-browse').style.display = tab === 'browse' ? 'block' : 'none';
    document.getElementById('store-panel-installed').style.display = tab === 'installed' ? 'block' : 'none';

    if (tab === 'installed') {
        loadInstalledPlugins();
    }
}

// ============================================================
// LOAD STORE PLUGINS
// ============================================================

async function loadStorePlugins() {
    const list = document.getElementById('store-plugins-list');
    list.innerHTML = '<div class="dim-text" style="padding: 2rem; text-align: center;">Đang tải...</div>';

    const search = document.getElementById('store-search').value.trim();
    const sort = document.getElementById('store-sort').value;

    const params = new URLSearchParams({ sort, per_page: 50 });
    if (search) params.append('search', search);

    try {
        const r = await fetch(`/code/api/store/plugins?${params}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();

        renderStorePlugins(data.plugins || []);
    } catch (e) {
        list.innerHTML = `<div class="store-empty"><div class="store-empty-icon">❌</div>Lỗi: ${e.message}</div>`;
    }
}

function renderStorePlugins(plugins) {
    const list = document.getElementById('store-plugins-list');

    if (plugins.length === 0) {
        list.innerHTML = '<div class="store-empty"><div class="store-empty-icon">📭</div>Không tìm thấy plugin</div>';
        return;
    }

    list.innerHTML = plugins.map(p => {
        const isInstalled = installedSlugs.has(p.slug);
        const stars = '★'.repeat(Math.round(p.rating || 0)) + '☆'.repeat(5 - Math.round(p.rating || 0));

        const hasFile = p.has_file !== false;  // Nếu API trả về has_file

        return `
            <div class="store-plugin-card">
                <div class="store-plugin-icon">${p.icon || '📦'}</div>
                <div class="store-plugin-info">
                    <div class="store-plugin-name">${p.name}</div>
                    <div class="store-plugin-meta">
                        👤 ${p.author} · 📁 ${p.category} ·
                        <span class="store-plugin-rating">${stars} ${p.rating || '0.0'}</span> ·
                        📥 ${p.downloads || 0}
                    </div>
                    <div class="store-plugin-desc">${p.description || ''}</div>
                </div>
                <button class="store-install-btn ${isInstalled ? 'installed' : ''}"
                        onclick="installStorePlugin('${p.slug}', this)"
                        ${isInstalled || !hasFile ? 'disabled' : ''}
                        title="${!hasFile ? 'Plugin chưa có file .cogni' : ''}">
                    ${isInstalled ? '✅ Đã cài' : (!hasFile ? '⚠️ Chưa có' : '📥 Install')}
                </button>
            </div>
        `;
    }).join('');
}

// ============================================================
// SEARCH DEBOUNCE
// ============================================================

function debouncedStoreSearch() {
    clearTimeout(storeSearchTimeout);
    storeSearchTimeout = setTimeout(loadStorePlugins, 300);
}

// ============================================================
// INSTALL PLUGIN
// ============================================================

async function installStorePlugin(slug, btn) {
    btn.disabled = true;
    btn.classList.add('installing');
    btn.textContent = '⏳ Đang cài...';

    try {
        const r = await fetch(`/code/api/store/install/${slug}`, { method: 'POST' });
        const data = await r.json();

        if (!r.ok || !data.success) {
            throw new Error(data.detail || `HTTP ${r.status}`);
        }

        btn.classList.remove('installing');
        btn.classList.add('installed');
        btn.textContent = '✅ Đã cài';

        installedSlugs.add(slug);
        updateInstalledCount();

        showToast(`✅ Đã cài ${data.name} v${data.version}`, 'success');

    } catch (e) {
        btn.classList.remove('installing');
        btn.disabled = false;
        btn.textContent = '📥 Install';
        showToast(`❌ ${e.message}`, 'error');
    }
}

// ============================================================
// LOAD INSTALLED PLUGINS
// ============================================================

async function loadInstalledSlugs() {
    try {
        const r = await fetch('/code/api/store/installed');
        if (!r.ok) return;
        const data = await r.json();
        installedSlugs = new Set((data.installed || []).map(p => p.slug));
        updateInstalledCount();
    } catch (e) {
        console.error(e);
    }
}

function updateInstalledCount() {
    const el = document.getElementById('installed-count');
    if (el) el.textContent = installedSlugs.size;
}

async function loadInstalledPlugins() {
    const list = document.getElementById('installed-plugins-list');
    list.innerHTML = '<div class="dim-text" style="padding: 2rem; text-align: center;">Đang tải...</div>';

    try {
        const r = await fetch('/code/api/store/installed');
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();

        const installed = data.installed || [];

        if (installed.length === 0) {
            list.innerHTML = '<div class="store-empty"><div class="store-empty-icon">📭</div>Chưa cài plugin nào</div>';
            return;
        }

        list.innerHTML = installed.map(p => `
            <div class="store-plugin-card">
                <div class="store-plugin-icon">${p.icon || '📦'}</div>
                <div class="store-plugin-info">
                    <div class="store-plugin-name">${p.name}</div>
                    <div class="store-plugin-meta">
                        v${p.version} · 👤 ${p.author} · 📁 ${p.category}
                    </div>
                    <div class="store-plugin-desc">${p.description || ''}</div>
                </div>
                <button class="store-install-btn" style="background: transparent; color: #ff3355; border: 1px solid #ff3355;"
                        onclick="uninstallPlugin('${p.slug}', this)">
                    🗑 Xóa
                </button>
            </div>
        `).join('');

    } catch (e) {
        list.innerHTML = `<div class="store-empty"><div class="store-empty-icon">❌</div>Lỗi: ${e.message}</div>`;
    }
}

// ============================================================
// UNINSTALL
// ============================================================

async function uninstallPlugin(slug, btn) {
    if (!confirm(`Xóa plugin "${slug}"?`)) return;

    btn.disabled = true;
    btn.textContent = '⏳...';

    try {
        const r = await fetch(`/code/api/store/installed/${slug}`, { method: 'DELETE' });
        const data = await r.json();

        if (!r.ok || !data.success) {
            throw new Error(data.detail || `HTTP ${r.status}`);
        }

        installedSlugs.delete(slug);
        updateInstalledCount();
        showToast(`✅ Đã xóa ${slug}`, 'success');
        loadInstalledPlugins();

    } catch (e) {
        btn.disabled = false;
        btn.textContent = '🗑 Xóa';
        showToast(`❌ ${e.message}`, 'error');
    }
}

// ============================================================
// TOAST (nếu app.js chưa có)
// ============================================================

if (typeof showToast !== 'function') {
    window.showToast = function(message, type = 'info') {
        const toast = document.getElementById('toast');
        if (!toast) return;
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        setTimeout(() => toast.classList.remove('show'), 3000);
    };
}

// Đóng modal khi click ngoài
document.addEventListener('click', (e) => {
    const modal = document.getElementById('store-modal');
    if (modal && e.target === modal) closeStore();
});

// ESC để đóng
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeStore();
});