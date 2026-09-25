// ============================================================
// COGNICRAFT AUTH — Google Sign-In (GIS)
// ============================================================
(function () {
    'use strict';

    // ⚠️ Thay Client ID nếu cần
    const GOOGLE_CLIENT_ID = "426541573663-cksl4s1t4qrv2gr0fa4f191404u0imnc.apps.googleusercontent.com";

    const STORAGE_KEY_TOKEN = "cognicraft_token";
    const STORAGE_KEY_USER = "cognicraft_user";

    const API_URL = window.STORE_API || "http://localhost:8001";

    // ============================================================
    // STATE
    // ============================================================
    let currentUser = null;

    function getToken() {
        try { return localStorage.getItem(STORAGE_KEY_TOKEN); }
        catch (e) { return null; }
    }

    function saveSession(token, user) {
        try {
            localStorage.setItem(STORAGE_KEY_TOKEN, token);
            localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
        } catch (e) {}
    }

    function clearSession() {
        try {
            localStorage.removeItem(STORAGE_KEY_TOKEN);
            localStorage.removeItem(STORAGE_KEY_USER);
        } catch (e) {}
        currentUser = null;
    }

    function loadUserFromStorage() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY_USER);
            if (raw) currentUser = JSON.parse(raw);
        } catch (e) {
            currentUser = null;
        }
        return currentUser;
    }

    // ============================================================
    // CALLBACK từ Google
    // ============================================================
    async function handleCredentialResponse(response) {
        const credential = response.credential;

        try {
            const r = await fetch(`${API_URL}/api/auth/google`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ credential }),
            });

            const data = await r.json();
            if (!r.ok || !data.success) {
                throw new Error(data.detail || `HTTP ${r.status}`);
            }

            saveSession(data.token, data.user);
            currentUser = data.user;

            showToast(`✅ Xin chào ${data.user.name}!`, "success");
            updateAuthUI();

            // Reload page sau 800ms để refresh state
            setTimeout(() => window.location.reload(), 800);

        } catch (e) {
            console.error("[Auth] Login error:", e);
            showToast(`❌ Login thất bại: ${e.message}`, "error");
        }
    }

    // ============================================================
    // LOGOUT
    // ============================================================
    function logout() {
        clearSession();
        showToast("👋 Đã đăng xuất", "info");
        setTimeout(() => window.location.reload(), 500);
    }

    // ============================================================
    // UPDATE UI — Header
    // ============================================================
    function updateAuthUI() {
        const container = document.getElementById("auth-container");
        if (!container) return;

        const user = loadUserFromStorage();

        if (user) {
            // Logged in — show avatar + name + logout
            const initial = (user.name || "?").charAt(0).toUpperCase();
            container.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.6rem;">
                    <a href="user.html?username=${encodeURIComponent((user.name || 'user').toLowerCase().replace(/\\s+/g, '_'))}" style="display: flex; align-items: center; gap: 0.5rem; text-decoration: none;">
                        ${user.avatar_url ? `
                            <img src="${user.avatar_url}" alt="${escapeHtml(user.name)}" style="width: 32px; height: 32px; border-radius: 50%; border: 2px solid var(--cyan);" referrerpolicy="no-referrer">
                        ` : `
                            <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, var(--green), var(--cyan)); display: flex; align-items: center; justify-content: center; font-weight: 700; color: var(--bg); font-size: 0.85rem;">${escapeHtml(initial)}</div>
                        `}
                        <span style="color: var(--text); font-size: 0.8rem; font-weight: 700;">${escapeHtml(user.name)}</span>
                    </a>
                    <button onclick="CogniAuth.logout()" style="background: transparent; border: 1px solid var(--border); color: var(--dim); padding: 0.4rem 0.7rem; border-radius: 6px; cursor: pointer; font-family: inherit; font-size: 0.75rem;" onmouseover="this.style.color='var(--red)'; this.style.borderColor='var(--red)'" onmouseout="this.style.color='var(--dim)'; this.style.borderColor='var(--border)'">Logout</button>
                </div>
            `;
        } else {
            // Not logged in — show Google Sign-In button
            container.innerHTML = `
                <div id="g_id_onload"
                     data-client_id="${GOOGLE_CLIENT_ID}"
                     data-callback="CogniAuth.handleGoogleCallback"
                     data-auto_prompt="false">
                </div>
                <div class="g_id_signin"
                     data-type="standard"
                     data-size="medium"
                     data-theme="filled_black"
                     data-text="signin_with"
                     data-shape="pill"
                     data-logo_alignment="left">
                </div>
            `;

            // Re-init GIS
            if (window.google && window.google.accounts) {
                window.google.accounts.id.initialize({
                    client_id: GOOGLE_CLIENT_ID,
                    callback: handleCredentialResponse,
                });
                window.google.accounts.id.renderButton(
                    container.querySelector(".g_id_signin") || container,
                    { theme: "filled_black", size: "medium", shape: "pill", text: "signin_with" }
                );
            }
        }
    }

    // ============================================================
    // GET USER INFO (for review form etc.)
    // ============================================================
    function getUser() {
        return loadUserFromStorage();
    }

    function getAuthHeader() {
        const token = getToken();
        return token ? { "Authorization": `Bearer ${token}` } : {};
    }

    // ============================================================
    // HELPERS
    // ============================================================
    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function showToast(message, type = "info") {
        const toast = document.getElementById("toast");
        if (!toast) return;
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        setTimeout(() => toast.classList.remove("show"), 3000);
    }

    // ============================================================
    // INIT
    // ============================================================
    function init() {
        loadUserFromStorage();

        // Wait for Google SDK loaded
        const waitForGoogle = setInterval(() => {
            if (window.google && window.google.accounts) {
                clearInterval(waitForGoogle);
                window.google.accounts.id.initialize({
                    client_id: GOOGLE_CLIENT_ID,
                    callback: handleCredentialResponse,
                });
                updateAuthUI();
            }
        }, 100);

        // Timeout 5s
        setTimeout(() => clearInterval(waitForGoogle), 5000);
    }

    // ============================================================
    // PUBLIC API
    // ============================================================
    window.CogniAuth = {
        init,
        logout,
        getUser,
        getAuthHeader,
        handleGoogleCallback: handleCredentialResponse,
        updateAuthUI,
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();