// ============================================================
// COGNICRAFT STORE - Frontend
// ============================================================

// ⚠️ THAY ĐỔI URL NÀY KHI DEPLOY
// Local: http://localhost:8001
// Production: https://your-store-api.railway.app
const API_URL = "http://localhost:8001";

let allPlugins = [];
let currentCategory = "";

// ============================================================
// LOAD PLUGINS
// ============================================================

async function loadPlugins() {
    const loading = document.getElementById("loading");
    const empty = document.getElementById("empty-state");
    
    loading.style.display = "block";
    empty.style.display = "none";

    try {
        const params = new URLSearchParams();
        if (currentCategory) params.append("category", currentCategory);
        
        const search = document.getElementById("search-input").value;
        if (search) params.append("search", search);
        
        const sort = document.getElementById("sort-filter").value;
        params.append("sort", sort);

        const r = await fetch(`${API_URL}/api/store/plugins?${params}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        
        const data = await r.json();
        allPlugins = data.plugins;

        renderFeatured();
        renderPlugins(allPlugins);
        
        document.getElementById("total-count").textContent = `${data.total} plugins`;
        document.getElementById("last-update").textContent =
            "Cập nhật: " + new Date().toLocaleTimeString("vi-VN");

        if (allPlugins.length === 0) {
            empty.style.display = "block";
        }
    } catch (e) {
        console.error(e);
        showToast(`Lỗi: ${e.message}`, "error");
    } finally {
        loading.style.display = "none";
    }
}

// ============================================================
// LOAD CATEGORIES
// ============================================================

async function loadCategories() {
    try {
        const r = await fetch(`${API_URL}/api/store/categories`);
        if (!r.ok) return;
        
        const data = await r.json();
        renderCategories(data.categories);
    } catch (e) {
        console.error(e);
    }
}

// ============================================================
// LOAD STATS
// ============================================================

async function loadStats() {
    try {
        const r = await fetch(`${API_URL}/api/store/stats`);
        if (!r.ok) return;
        
        const data = await r.json();
        document.getElementById("stats-summary").textContent =
            `${data.total_plugins} plugins · ${data.total_downloads} downloads`;
    } catch (e) {
        console.error(e);
    }
}

// ============================================================
// RENDER CATEGORIES
// ============================================================

function renderCategories(categories) {
    const bar = document.getElementById("categories-bar");
    bar.innerHTML = "";

    // "All" chip
    const allChip = document.createElement("div");
    allChip.className = "category-chip" + (currentCategory === "" ? " active" : "");
    allChip.innerHTML = `📁 Tất cả`;
    allChip.onclick = () => {
        currentCategory = "";
        loadPlugins();
    };
    bar.appendChild(allChip);

    // Category chips
    categories.forEach(cat => {
        const chip = document.createElement("div");
        chip.className = "category-chip" + (currentCategory === cat.id ? " active" : "");
        chip.innerHTML = `
            ${cat.icon} ${cat.name}
            <span class="cat-count">${cat.plugin_count || 0}</span>
        `;
        chip.onclick = () => {
            currentCategory = cat.id;
            loadPlugins();
        };
        bar.appendChild(chip);
    });

    // Update select filter
    const select = document.getElementById("category-filter");
    select.innerHTML = '<option value="">📁 Tất cả</option>';
    categories.forEach(cat => {
        const option = document.createElement("option");
        option.value = cat.id;
        option.textContent = `${cat.icon} ${cat.name}`;
        select.appendChild(option);
    });
}

// ============================================================
// RENDER FEATURED
// ============================================================

function renderFeatured() {
    const featured = allPlugins.filter(p => p.featured).slice(0, 3);
    const grid = document.getElementById("featured-grid");
    const section = grid.closest(".section");
    
    if (featured.length === 0) {
        section.style.display = "none";
        return;
    }
    
    section.style.display = "block";
    document.getElementById("featured-count").textContent = `${featured.length} plugins`;
    grid.innerHTML = featured.map(p => renderPluginCard(p)).join("");
}

// ============================================================
// RENDER PLUGINS
// ============================================================

function renderPlugins(plugins) {
    const grid = document.getElementById("plugins-grid");
    
    if (plugins.length === 0) {
        grid.innerHTML = "";
        return;
    }
    
    grid.innerHTML = plugins.map(p => renderPluginCard(p)).join("");
}

function renderPluginCard(plugin) {
    const verifiedBadge = plugin.verified
        ? '<span class="plugin-badge badge-verified">✓ VERIFIED</span>'
        : "";
    
    const featuredBadge = plugin.featured
        ? '<span class="plugin-badge badge-featured" style="top: 3rem;">⭐ FEATURED</span>'
        : "";

    const stars = "★".repeat(Math.round(plugin.rating || 0)) + 
                  "☆".repeat(5 - Math.round(plugin.rating || 0));

    return `
        <a href="plugin.html?slug=${plugin.slug}" class="plugin-card">
            ${verifiedBadge}
            ${featuredBadge}
            <div class="plugin-icon">${plugin.icon || "📦"}</div>
            <div class="plugin-name">${plugin.name}</div>
            <div class="plugin-author">${plugin.author}</div>
            <div class="plugin-desc">${plugin.description || ""}</div>
            <div class="plugin-meta">
                <span class="plugin-rating">${stars} ${plugin.rating || "0.0"}</span>
                <span class="plugin-downloads">📥 ${formatNumber(plugin.downloads || 0)}</span>
            </div>
        </a>
    `;
}

// ============================================================
// HELPERS
// ============================================================

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "K";
    return num.toString();
}

function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

// ============================================================
// EVENTS
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    // Search input
    let searchTimeout;
    document.getElementById("search-input").addEventListener("input", () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(loadPlugins, 300);
    });

    // Category filter
    document.getElementById("category-filter").addEventListener("change", (e) => {
        currentCategory = e.target.value;
        loadPlugins();
    });

    // Sort filter
    document.getElementById("sort-filter").addEventListener("change", () => {
        loadPlugins();
    });

    // Initial load
    loadStats();
    loadCategories();
    loadPlugins();
});