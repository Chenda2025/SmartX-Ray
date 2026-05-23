/* ════════════════════════════════════════════════════════════════════════════
   static/js/user.js  —  User-facing utilities for SmartX-Ray
   ────────────────────────────────────────────────────────────────────────────
   Responsibilities:
     • TierGate   — detect free/pro tier, lock/unlock PDF & features
     • AdBanner   — load ad from API, render, handle dismiss & click tracking
     • ScanUpload — file selection preview, drag-and-drop, quota guard, submit
     • HeatmapToggle — toggle between original X-ray and Grad-CAM overlay
   ────────────────────────────────────────────────────────────────────────────
   Depends on: api.js (User, Auth, api, showToast, showLoading, hideLoading)
               i18n.js (I18n)
   Load order: base.html loads i18n.js → api.js → user.js (in {% block scripts %}
               or via a <script src="/static/js/user.js"></script> in base.html)
   ════════════════════════════════════════════════════════════════════════════ */

/* ── Namespace guard: only define once even if script is included twice ─── */
if (typeof UserKit === 'undefined') {

/* ══════════════════════════════════════════════════════════════════════════
   TierGate
   ──────────────────────────────────────────────────────────────────────────
   Reads the current user's tier from User.get() and exposes helpers that
   show/hide or enable/disable elements across every user-facing page.

   Usage:
     await TierGate.init();          // call once after Auth.requireLogin()
     TierGate.isPro                  // boolean
     TierGate.guard(elem, msg)       // grey out + click-toast on locked elem
     TierGate.applyAll()             // scan DOM for [data-pro-only] attrs
   ══════════════════════════════════════════════════════════════════════════ */
const TierGate = (() => {
  let _isPro = false;

  /**
   * Initialise from cached User or fresh /api/auth/me call.
   * @returns {Promise<object>} user object
   */
  async function init() {
    const user = User.get() || await Auth.me();
    if (!user) return null;
    _isPro = user.tier === 'pro';
    applyAll();
    return user;
  }

  /** Read-only tier flag. */
  const isPro = () => _isPro;

  /**
   * Visually lock an element and attach a toast on click.
   * @param {HTMLElement} elem
   * @param {string}      [msg] — toast message (falls back to i18n key)
   */
  function guard(elem, msg) {
    if (!elem) return;
    elem.classList.add('pdf-locked');
    elem.setAttribute('title', msg || I18n.t('dash_pdf_locked'));
    elem.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      showToast(msg || (I18n.t('dash_pro_pdf') + ' — Upgrade to Pro!'), 'warning');
    });
  }

  /**
   * Walk the DOM looking for elements with these data attributes:
   *
   *   data-pro-only         → hide (add d-none) if user is free
   *   data-free-only        → hide (add d-none) if user is pro
   *   data-pro-locked       → call guard() if user is free
   */
  function applyAll() {
    /* [data-pro-only]: visible for pro, hidden for free */
    document.querySelectorAll('[data-pro-only]').forEach(el => {
      el.classList.toggle('d-none', !_isPro);
    });

    /* [data-free-only]: visible for free, hidden for pro */
    document.querySelectorAll('[data-free-only]').forEach(el => {
      el.classList.toggle('d-none', _isPro);
    });

    /* [data-pro-locked]: lock for free users (show but disable) */
    if (!_isPro) {
      document.querySelectorAll('[data-pro-locked]').forEach(el => {
        const msg = el.getAttribute('data-pro-locked') || undefined;
        guard(el, msg);
      });
    }
  }

  return { init, isPro, guard, applyAll };
})();

/* ══════════════════════════════════════════════════════════════════════════
   AdBanner
   ──────────────────────────────────────────────────────────────────────────
   Fetches an ad from /api/ads?placement=<type>, renders it into a container,
   and wires dismiss + click-tracking.

   Usage:
     await AdBanner.load('banner',  'bannerAdWrap');
     await AdBanner.load('sidebar', 'sidebarAdWrap');
   ══════════════════════════════════════════════════════════════════════════ */
const AdBanner = (() => {
  /**
   * Render an ad object into a container element.
   * @param {object} ad         — ad record from API
   * @param {string} containerId — id of wrapper div
   */
  function _render(ad, containerId) {
    const wrap = document.getElementById(containerId);
    if (!wrap) return;
    wrap.classList.remove('d-none');
    wrap.innerHTML = `
      <div class="card ad-card p-3 border-0 shadow-sm position-relative">
        <!-- Dismiss button -->
        <button type="button"
                class="btn-close btn-sm position-absolute"
                style="top:8px;right:8px;opacity:.4;font-size:10px;"
                aria-label="Dismiss ad"
                onclick="AdBanner.dismiss('${containerId}')"></button>

        <span class="ad-label">${I18n.t('dash_advertisement') || 'Advertisement'}</span>

        <div class="d-flex align-items-center gap-3 mt-2">
          ${ad.image_url
            ? `<img src="${ad.image_url}" alt=""
                    style="height:44px;width:44px;object-fit:cover;
                           border-radius:8px;flex-shrink:0;">`
            : ''}
          <div class="flex-grow-1 overflow-hidden">
            <div class="fw-semibold small text-truncate">${_esc(ad.title)}</div>
            <div class="text-muted small">${_esc(ad.body || '')}</div>
          </div>
          <a href="#"
             onclick="AdBanner.click(${ad.id},'${_escAttr(ad.target_url)}');return false;"
             class="btn btn-sm btn-outline-secondary flex-shrink-0">
            ${I18n.t('dash_learn_more') || 'Learn More'}
          </a>
        </div>
      </div>`;
  }

  /** Escape HTML special chars for text content */
  function _esc(str) {
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  /** Escape for inline event attribute values */
  function _escAttr(str) {
    return String(str).replace(/'/g, "\\'");
  }

  /**
   * Load an ad for the given placement and render it.
   * Silently swallows errors — ads are non-critical.
   * @param {'banner'|'sidebar'|'result_page'|'interstitial'} placement
   * @param {string} containerId
   */
  async function load(placement, containerId) {
    try {
      const res  = await api.get(`/ads?placement=${encodeURIComponent(placement)}`);
      const data = await res.json();
      const ad   = data.ads?.[0];
      if (ad) _render(ad, containerId);
    } catch {
      /* non-critical — do nothing */
    }
  }

  /**
   * Record a click impression and open the target URL.
   * @param {number} adId
   * @param {string} targetUrl
   */
  async function click(adId, targetUrl) {
    try { await fetch(`/api/ads/${adId}/click`, { method: 'POST' }); } catch {}
    window.open(targetUrl, '_blank', 'noopener,noreferrer');
  }

  /**
   * Slide-dismiss an ad container with a smooth collapse.
   * @param {string} containerId
   */
  function dismiss(containerId) {
    const wrap = document.getElementById(containerId);
    if (!wrap) return;
    wrap.style.transition = 'opacity .25s, max-height .3s';
    wrap.style.opacity    = '0';
    wrap.style.maxHeight  = wrap.offsetHeight + 'px';
    requestAnimationFrame(() => {
      wrap.style.maxHeight = '0';
      wrap.style.overflow  = 'hidden';
      setTimeout(() => wrap.classList.add('d-none'), 320);
    });
  }

  return { load, click, dismiss };
})();

/* ══════════════════════════════════════════════════════════════════════════
   ScanUpload
   ──────────────────────────────────────────────────────────────────────────
   Self-contained controller for the X-ray upload zone.  Attach it to an
   existing drop-zone element, then call ScanUpload.init(opts).

   opts = {
     dropZoneId    : 'dropZone',       // required
     fileInputId   : 'fileInput',      // required
     previewSectId : 'previewSection', // required
     previewImgId  : 'previewImg',     // required
     previewNameId : 'previewName',    // required
     analyseBtnId  : 'analyseBtn',     // required
     spinnerId     : 'uploadSpinner',  // required
     quotaTextId   : 'quotaText',      // optional (free-tier guard)
     quotaAlertId  : 'quotaAlert',     // optional
     quotaLimit    : 3,                // optional (default 3)
     isPro         : false,            // optional
     onSuccess     : (data) => { window.location.href = `/scan/${data.id}`; },
   }
   ══════════════════════════════════════════════════════════════════════════ */
const ScanUpload = (() => {
  let _opts     = {};
  let _file     = null;

  function init(opts = {}) {
    _opts = {
      dropZoneId   : 'dropZone',
      fileInputId  : 'fileInput',
      previewSectId: 'previewSection',
      previewImgId : 'previewImg',
      previewNameId: 'previewName',
      analyseBtnId : 'analyseBtn',
      spinnerId    : 'uploadSpinner',
      quotaLimit   : 3,
      isPro        : false,
      onSuccess    : d => { window.location.href = `/scan/${d.id}`; },
      ...opts,
    };
    _bindDrop();
    _bindFileInput();
  }

  /* ── File selected (via input or drop) ──────────────────────────────── */
  function _onFileSelected(file) {
    if (!file) return;
    _file = file;
    const reader = new FileReader();
    reader.onload = e => {
      _el('previewImgId').src          = e.target.result;
      _el('previewNameId').textContent = file.name;
      _el('previewSectId').classList.remove('d-none');
    };
    reader.readAsDataURL(file);
  }

  /** Clear preview and reset state */
  function clear() {
    _file = null;
    const fi = _el('fileInputId');
    if (fi) fi.value = '';
    _el('previewSectId').classList.add('d-none');
  }

  /* ── Submit scan ─────────────────────────────────────────────────────── */
  async function submit() {
    if (!_file) return;

    /* Quota guard for free users */
    if (!_opts.isPro) {
      const quotaEl = document.getElementById(_opts.quotaTextId);
      if (quotaEl) {
        const used = parseInt(quotaEl.textContent) || 0;
        if (used >= (_opts.quotaLimit || 3)) {
          showToast(
            (I18n.t('dash_quota_exceeded') || 'Daily limit reached.') + ' ' +
            (I18n.t('dash_upgrade_link')   || 'Upgrade for unlimited →'),
            'warning'
          );
          const alertEl = document.getElementById(_opts.quotaAlertId);
          if (alertEl) alertEl.classList.remove('d-none');
          return;
        }
      }
    }

    const spinner = _el('spinnerId');
    const btn     = _el('analyseBtnId');
    if (spinner) spinner.classList.remove('d-none');
    if (btn)     btn.disabled = true;
    showLoading(I18n.t('dash_analysing') || 'Analysing…');

    try {
      const form = new FormData();
      form.append('file', _file);
      const res  = await api.upload('/scan/upload', form);
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || I18n.t('dash_upload_failed') || 'Upload failed.', 'danger');
        return;
      }
      showToast(I18n.t('dash_analysis_done') || 'Analysis complete!', 'success');
      _opts.onSuccess(data);
    } catch {
      showToast(I18n.t('dash_error') || 'An error occurred.', 'danger');
    } finally {
      if (spinner) spinner.classList.add('d-none');
      if (btn)     btn.disabled = false;
      hideLoading();
    }
  }

  /* ── Drag-and-drop wiring ────────────────────────────────────────────── */
  function _bindDrop() {
    const zone = document.getElementById(_opts.dropZoneId);
    if (!zone) return;
    zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', ()  => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('dragover');
      const file = e.dataTransfer.files[0];
      if (!file) return;
      /* Sync into the file input so form serialisation still works */
      const dt = new DataTransfer();
      dt.items.add(file);
      const fi = document.getElementById(_opts.fileInputId);
      if (fi) fi.files = dt.files;
      _onFileSelected(file);
    });
  }

  function _bindFileInput() {
    const fi = document.getElementById(_opts.fileInputId);
    if (!fi) return;
    fi.addEventListener('change', () => {
      if (fi.files[0]) _onFileSelected(fi.files[0]);
    });
  }

  /** Resolve an option key to a DOM element */
  function _el(optKey) {
    return document.getElementById(_opts[optKey]);
  }

  return { init, clear, submit };
})();

/* ══════════════════════════════════════════════════════════════════════════
   HeatmapToggle
   ──────────────────────────────────────────────────────────────────────────
   On the result page, toggles the main image between the original X-ray
   and the Grad-CAM heatmap overlay.

   Markup expected:
     <img id="mainViewer" src="<original>" data-heat="<heatmap>" ... />
     <button onclick="HeatmapToggle.toggle()" id="heatmapBtn">Show Heatmap</button>

   Usage:
     HeatmapToggle.init('mainViewer', 'heatmapBtn');
     // or let it auto-discover via [data-heat] attribute
     HeatmapToggle.init();
   ══════════════════════════════════════════════════════════════════════════ */
const HeatmapToggle = (() => {
  let _img      = null;
  let _btn      = null;
  let _original = '';
  let _heat     = '';
  let _showing  = false;   // false = original, true = heatmap

  /**
   * @param {string} [imgId='mainViewer']
   * @param {string} [btnId='heatmapBtn']
   */
  function init(imgId = 'mainViewer', btnId = 'heatmapBtn') {
    _img = document.getElementById(imgId);
    _btn = document.getElementById(btnId);
    if (!_img) return;
    _original = _img.src;
    _heat     = _img.dataset.heat || '';
    if (!_heat && _btn) _btn.classList.add('d-none');
  }

  /** Toggle between original and heatmap. */
  function toggle() {
    if (!_img || !_heat) return;
    _showing = !_showing;
    _img.style.opacity = '0';

    setTimeout(() => {
      _img.src = _showing ? _heat : _original;
      _img.style.transition = 'opacity .25s';
      _img.style.opacity    = '1';
    }, 150);

    if (_btn) {
      _btn.innerHTML = _showing
        ? '<i class="fa-solid fa-xray me-1"></i>' +
          (I18n.t('dash_show_original') || 'Show Original')
        : '<i class="fa-solid fa-fire me-1"></i>' +
          (I18n.t('dash_show_heatmap')  || 'Show Heatmap');
    }
  }

  /** Show heatmap directly (e.g. after page load if pneumonia detected). */
  function showHeat() { if (!_showing) toggle(); }

  /** Restore original directly. */
  function showOriginal() { if (_showing) toggle(); }

  return { init, toggle, showHeat, showOriginal };
})();

/* ── Expose globals ──────────────────────────────────────────────────── */
window.TierGate      = TierGate;
window.AdBanner      = AdBanner;
window.ScanUpload    = ScanUpload;
window.HeatmapToggle = HeatmapToggle;

} /* end UserKit guard */
