// store/web/theme-publish.js
/**
 * Publish Theme UI
 * - Tự động inject nút "🚀 Publish" + modal vào theme-editor.html
 * - User nhập: tên, mô tả, tags, giá bán
 * - POST /api/marketplace/themes
 */
(function () {
  'use strict';

  const API_BASE =
    window.COGNI_API_BASE ||
    (location.hostname === 'localhost'
      ? 'http://localhost:8001'
      : 'https://web-production-8b760.up.railway.app');

  const getToken = () =>
    localStorage.getItem('cognicraft_token') ||
    localStorage.getItem('token') ||
    localStorage.getItem('cogni_token') ||
    '';

  // ============================================================
  // INJECT BUTTON
  // ============================================================
  function injectButton() {
    if (document.getElementById('publish-btn')) return;

    const actions = document.querySelector('.editor-actions');
    if (!actions) {
      setTimeout(injectButton, 200);
      return;
    }

    const btn = document.createElement('button');
    btn.className = 'btn btn-primary';
    btn.id = 'publish-btn';
    btn.innerHTML = '🚀 Publish lên chợ';
    btn.style.background = 'linear-gradient(135deg, #22c55e, #06b6d4)';
    btn.style.color = '#fff';
    btn.style.marginLeft = 'auto';
    btn.onclick = openPublishModal;

    actions.appendChild(btn);
  }

  // ============================================================
  // INJECT MODAL
  // ============================================================
  function injectModal() {
    if (document.getElementById('publish-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'publish-modal';
    modal.style.cssText = `
      position: fixed;
      inset: 0;
      background: rgba(5, 1, 15, 0.85);
      backdrop-filter: blur(20px);
      z-index: 99999;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
    `;

    modal.innerHTML = `
      <div style="
        width: 100%;
        max-width: 600px;
        background: linear-gradient(135deg, rgba(30, 15, 60, 0.98), rgba(20, 8, 45, 0.98));
        border: 1px solid rgba(168, 85, 247, 0.3);
        border-radius: 20px;
        padding: 28px;
        color: #f0e5ff;
        font-family: system-ui, sans-serif;
        box-shadow: 0 40px 100px rgba(168, 85, 247, 0.3);
        max-height: 90vh;
        overflow-y: auto;
      ">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
          <h2 style="margin:0;font-size:22px;font-weight:800;background:linear-gradient(90deg,#22c55e,#06b6d4);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">
            🚀 Publish Theme lên chợ
          </h2>
          <button id="publish-close" style="background:transparent;border:none;color:#a855f7;font-size:24px;cursor:pointer;">✕</button>
        </div>

        <div style="display:flex;flex-direction:column;gap:14px;">
          <div>
            <label style="display:block;font-size:12px;color:#c4b5fd;font-weight:700;margin-bottom:6px;text-transform:uppercase;">Tên theme *</label>
            <input id="pub-name" type="text" placeholder="VD: Neon Dark" maxlength="60"
              style="width:100%;padding:12px 14px;background:#2d1b4e;border:1px solid rgba(168,85,247,0.3);border-radius:10px;color:#fff;font-size:14px;outline:none;">
          </div>

          <div>
            <label style="display:block;font-size:12px;color:#c4b5fd;font-weight:700;margin-bottom:6px;text-transform:uppercase;">Mô tả ngắn (max 200)</label>
            <textarea id="pub-desc" placeholder="Theme này có gì đặc biệt?" maxlength="200" rows="2"
              style="width:100%;padding:12px 14px;background:#2d1b4e;border:1px solid rgba(168,85,247,0.3);border-radius:10px;color:#fff;font-size:14px;resize:vertical;outline:none;font-family:inherit;"></textarea>
          </div>

          <div>
            <label style="display:block;font-size:12px;color:#c4b5fd;font-weight:700;margin-bottom:6px;text-transform:uppercase;">Tags (phân cách bằng dấu phẩy)</label>
            <input id="pub-tags" type="text" placeholder="dark, neon, cyberpunk"
              style="width:100%;padding:12px 14px;background:#2d1b4e;border:1px solid rgba(168,85,247,0.3);border-radius:10px;color:#fff;font-size:14px;outline:none;">
          </div>

          <div>
            <label style="display:block;font-size:12px;color:#c4b5fd;font-weight:700;margin-bottom:6px;text-transform:uppercase;">💰 Giá bán</label>
            <div style="display:flex;gap:8px;">
              <label style="flex:1;padding:12px;background:rgba(34,197,94,0.15);border:2px solid rgba(34,197,94,0.3);border-radius:10px;cursor:pointer;text-align:center;transition:all 0.2s;" id="pub-free-label">
                <input type="radio" name="pub-price" value="0" checked style="margin-right:6px;">
                <span style="font-weight:700;color:#4ade80;">Miễn phí</span>
              </label>
              <label style="flex:1;padding:12px;background:rgba(251,191,36,0.1);border:2px solid rgba(251,191,36,0.2);border-radius:10px;cursor:pointer;text-align:center;transition:all 0.2s;" id="pub-paid-label">
                <input type="radio" name="pub-price" value="paid" style="margin-right:6px;">
                <span style="font-weight:700;color:#fbbf24;">Trả phí</span>
              </label>
            </div>
            <div id="pub-price-input-wrap" style="display:none;margin-top:10px;">
              <input id="pub-price" type="number" min="1000" step="1000" placeholder="VD: 49000" value="49000"
                style="width:100%;padding:12px 14px;background:#2d1b4e;border:1px solid rgba(251,191,36,0.3);border-radius:10px;color:#fff;font-size:14px;outline:none;">
              <div style="font-size:11px;color:#a78bfa;margin-top:6px;">Đơn vị: VNĐ. Đề xuất: 19K, 49K, 99K, 149K</div>
              <div id="pub-price-preview" style="font-size:13px;color:#fbbf24;margin-top:6px;font-weight:700;"></div>
            </div>
          </div>

          <div id="publish-alert" style="display:none;padding:12px;border-radius:10px;font-size:13px;font-weight:600;"></div>

          <div style="display:flex;gap:10px;margin-top:10px;">
            <button id="pub-submit" style="flex:2;padding:14px;background:linear-gradient(135deg,#22c55e,#06b6d4);color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:800;cursor:pointer;letter-spacing:0.5px;">
              🚀 PUBLISH NGAY
            </button>
            <button id="pub-cancel" style="flex:1;padding:14px;background:rgba(168,85,247,0.15);color:#c4b5fd;border:1px solid rgba(168,85,247,0.3);border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;">
              Hủy
            </button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // Bind events
    document.getElementById('publish-close').onclick = closePublishModal;
    document.getElementById('pub-cancel').onclick = closePublishModal;
    document.getElementById('pub-submit').onclick = submitPublish;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) closePublishModal();
    });

    // Price toggle
    document.querySelectorAll('input[name="pub-price"]').forEach((radio) => {
      radio.addEventListener('change', (e) => {
        const isPaid = e.target.value === 'paid';
        const wrap = document.getElementById('pub-price-input-wrap');
        const freeLabel = document.getElementById('pub-free-label');
        const paidLabel = document.getElementById('pub-paid-label');

        wrap.style.display = isPaid ? 'block' : 'none';
        freeLabel.style.borderColor = isPaid ? 'rgba(34,197,94,0.15)' : 'rgba(34,197,94,0.8)';
        paidLabel.style.borderColor = isPaid ? 'rgba(251,191,36,0.8)' : 'rgba(251,191,36,0.2)';

        if (isPaid) updatePricePreview();
      });
    });

    document.getElementById('pub-price')?.addEventListener('input', updatePricePreview);
  }

  function updatePricePreview() {
    const input = document.getElementById('pub-price');
    const preview = document.getElementById('pub-price-preview');
    if (!input || !preview) return;

    const val = parseInt(input.value) || 0;
    if (val >= 1000) {
      preview.textContent = `→ ${(val / 1000).toFixed(0)}K VNĐ`;
    } else {
      preview.textContent = '';
    }
  }

  function openPublishModal() {
    const modal = document.getElementById('publish-modal');
    if (modal) modal.style.display = 'flex';
  }

  function closePublishModal() {
    const modal = document.getElementById('publish-modal');
    if (modal) modal.style.display = 'none';
    const alert = document.getElementById('publish-alert');
    if (alert) alert.style.display = 'none';
  }

  function showAlert(msg, type = 'error') {
    const alert = document.getElementById('publish-alert');
    if (!alert) return;
    alert.style.display = 'block';
    if (type === 'error') {
      alert.style.background = 'rgba(239,68,68,0.2)';
      alert.style.color = '#fca5a5';
      alert.style.border = '1px solid rgba(239,68,68,0.4)';
    } else {
      alert.style.background = 'rgba(34,197,94,0.2)';
      alert.style.color = '#4ade80';
      alert.style.border = '1px solid rgba(34,197,94,0.4)';
    }
    alert.textContent = msg;
  }

  // ============================================================
  // SUBMIT
  // ============================================================
  async function submitPublish() {
    const nameEl = document.getElementById('pub-name');
    const descEl = document.getElementById('pub-desc');
    const tagsEl = document.getElementById('pub-tags');
    const priceRadio = document.querySelector('input[name="pub-price"]:checked');
    const priceEl = document.getElementById('pub-price');
    const cssEl = document.getElementById('css-editor');

    const name = nameEl.value.trim();
    const description = descEl.value.trim();
    const tags = tagsEl.value
      .split(',')
      .map((t) => t.trim().toLowerCase())
      .filter((t) => t);
    const isPaid = priceRadio?.value === 'paid';
    const priceVnd = isPaid ? parseInt(priceEl.value) || 0 : 0;
    const cssContent = cssEl?.value || '';

    // Validate
    if (!name || name.length < 3) {
      showAlert('Tên theme phải có ít nhất 3 ký tự', 'error');
      return;
    }
    if (!cssContent || cssContent.length < 10) {
      showAlert('CSS theme trống — viết CSS trước khi publish', 'error');
      return;
    }
    if (isPaid && priceVnd < 1000) {
      showAlert('Giá bán tối thiểu 1.000 VNĐ', 'error');
      return;
    }

    const token = getToken();
    if (!token) {
      showAlert('Bạn cần login trước', 'error');
      return;
    }

    const submitBtn = document.getElementById('pub-submit');
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Đang publish...';

    try {
      const res = await fetch(API_BASE + '/api/marketplace/themes', {
        method: 'POST',
        headers: {
          Authorization: 'Bearer ' + token,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          description,
          css_content: cssContent,
          tags,
          price_vnd: priceVnd,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        showAlert(data.detail || `Lỗi ${res.status}`, 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = '🚀 PUBLISH NGAY';
        return;
      }

      showAlert('✅ Publish thành công! Đang chuyển sang chợ...', 'success');

      setTimeout(() => {
        window.location.href = `marketplace.html?theme=${data.slug}`;
      }, 1500);
    } catch (e) {
      showAlert('Lỗi kết nối: ' + e.message, 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = '🚀 PUBLISH NGAY';
    }
  }

  // ============================================================
  // INIT
  // ============================================================
  function init() {
    injectButton();
    injectModal();
    console.log('✅ Theme publish UI loaded');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();