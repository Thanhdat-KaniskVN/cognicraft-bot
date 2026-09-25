// ============================================================
// COGNICRAFT STORE - Frontend v2.2 (Advanced Search)
// ============================================================

const API_URL = window.STORE_API || "http://localhost:8001";

let allPlugins = [];
let currentFilters = {
    category: "",
    search: "",
    author: "",
    tag: "",
    min_rating: null,
    price_type: "",
    sort: "downloads",
    page: 1,
};

let searchSuggestTimeout = null;

// ============================================================
// LOAD PLUGINS
// ============================================================

async function loadPlugins() {
    const loading = document.getElementById("loading");
    const empty = document.getElementById("empty-state");

    if (loading) loading.style.display = "block";
    if (empty) empty.style.display = "none";

    try {
        const params = new URLSearchParams();
        if (currentFilters.category) params.append("category", currentFilters.category);
        if (currentFilters.search) params.append("search", currentFilters.search);
        if (currentFilters.author) params.append("author", currentFilters.author);
        if (currentFilters.tag) params.append("tag", currentFilters.tag);
        if (currentFilters.min_rating !== null) params.append("min_rating", currentFilters.min_rating);
        if (currentFilters.price_type) params.append("price_type", currentFilters.price_type);
        params.append("sort", currentFilters.sort);
        params.append("page", currentFilters.page);
        params.append("per_page", 50);

        const r = await fetch(`${API_URL}/api/store/plugins?${params}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);

        const data = await r.json();
        allPlugins = data.plugins;

        renderFeatured();
        renderPlugins(allPlugins);

        document.getElementById("total-count").textContent = `${data.total} plugins`;
        document.getElementById("last-update").textContent =
            "Cập nhật: " + new Date().toLocaleTimeString("vi-VN");

        // Update active filter count
        updateFilterBadge();

        if (allPlugins.length === 0) {
            empty.style.display = "block";
        }
    } catch (e) {
        console.error(e);
        showToast(`Lỗi: ${e.message}`, "error");
    } finally {
        if (loading) loading.style.display = "none";
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
// LOAD POPULAR TAGS
// ============================================================

async function loadTags() {
    try {
        const r = await fetch(`${API_URL}/api/store/tags?limit=10`);
        if (!r.ok) return;
        const data = await r.json();
        renderTags(data.tags);
    } catch (e) {
        console.error(e);
    }
}

function renderTags(tags) {
    const container = document.getElementById("popular-tags");
    if (!container) return;

    if (!tags || tags.length === 0) {
        container.innerHTML = '<span style="color: var(--dim); font-size: 0.8rem;">Chưa có tag nào</span>';
        return;
    }

    container.innerHTML = tags.map(t =>
        `<div class="tag-chip ${currentFilters.tag === t.tag ? 'active' : ''}"
              onclick="filterByTag('${escapeHtml(t.tag)}')">
            🏷️ ${escapeHtml(t.tag)}
            <span class="tag-count">${escapeHtml(t.count)}</span>
        </div>`
    ).join("");
}

function filterByTag(tag) {
    if (currentFilters.tag === tag) {
        currentFilters.tag = "";
    } else {
        currentFilters.tag = tag;
    }
    loadTags();
    loadPlugins();
}

// ============================================================
// SEARCH SUGGESTIONS
// ============================================================

async function fetchSuggestions(q) {
    if (!q || q.length < 1) {
        hideSuggestions();
        return;
    }

    try {
        const r = await fetch(`${API_URL}/api/store/search/suggest?q=${encodeURIComponent(q)}`);
        if (!r.ok) return;
        const data = await r.json();
        showSuggestions(data.suggestions);
    } catch (e) {
        console.error(e);
    }
}

function showSuggestions(suggestions) {
    const dropdown = document.getElementById("search-suggestions");
    if (!dropdown) return;

    if (!suggestions || suggestions.length === 0) {
        hideSuggestions();
        return;
    }

    dropdown.innerHTML = suggestions.map(s => {
        if (s.type === "plugin") {
            return `<div class="suggestion-item" onclick="selectSuggestion('plugin', '${escapeHtml(s.slug)}')">
                <span class="suggestion-icon">${escapeHtml(s.icon || '📦')}</span>
                <span class="suggestion-text">${escapeHtml(s.text)}</span>
                <span class="suggestion-type">plugin</span>
            </div>`;
        } else if (s.type === "author") {
            return `<div class="suggestion-item" onclick="selectSuggestion('author', '${escapeHtml(s.text)}')">
                <span class="suggestion-icon">${escapeHtml(s.icon)}</span>
                <span class="suggestion-text">${escapeHtml(s.text)}</span>
                <span class="suggestion-type">author</span>
            </div>`;
        } else if (s.type === "tag") {
            return `<div class="suggestion-item" onclick="selectSuggestion('tag', '${escapeHtml(s.text)}')">
                <span class="suggestion-icon">${escapeHtml(s.icon)}</span>
                <span class="suggestion-text">${escapeHtml(s.text)}</span>
                <span class="suggestion-type">tag</span>
            </div>`;
        }
    }).join("");

    dropdown.classList.add("open");
}

function hideSuggestions() {
    const dropdown = document.getElementById("search-suggestions");
    if (dropdown) dropdown.classList.remove("open");
}

function selectSuggestion(type, value) {
    if (type === "plugin") {
        // Navigate to plugin detail
        window.location.href = `plugin.html?slug=${value}`;
        return;
    } else if (type === "author") {
        currentFilters.author = value;
        currentFilters.search = "";
        document.getElementById("search-input").value = value;
    } else if (type === "tag") {
        currentFilters.tag = value;
        currentFilters.search = "";
        document.getElementById("search-input").value = value;
    }
    hideSuggestions();
    loadPlugins();
    loadTags();
}

// ============================================================
// RENDER CATEGORIES
// ============================================================

function renderCategories(categories) {
    const bar = document.getElementById("categories-bar");
    if (!bar) return;
    bar.innerHTML = "";

    const allChip = document.createElement("div");
    allChip.className = "category-chip" + (currentFilters.category === "" ? " active" : "");
    allChip.innerHTML = `📁 Tất cả`;
    allChip.onclick = () => {
        currentFilters.category = "";
        loadPlugins();
    };
    bar.appendChild(allChip);

    categories.forEach(cat => {
        const chip = document.createElement("div");
        chip.className = "category-chip" + (currentFilters.category === cat.id ? " active" : "");
        chip.innerHTML = `${escapeHtml(cat.icon)} ${escapeHtml(cat.name)} <span class="cat-count">${escapeHtml(cat.plugin_count || 0)}</span>`;
        chip.onclick = () => {
            currentFilters.category = cat.id;
            loadPlugins();
        };
        bar.appendChild(chip);
    });

    const select = document.getElementById("category-filter");
    if (select) {
        select.innerHTML = '<option value="">📁 Tất cả</option>';
        categories.forEach(cat => {
            const option = document.createElement("option");
            option.value = cat.id;
            option.textContent = `${cat.icon} ${cat.name}`;
            select.appendChild(option);
        });
    }
}
// ============================================================
// RENDER FEATURED
// ============================================================

function renderFeatured() {
    const featured = allPlugins.filter(p => p.featured).slice(0, 3);
    const grid = document.getElementById("featured-grid");
    const section = grid ? grid.closest(".section") : null;

    if (!section) return;

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
    if (!grid) return;

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
        <a href="plugin.html?slug=${escapeHtml(plugin.slug)}" class="plugin-card">
            ${verifiedBadge}
            ${featuredBadge}
            <div class="plugin-icon">${escapeHtml(plugin.icon || "📦")}</div>
            <div class="plugin-name">${escapeHtml(plugin.name)}</div>
            <div class="plugin-author">${escapeHtml(plugin.author)}</div>
            <div class="plugin-desc">${escapeHtml(plugin.description || "")}</div>
            <div class="plugin-meta">
                <span class="plugin-rating">${stars} ${escapeHtml(plugin.rating || "0.0")}</span>
                <span class="plugin-downloads">📥 ${escapeHtml(formatNumber(plugin.downloads || 0))}</span>
            </div>
        </a>
    `;
}

// ============================================================
// FILTER BADGE
// ============================================================

function updateFilterBadge() {
    const badge = document.getElementById("filter-badge");
    if (!badge) return;

    let count = 0;
    if (currentFilters.author) count++;
    if (currentFilters.tag) count++;
    if (currentFilters.min_rating !== null) count++;
    if (currentFilters.price_type) count++;

    if (count > 0) {
        badge.textContent = count;
        badge.style.display = "inline-block";
    } else {
        badge.style.display = "none";
    }
}

function toggleFilterPanel() {
    const panel = document.getElementById("filter-panel");
    if (!panel) return;
    panel.classList.toggle("open");
}

function applyAdvancedFilters() {
    const author = document.getElementById("filter-author").value.trim();
    const minRating = document.getElementById("filter-rating").value;
    const priceType = document.getElementById("filter-price").value;

    currentFilters.author = author;
    currentFilters.min_rating = minRating ? parseFloat(minRating) : null;
    currentFilters.price_type = priceType;

    loadPlugins();
    toggleFilterPanel();
}

function resetFilters() {
    document.getElementById("filter-author").value = "";
    document.getElementById("filter-rating").value = "";
    document.getElementById("filter-price").value = "";

    currentFilters.author = "";
    currentFilters.min_rating = null;
    currentFilters.price_type = "";

    loadPlugins();
    updateFilterBadge();
}

// ============================================================
// HELPERS
// ============================================================
// ============================================================
// SECURITY: Escape HTML
// ============================================================
function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;")
        .replace(/`/g, "&#96;");
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "K";
    return num.toString();
}

function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => toast.classList.remove("show"), 3000);
}

// ============================================================
// EVENTS
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    // Search input with debounce + suggestions
    const searchInput = document.getElementById("search-input");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            const val = e.target.value.trim();
            currentFilters.search = val;
            currentFilters.author = "";
            currentFilters.tag = "";

            clearTimeout(searchSuggestTimeout);
            searchSuggestTimeout = setTimeout(() => {
                loadPlugins();
            }, 300);

            // Fetch suggestions
            clearTimeout(window.__suggestTimeout);
            window.__suggestTimeout = setTimeout(() => {
                fetchSuggestions(val);
            }, 150);
        });

        searchInput.addEventListener("focus", (e) => {
            if (e.target.value.trim()) fetchSuggestions(e.target.value.trim());
        });
    }

    // Hide suggestions when click outside
    document.addEventListener("click", (e) => {
        if (!e.target.closest(".search-box")) {
            hideSuggestions();
        }
    });

    // Category filter
    const catFilter = document.getElementById("category-filter");
    if (catFilter) {
        catFilter.addEventListener("change", (e) => {
            currentFilters.category = e.target.value;
            loadPlugins();
        });
    }

    // Sort filter
    const sortFilter = document.getElementById("sort-filter");
    if (sortFilter) {
        sortFilter.addEventListener("change", (e) => {
            currentFilters.sort = e.target.value;
            loadPlugins();
        });
    }

    // Initial load
    loadStats();
    loadCategories();
    loadTags();
    loadPlugins();
});