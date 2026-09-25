// config.js — Auto-detect API URL theo environment
window.STORE_API = (location.hostname === "localhost" ||
                    location.hostname === "127.0.0.1" ||
                    location.protocol === "file:")
    ? "http://localhost:8001"
    : "https://web-production-8b760.up.railway.app";