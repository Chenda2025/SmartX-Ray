/* ═══════════════════════════════════════════════════════════════════════════
   user-dashboard.js  —  SmartX-Ray User Dashboard
   Figma Blueprint: SmartXRay_User_Dashboard_Complete
   Depends on: i18n.js, api.js
   ═══════════════════════════════════════════════════════════════════════════ */

/* ── State ───────────────────────────────────────────────────────────────── */
let UD = {
  isPro:        false,
  user:         null,
  currentScanData: null,
  scanPage:     1,
  allScans:     [],
  scanMap:      {},          // id → scan object, for quick modal lookup
  doctors:      [],            // loaded from /api/marketplace/doctors
  doctorFilter: 'all',
  selectedDate: null,
  selectedTime: null,
  activeDoctorId:    null,
  activeDoctorFee:   15,
  activeDoctorName:  '',
  activeDoctorSpec:  '',
  activeDoctorColor: { bg:'#EEF2FF', color:'#6366F1' },
  bookedAppointments: [],
  uploadedFile: null,
  zoomLevel: 1,
  currentImageUrl: null,
  currentHeatmapUrl: null,
};

/* SDM = Scan Detail Modal state */
let SDM = { zoomLevel: 1, reportId: null, imageUrl: null };

/* ── Doctor colour palette — assigned by index ───────────────────────────── */
const _DOC_PALETTE = [
  { bg:'#EEF2FF', color:'#6366F1' },
  { bg:'#ECFDF5', color:'#10B981' },
  { bg:'#FEF3C7', color:'#F59E0B' },
  { bg:'#FEF2F2', color:'#EF4444' },
  { bg:'#F0FDF4', color:'#059669' },
  { bg:'#FFF7ED', color:'#EA580C' },
];

/* ════════════════════════════════════════════════════════════════════════════
   BOOTSTRAP — runs on DOMContentLoaded
   ════════════════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  /* Require login — redirect if no token */
  if (!Token.access) {
    window.location.href = '/login';
    return;
  }

  /* Load user */
  UD.user = User.get() || await Auth.me();
  if (!UD.user) { window.location.href = '/login'; return; }

  UD.isPro = UD.user.tier === 'pro';
  if (UD.isPro) document.body.classList.add('is-pro');

  /* Apply i18n default */
  I18n.applyAll();

  udInitNav();
  udInitWelcome();
  udInitQuickCards();
  udInitUploadPanel();
  udInitResultPanel();
  await udLoadHistory();
  udInitDoctors();
  udInitAppointments();
  udInitUpgradeBanner();
  udInitAds();
});

/* ════════════════════════════════════════════════════════════════════════════
   1. NAVIGATION
   ════════════════════════════════════════════════════════════════════════════ */
function udInitNav() {
  const u = UD.user;
  /* Avatar initials */
  const initials = (u.full_name || u.email || '?').slice(0,2).toUpperCase();
  document.getElementById('udAvatar').textContent = initials;

  /* Dropdown info */
  document.getElementById('ddName').textContent  = u.full_name  || '—';
  document.getElementById('ddEmail').textContent = u.email || '—';

  /* Tier badge */
  const badge = document.getElementById('udTierBadge');
  if (UD.isPro) {
    badge.textContent = 'Pro ⭐';
    badge.className   = 'ud-tier-badge pro';
  } else {
    badge.textContent = 'Free';
    badge.className   = 'ud-tier-badge free';
  }

  /* Close dropdown on outside click */
  document.addEventListener('click', e => {
    const wrap = document.querySelector('.ud-avatar-wrap');
    if (wrap && !wrap.contains(e.target)) {
      document.getElementById('udDropdown').classList.remove('open');
    }
  });

  /* Active nav + tab highlight on scroll */
  const _udSections = ['scan-section','history-section','doctor-section','appt-section'];
  const _udAllLinks = document.querySelectorAll('.ud-nav-links a[data-section], .ud-tab-bar a[data-section]');
  window.addEventListener('scroll', _udUpdateActiveNav, { passive: true });
  _udUpdateActiveNav();
}

function _udUpdateActiveNav() {
  const sections = ['scan-section','history-section','doctor-section','appt-section'];
  let current = '';
  sections.forEach(id => {
    const el = document.getElementById(id);
    if (el && window.scrollY >= el.offsetTop - 100) current = id;
  });
  document.querySelectorAll('.ud-nav-links a[data-section], .ud-tab-bar a[data-section]').forEach(a => {
    const ds = a.dataset.section;
    a.classList.toggle('active', current ? ds === current : ds === 'top');
  });
}

/* ── udScrollTo — in-page smooth scroll, never leaves the dashboard ── */
function udScrollTo(sectionId) {
  if (sectionId === 'top') {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else {
    const el = document.getElementById(sectionId);
    if (!el) return;
    const navH = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--nav-height')
    ) || 64;
    const top = el.getBoundingClientRect().top + window.scrollY - navH - 16;
    window.scrollTo({ top, behavior: 'smooth' });
  }
  // Let the scroll listener update active states naturally
}

function udToggleDropdown() {
  document.getElementById('udDropdown').classList.toggle('open');
}

function udLogout() {
  Auth.logout();
  window.location.href = '/login';
}

/* ── Language toggle ────────────────────────────────────────────────────── */
function udToggleLang() {
  I18n.toggle();
  const btn = document.getElementById('udLangBtn');
  btn.textContent = I18n.getLang() === 'km' ? 'English' : 'ខ្មែរ';
  /* Refresh greeting */
  udSetGreeting();
  /* Refresh dynamic content */
  udRefreshDynamicI18n();
}

function udRefreshDynamicI18n() {
  /* Re-render history, doctors to pick up lang change */
  udRenderHistory(UD.allScans);
  udRenderDoctors();
  udRenderAppointments();
  udRefreshQuota();
}

/* ════════════════════════════════════════════════════════════════════════════
   2. AD BANNER
   ════════════════════════════════════════════════════════════════════════════ */
async function udInitAds() {
  if (UD.isPro) return;
  /* Try to load real ad */
  try {
    const res  = await api.get('/ads?placement=banner');
    const data = await res.json();
    if (data && data.ads && data.ads.length > 0) {
      const ad = data.ads[0];
      const img = document.getElementById('udAdImg');
      if (ad.image_url) {
        img.innerHTML = `<img src="${ad.image_url}" alt="Ad" />`;
      }
      document.getElementById('udAdText').textContent =
        (I18n.getLang() === 'km' ? 'ឧបត្ថម្ភ — ' : 'Sponsored — ') +
        (ad.advertiser || 'Cambodia Medical Supplies');
    }
  } catch { /* use default */ }
  document.getElementById('udAdBanner').classList.remove('ud-hidden');
}

/* ════════════════════════════════════════════════════════════════════════════
   3. WELCOME BANNER
   ════════════════════════════════════════════════════════════════════════════ */
function udInitWelcome() {
  udSetGreeting();
  const sub = document.getElementById('udWelcomeSub');
  const uni  = UD.user.university || 'RUPP';
  const plan = UD.isPro ? 'Pro Plan ⭐' : (I18n.t('plan_free') || 'Free Plan');
  sub.textContent = `${uni} · ${plan}`;
}

function udSetGreeting() {
  const h   = new Date().getHours();
  let greet;
  const name = (UD.user?.full_name || '').split(' ')[0] || 'there';
  if (I18n.getLang() === 'km') {
    greet = h < 12 ? 'អរុណសួស្តី' : h < 17 ? 'ទិវាសួស្តី' : 'សាយណ្ហសួស្តី';
    document.getElementById('udGreeting').textContent = `${greet} ${name}`;
  } else {
    greet = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
    document.getElementById('udGreeting').textContent = `${greet}, ${name}`;
  }
}

/* ════════════════════════════════════════════════════════════════════════════
   4. QUICK ACTION CARDS
   ════════════════════════════════════════════════════════════════════════════ */
function udInitQuickCards() {
  /* PDF card: unlock for pro */
  const pdfCard = document.getElementById('udPdfCard');
  if (UD.isPro) {
    pdfCard.className = 'ud-qcard ud-qcard-pdf-unlocked';
    pdfCard.onclick   = null;
    pdfCard.querySelector('.qcard-lock-overlay').remove();
    pdfCard.querySelector('.qcard-pro-badge').remove();
    pdfCard.querySelector('.qcard-icon').className = 'ti ti-file-description qcard-icon';
    pdfCard.querySelector('.qcard-label').style.color = 'var(--text-primary)';
    const sub = pdfCard.querySelector('.qcard-sub');
    sub.setAttribute('data-i18n', 'qcard_pdf_sub_pro');
    sub.textContent = I18n.t('qcard_pdf_sub_pro') || 'Export AI diagnosis report';
  }
}

/* ════════════════════════════════════════════════════════════════════════════
   5. SCAN UPLOAD PANEL
   ════════════════════════════════════════════════════════════════════════════ */
function udInitUploadPanel() {
  udRefreshQuota();
}

function udRefreshQuota() {
  const el = document.getElementById('udQuotaText');
  if (!el) return;
  if (UD.isPro) {
    el.textContent = I18n.t('quota_pro') || 'Pro plan: Unlimited scans';
    el.classList.add('pro');
  } else {
    const used  = UD.user?.scans_today ?? 0;
    const limit = 5;
    const rem   = Math.max(0, limit - used);
    const lbl   = I18n.t('quota_free') || 'Free plan: 5 scans/month · remaining:';
    el.textContent = `${lbl} ${rem}`;
    el.classList.remove('pro');
  }
}

/* ── Drag & Drop ─────────────────────────────────────────────────────────── */
function udDragOver(e) {
  e.preventDefault();
  document.getElementById('udDropzone').classList.add('dragover');
}
function udDragLeave(e) {
  document.getElementById('udDropzone').classList.remove('dragover');
}
function udDrop(e) {
  e.preventDefault();
  document.getElementById('udDropzone').classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) udApplyFile(f);
}
function udFileSelected(input) {
  if (input.files[0]) udApplyFile(input.files[0]);
}

function udApplyFile(file) {
  /* Validate */
  const allowed = ['image/png','image/jpeg','image/jpg'];
  if (!allowed.includes(file.type) && !file.name.match(/\.(dcm)$/i)) {
    udShowToast('Please select a PNG, JPG, or DICOM file.', 'error');
    return;
  }
  if (file.size > 16 * 1024 * 1024) {
    udShowToast('File exceeds 16 MB limit.', 'error');
    return;
  }

  UD.uploadedFile = file;

  /* Preview */
  const reader = new FileReader();
  reader.onload = e => {
    const img = document.getElementById('udPreviewImg');
    if (file.type.startsWith('image/')) {
      img.src = e.target.result;
    } else {
      img.src = '/static/img/dicom-placeholder.png'; /* fallback */
    }
  };
  reader.readAsDataURL(file);

  document.getElementById('udPreviewName').textContent = file.name;
  document.getElementById('udPreviewSize').textContent = (file.size / 1024).toFixed(1) + ' KB';
  document.getElementById('udPreview').classList.add('visible');
  document.getElementById('udAnalyseBtn').classList.add('visible');
}

function udClearPreview() {
  UD.uploadedFile = null;
  document.getElementById('udPreview').classList.remove('visible');
  document.getElementById('udAnalyseBtn').classList.remove('visible');
  document.getElementById('udLoading').classList.remove('visible');
  document.getElementById('udFileInput').value = '';
}

/* ── Submit scan ─────────────────────────────────────────────────────────── */
async function udSubmitScan() {
  if (!UD.uploadedFile) return;

  /* Quota check for free users */
  if (!UD.isPro) {
    const used  = UD.user?.scans_today ?? 0;
    if (used >= 5) {
      udShowToast('Monthly scan limit reached. Upgrade to Pro for unlimited scans.', 'warning');
      return;
    }
  }

  /* Show loading */
  document.getElementById('udAnalyseBtn').disabled = true;
  document.getElementById('udLoading').classList.add('visible');
  document.getElementById('udResultCard').classList.remove('visible');

  try {
    const form = new FormData();
    form.append('file', UD.uploadedFile);
    const res  = await api.upload('/scan/upload', form);
    const data = await res.json();

    if (!res.ok) {
      udShowToast(data.error || 'Upload failed. Please try again.', 'error');
      return;
    }

    /* Update user quota */
    if (UD.user) UD.user.scans_today = (UD.user.scans_today || 0) + 1;
    User.save(UD.user);
    udRefreshQuota();

    /* Show result */
    UD.currentScanData = data;
    udShowResult(data);

    /* Reload history */
    await udLoadHistory();

    /* Update scan count badge */
    udRefreshScanBadge();

    udClearPreview();
  } catch (err) {
    udShowToast('Network error. Please check your connection.', 'error');
    console.error(err);
  } finally {
    document.getElementById('udAnalyseBtn').disabled = false;
    document.getElementById('udLoading').classList.remove('visible');
  }
}

/* ════════════════════════════════════════════════════════════════════════════
   6. AI RESULT PANEL
   ════════════════════════════════════════════════════════════════════════════ */
function udInitResultPanel() {
  document.getElementById('udResultCard').classList.remove('visible');
}

function udShowResult(data) {
  const isPneumonia = data.prediction === 'PNEUMONIA';
  const conf        = parseFloat(data.confidence) || 0;
  const confPct     = conf.toFixed(1) + '%';

  /* Result label */
  const lbl = document.getElementById('udResultLabel');
  if (isPneumonia) {
    lbl.textContent = I18n.t('result_pneumonia') || 'PNEUMONIA DETECTED';
    lbl.className   = 'ud-result-label pneumonia';
  } else {
    lbl.textContent = I18n.t('result_normal') || 'NORMAL';
    lbl.className   = 'ud-result-label normal';
  }

  /* Confidence ring */
  const ringFill = document.getElementById('udRingFill');
  const pct      = Math.min(conf, 100) / 100;
  const dashOffset = 283 - (283 * pct);
  ringFill.style.strokeDashoffset = dashOffset;
  ringFill.className = `ud-ring-fill ${isPneumonia ? 'pneumonia' : 'normal'}`;
  document.getElementById('udRingPct').textContent = confPct;

  /* Detail rows */
  const procMs = data.processing_time_ms || data.processing_time || 0;
  document.getElementById('udProcTime').textContent   =
    procMs ? ((procMs / 1000).toFixed(1) + 's') : '—';
  document.getElementById('udModelVer').textContent   = data.model_version || 'CNN+ANN v1.0';
  document.getElementById('udScanId').textContent     = '#SCN-' + String(data.id || 0).padStart(3,'0');
  document.getElementById('udUniversity').textContent = UD.user?.university || 'RUPP';

  /* Timestamp */
  document.getElementById('udResultTs').textContent   =
    new Date().toLocaleTimeString(undefined, { hour:'2-digit', minute:'2-digit' });

  /* X-ray image */
  UD.currentImageUrl   = data.image_url   || null;
  UD.currentHeatmapUrl = data.heatmap_url || null;
  UD.zoomLevel         = 1;

  const xrayImg = document.getElementById('udXrayImg');
  xrayImg.src = UD.currentImageUrl || '';
  xrayImg.style.transform = 'scale(1)';

  const hm = document.getElementById('udHeatmapImg');
  if (UD.currentHeatmapUrl) {
    hm.src = UD.currentHeatmapUrl;
    document.getElementById('udHeatmapToggle').disabled = false;
  } else {
    document.getElementById('udHeatmapToggle').disabled = true;
  }

  /* PDF button */
  document.getElementById('udSaveBtn').disabled = false;
  if (UD.isPro && data.report_id) {
    document.getElementById('udPdfBtnLocked').classList.add('ud-hidden');
    const pdfPro = document.getElementById('udPdfBtnPro');
    pdfPro.dataset.reportId = data.report_id;
    pdfPro.classList.remove('ud-hidden');
  } else {
    document.getElementById('udPdfBtnLocked').classList.remove('ud-hidden');
    document.getElementById('udPdfBtnPro').classList.add('ud-hidden');
  }

  /* Show panel */
  const card = document.getElementById('udResultCard');
  card.classList.add('visible');
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ── Image viewer tools ──────────────────────────────────────────────────── */
function udZoomIn()    { UD.zoomLevel = Math.min(UD.zoomLevel + 0.25, 3);   _applyZoom(); }
function udZoomOut()   { UD.zoomLevel = Math.max(UD.zoomLevel - 0.25, 0.5); _applyZoom(); }
function udZoomReset() { UD.zoomLevel = 1; _applyZoom(); }
function _applyZoom()  {
  document.getElementById('udXrayImg').style.transform = `scale(${UD.zoomLevel})`;
}
function udDownloadXray() {
  if (!UD.currentImageUrl) return;
  const a = document.createElement('a');
  a.href = UD.currentImageUrl; a.download = 'xray.jpg'; a.click();
}

/* ── Heatmap toggle ─────────────────────────────────────────────────────── */
function udToggleHeatmap(chk) {
  const overlay = document.getElementById('udHeatmapOverlay');
  chk.checked ? overlay.classList.add('visible') : overlay.classList.remove('visible');
}

/* ── Save scan ──────────────────────────────────────────────────────────── */
function udSaveToHistory() {
  /* Scan is auto-saved on upload — just show confirmation */
  const btn = document.getElementById('udSaveBtn');
  btn.disabled = true;
  udShowToast(I18n.t('toast_saved') || 'Saved to history.', 'success');
}

/* ════════════════════════════════════════════════════════════════════════════
   7. SCAN HISTORY
   ════════════════════════════════════════════════════════════════════════════ */
async function udLoadHistory() {
  try {
    const res  = await api.get('/scan/history?page=1&limit=10');
    const data = await res.json();
    UD.allScans = data.scans || [];
    /* Build quick-lookup map for the detail modal */
    UD.scanMap  = {};
    UD.allScans.forEach(s => { UD.scanMap[s.id] = s; });
    udRenderHistory(UD.allScans);
    udRefreshScanBadge();
  } catch {
    udRenderHistory([]);
  }
}

function udRefreshScanBadge() {
  const badge = document.getElementById('udScanBadge');
  const sub   = document.getElementById('udScanSubLabel');
  const n     = UD.allScans.length;
  if (n > 0) {
    badge.textContent = n;
    badge.classList.remove('ud-hidden');
    sub.textContent = `${n} scan${n !== 1 ? 's' : ''} total`;
  } else {
    badge.classList.add('ud-hidden');
    sub.textContent = '—';
  }
}

function udRenderHistory(scans) {
  const empty   = document.getElementById('udHistoryEmpty');
  const tbody   = document.getElementById('udHistoryBody');
  const mCards  = document.getElementById('udScanCards');

  if (!scans.length) {
    tbody.innerHTML = '';
    mCards.innerHTML = '';
    empty.classList.remove('ud-hidden');
    return;
  }
  empty.classList.add('ud-hidden');

  /* Reveal the "Select" toggle button now that we have rows */
  const selectBtn = document.getElementById('udSelectToggleBtn');
  if (selectBtn) selectBtn.classList.remove('ud-hidden');

  /* Table rows */
  tbody.innerHTML = scans.map(s => {
    const isPneu  = s.prediction === 'PNEUMONIA';
    const dt      = s.created_at ? new Date(s.created_at) : null;
    const dateStr = dt ? dt.toLocaleDateString(undefined, { day:'2-digit', month:'short', year:'numeric' }) : '—';
    const timeStr = dt ? dt.toLocaleTimeString(undefined, { hour:'2-digit', minute:'2-digit' }) : '';
    const scanId  = '#SCN-' + String(s.id || 0).padStart(3,'0');
    const confRaw = parseFloat(s.confidence) || 0;
    const conf    = confRaw.toFixed(1) + '%';
    const procMs  = s.processing_time_ms || 0;
    const aiTime  = procMs ? (procMs / 1000).toFixed(2) + 's' : '—';
    const pillCls = isPneu ? 'pneumonia' : 'normal';
    const pillDot = isPneu ? '🔴' : '🟢';
    const pillLbl = isPneu
      ? (I18n.t('hist_pill_pneumonia') || 'PNEUMONIA')
      : (I18n.t('hist_pill_normal')    || 'NORMAL');
    const confBar = `
      <div class="ud-conf-wrap">
        <span class="ud-conf-val ${pillCls}">${conf}</span>
        <div class="ud-conf-bar">
          <div class="ud-conf-fill ${pillCls}" style="width:${Math.min(confRaw,100)}%"></div>
        </div>
      </div>`;
    const pdfHtml = UD.isPro && s.report_id
      ? `<button class="ud-hist-pdf-btn pro" onclick="udDownloadReport(${s.report_id})" title="Download PDF Report">
           <i class="ti ti-file-download"></i>
         </button>`
      : `<button class="ud-hist-pdf-btn locked" title="${I18n.t('hist_dl_locked')||'Upgrade to Pro'}" disabled>
           <i class="ti ti-lock"></i>
         </button>`;
    return `
      <tr data-scan-id="${s.id}">
        <td class="ud-td-check ud-hidden">
          <label class="ud-cb-wrap">
            <input type="checkbox" class="ud-row-chk" value="${s.id}" onchange="udRowCheckChange()" />
            <span class="ud-cb"></span>
          </label>
        </td>
        <td>
          <div class="ud-hist-date">${dateStr}</div>
          <div class="ud-hist-time">${timeStr}</div>
        </td>
        <td><span class="ud-hist-id">${scanId}</span></td>
        <td>
          <span class="ud-result-pill ${pillCls}">
            <span class="ud-pill-dot">${pillDot}</span>${pillLbl}
          </span>
        </td>
        <td>${confBar}</td>
        <td>
          <span class="ud-ai-time-val">
            <i class="ti ti-clock" style="font-size:12px;opacity:.6;"></i> ${aiTime}
          </span>
        </td>
        <td>
          <div class="ud-hist-actions">
            <button class="ud-hist-view-btn" onclick="udOpenScanDetailModal(${s.id})">
              <i class="ti ti-eye"></i>
              <span>${I18n.t('hist_view')||'View'}</span>
            </button>
            ${pdfHtml}
            <button class="ud-hist-del-btn" onclick="udConfirmDeleteScan(${s.id})"
                    title="${I18n.t('hist_delete')||'Delete scan'}">
              <i class="ti ti-trash"></i>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');

  /* Phone card list */
  mCards.innerHTML = scans.map(s => {
    const isPneu  = s.prediction === 'PNEUMONIA';
    const dt      = s.created_at ? new Date(s.created_at) : null;
    const dateStr = dt ? dt.toLocaleDateString(undefined, { day:'2-digit', month:'short', year:'numeric' }) : '—';
    const timeStr = dt ? dt.toLocaleTimeString(undefined, { hour:'2-digit', minute:'2-digit' }) : '';
    const scanId  = '#SCN-' + String(s.id || 0).padStart(3,'0');
    const confRaw = parseFloat(s.confidence) || 0;
    const conf    = confRaw.toFixed(1) + '%';
    const procMs  = s.processing_time_ms || 0;
    const aiTime  = procMs ? (procMs / 1000).toFixed(2) + 's' : '—';
    const pillCls = isPneu ? 'pneumonia' : 'normal';
    const pillLbl = isPneu
      ? (I18n.t('hist_pill_pneumonia')||'PNEUMONIA')
      : (I18n.t('hist_pill_normal')||'NORMAL');
    const pdfHtml = UD.isPro && s.report_id
      ? `<button class="ud-hist-pdf-btn pro" onclick="udDownloadReport(${s.report_id})">
           <i class="ti ti-file-download"></i> PDF
         </button>`
      : `<button class="ud-hist-pdf-btn locked" disabled>
           <i class="ti ti-lock"></i> PDF
         </button>`;
    return `
      <div class="ud-scan-card" data-scan-id="${s.id}">
        <!-- Card head: ID + pill + checkbox -->
        <div class="ud-scan-card-head">
          <label class="ud-cb-wrap ud-card-chk ud-hidden">
            <input type="checkbox" class="ud-row-chk" value="${s.id}" onchange="udRowCheckChange()" />
            <span class="ud-cb"></span>
          </label>
          <span class="ud-hist-id">${scanId}</span>
          <span class="ud-result-pill ${pillCls}">${pillLbl}</span>
        </div>
        <!-- Stats row -->
        <div class="ud-scan-card-stats">
          <div class="ud-scan-stat">
            <span class="ud-scan-stat-lbl"><i class="ti ti-calendar" style="font-size:11px;"></i> Date</span>
            <span class="ud-scan-stat-val">${dateStr}<br><small>${timeStr}</small></span>
          </div>
          <div class="ud-scan-stat">
            <span class="ud-scan-stat-lbl"><i class="ti ti-chart-bar" style="font-size:11px;"></i> Confidence</span>
            <span class="ud-scan-stat-val ${pillCls}" style="font-weight:700;">${conf}</span>
          </div>
          <div class="ud-scan-stat">
            <span class="ud-scan-stat-lbl"><i class="ti ti-clock" style="font-size:11px;"></i> AI Time</span>
            <span class="ud-scan-stat-val">${aiTime}</span>
          </div>
        </div>
        <!-- Confidence bar -->
        <div class="ud-conf-bar" style="margin:8px 0 12px;">
          <div class="ud-conf-fill ${pillCls}" style="width:${Math.min(confRaw,100)}%"></div>
        </div>
        <!-- Actions -->
        <div class="ud-scan-card-actions">
          <button class="ud-hist-view-btn" onclick="udOpenScanDetailModal(${s.id})">
            <i class="ti ti-eye"></i> ${I18n.t('hist_view')||'View Details'}
          </button>
          ${pdfHtml}
          <button class="ud-hist-del-btn" onclick="udConfirmDeleteScan(${s.id})"
                  title="${I18n.t('hist_delete')||'Delete scan'}">
            <i class="ti ti-trash"></i>
          </button>
        </div>
      </div>`;
  }).join('');
}

/* ════════════════════════════════════════════════════════════════════════════
   8. FIND DOCTOR PANEL
   ════════════════════════════════════════════════════════════════════════════ */
async function udInitDoctors() {
  const grid = document.getElementById('udDoctorGrid');
  if (grid) grid.innerHTML = `<div class="ud-empty" style="grid-column:1/-1;"><i class="ti ti-loader" style="animation:spin 1s linear infinite"></i></div>`;

  try {
    const res  = await fetch('/api/marketplace/doctors?limit=12');
    const data = await res.json();
    UD.doctors = (data.doctors || []);
  } catch {
    UD.doctors = [];
  }
  udRenderDoctors();
}

function udSetFilter(btn) {
  document.querySelectorAll('.ud-filter-pill').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  UD.doctorFilter = btn.dataset.filter;
  udRenderDoctors();
}

function udFilterDoctors() {
  udRenderDoctors();
}

function udRenderDoctors() {
  const query  = (document.getElementById('udDoctorSearch')?.value || '').toLowerCase();
  const filter = UD.doctorFilter;
  const docs   = UD.doctors || [];

  const filtered = docs.filter(d => {
    const matchFilter = filter === 'all' || (d.specialty || '').toLowerCase().includes(filter.toLowerCase());
    const matchQuery  = !query ||
      (d.full_name  || '').toLowerCase().includes(query) ||
      (d.specialty  || '').toLowerCase().includes(query) ||
      (d.hospital   || '').toLowerCase().includes(query);
    return matchFilter && matchQuery;
  });

  const grid = document.getElementById('udDoctorGrid');
  if (!grid) return;

  if (!filtered.length) {
    grid.innerHTML = `
      <div class="ud-empty" style="grid-column:1/-1;">
        <i class="ti ti-search-off"></i>
        <span class="ud-empty-h">${I18n.t('doc_no_results') || 'No doctors found'}</span>
      </div>`;
    return;
  }

  grid.innerHTML = filtered.map((d, i) => udDoctorCardHTML(d, i)).join('');
}

function udDoctorCardHTML(d, idx = 0) {
  const palette  = _DOC_PALETTE[idx % _DOC_PALETTE.length];
  const initials = (d.full_name || 'DR').split(' ').map(w => w[0]).slice(0,2).join('').toUpperCase();
  const rating   = Number(d.rating || 0).toFixed(1);
  const stars    = Array.from({length:5}, (_,i) =>
    `<i class="ti ti-star${i < Math.floor(d.rating) ? '-filled' : ''}" style="font-size:13px;"></i>`
  ).join('');
  const fee = d.rate_per_session ? `$${d.rate_per_session}` : (d.qualifications ? '' : '—');
  const verBadge = d.is_verified
    ? `<span class="ud-verified-badge">
         <i class="ti ti-shield-check" style="font-size:12px;"></i>
         ${I18n.t('doc_verified') || 'Verified'}
       </span>`
    : '';
  return `
    <div class="ud-doc-card">
      <div class="ud-doc-top">
        <div class="ud-doc-info">
          <div class="ud-doc-avatar" style="background:${palette.bg};color:${palette.color};">${initials}</div>
          <div>
            <div class="ud-doc-name">${d.full_name || '—'}</div>
            <div class="ud-doc-spec">${d.specialty || '—'}</div>
          </div>
        </div>
        ${verBadge}
      </div>
      <div class="ud-doc-meta">
        <span class="ud-doc-uni">${d.hospital || d.city || '—'}</span>
        <span class="ud-doc-exp">${d.qualifications || ''}</span>
      </div>
      <div class="ud-doc-rating">
        <span class="ud-stars">${stars}</span>
        <span class="ud-rating-num">${rating}</span>
        <span class="ud-rating-rev">(${d.review_count || 0} ${I18n.t('doc_reviews') || 'reviews'})</span>
      </div>
      ${fee ? `<div class="ud-doc-price"><i class="ti ti-currency-dollar"></i>${fee} ${I18n.t('doc_consult') || '/ consultation'}</div>` : ''}
      <div class="ud-doc-actions">
        <button class="ud-doc-view-btn" onclick="window.location='/marketplace'"
          data-i18n="doc_view">${I18n.t('doc_view') || 'View Profile'}</button>
        <button class="ud-doc-book-btn" onclick="udOpenBookModal(${d.id})"
          data-i18n="doc_book">${I18n.t('doc_book') || 'Book Now'}</button>
      </div>
    </div>`;
}

/* ════════════════════════════════════════════════════════════════════════════
   9. APPOINTMENTS
   ════════════════════════════════════════════════════════════════════════════ */
async function udInitAppointments() {
  await udLoadAppointments();
}

async function udLoadAppointments() {
  try {
    const res  = await API.get('/api/appointments');
    const data = await res.json();
    if (res.ok && data.appointments) {
      UD.bookedAppointments = data.appointments;
    }
  } catch (_) { /* network error — keep empty array */ }
  udRenderAppointments();
}

function udRenderAppointments() {
  const list  = document.getElementById('udApptList');
  const empty = document.getElementById('udApptEmpty');

  const active = UD.bookedAppointments.filter(a => a.status !== 'cancelled');

  if (!active.length) {
    list.innerHTML = '';
    empty.classList.remove('ud-hidden');
    return;
  }
  empty.classList.add('ud-hidden');

  list.innerHTML = active.map((a, idx) => {
    const palette  = _DOC_PALETTE[a.doctor_id % _DOC_PALETTE.length];
    const initials = (a.doctor_name || 'DR').split(' ').map(w => w[0]).slice(0,2).join('').toUpperCase();
    const dateStr  = _udFmtDate(a.appointment_date);
    const fee      = a.fee_snapshot ? `$${Number(a.fee_snapshot).toFixed(2)}` : '';
    const noteHtml = a.note
      ? `<div class="ud-appt-note"><i class="ti ti-notes"></i> ${_udEsc(a.note)}</div>`
      : '';
    const statusClass = a.status === 'completed' ? 'completed' : 'confirmed';
    const statusLabel = a.status === 'completed'
      ? (I18n.t('appt_completed') || 'Completed')
      : (I18n.t('appt_confirmed') || 'Confirmed');

    return `
    <div class="ud-appt-row" id="appt-row-${a.id}">
      <div class="ud-appt-avatar" style="background:${palette.bg};color:${palette.color};">${initials}</div>
      <div class="ud-appt-info">
        <div class="ud-appt-name">${_udEsc(a.doctor_name)}</div>
        <div class="ud-appt-spec">${_udEsc(a.doctor_specialty)}</div>
        <div class="ud-appt-time">
          <i class="ti ti-calendar"></i> ${dateStr}
          &nbsp;·&nbsp;
          <i class="ti ti-clock"></i> ${_udEsc(a.appointment_time)}
          ${fee ? `&nbsp;·&nbsp;<i class="ti ti-cash"></i> ${fee}` : ''}
        </div>
        ${noteHtml}
      </div>
      <span class="ud-status-pill ${statusClass}">${statusLabel}</span>
      <div class="ud-appt-actions">
        <button class="ud-join-btn">
          <i class="ti ti-video"></i>
          ${I18n.t('appt_join') || 'Join Meeting'}
        </button>
        ${a.status === 'confirmed' ? `
        <button class="ud-cancel-appt-btn" onclick="udCancelAppointment(${a.id})">
          <i class="ti ti-x"></i>
          ${I18n.t('appt_cancel') || 'Cancel'}
        </button>` : ''}
      </div>
    </div>`;
  }).join('');
}

/* ── Cancel appointment ──────────────────────────────────────────────────── */
async function udCancelAppointment(aptId) {
  if (!confirm(I18n.t('appt_cancel_confirm') || 'Cancel this appointment?')) return;

  try {
    const res  = await API.patch(`/api/appointments/${aptId}/cancel`, {});
    const data = await res.json();
    if (res.ok) {
      // Update local state
      const apt = UD.bookedAppointments.find(a => a.id === aptId);
      if (apt) apt.status = 'cancelled';
      udRenderAppointments();
      udShowToast(I18n.t('toast_cancelled') || 'Appointment cancelled.', 'info');
    } else {
      udShowToast(data.error || 'Could not cancel appointment.', 'error');
    }
  } catch {
    udShowToast('Network error. Please try again.', 'error');
  }
}

/* ── Date formatter: "2026-05-26" → "26 May 2026" ────────────────────────── */
function _udFmtDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-').map(Number);
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${d} ${months[m - 1]} ${y}`;
}

/* ── XSS-safe escaper ────────────────────────────────────────────────────── */
function _udEsc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

/* ════════════════════════════════════════════════════════════════════════════
   10. UPGRADE BANNER
   ════════════════════════════════════════════════════════════════════════════ */
function udInitUpgradeBanner() {
  /* Already hidden for pro via CSS body.is-pro */
}

/* ════════════════════════════════════════════════════════════════════════════
   11. BOOK NOW MODAL
   ════════════════════════════════════════════════════════════════════════════ */
function udOpenBookModal(doctorId) {
  const d = UD.doctors.find(x => x.id === doctorId);
  if (!d) return;

  const idx      = UD.doctors.indexOf(d);
  const palette  = _DOC_PALETTE[idx % _DOC_PALETTE.length];
  const initials = (d.full_name || 'DR').split(' ').map(w => w[0]).slice(0,2).join('').toUpperCase();
  const fee      = d.rate_per_session || 0;

  UD.activeDoctorId    = d.id;
  UD.activeDoctorFee   = fee;
  UD.activeDoctorName  = d.full_name;
  UD.activeDoctorSpec  = d.specialty;
  UD.activeDoctorColor = palette;

  /* Avatar */
  const av = document.getElementById('mdAvatar');
  av.textContent      = initials;
  av.style.background = palette.bg;
  av.style.color      = palette.color;

  document.getElementById('mdDocName').textContent = d.full_name || '—';
  document.getElementById('mdDocSpec').textContent = d.specialty  || '—';
  document.getElementById('mdFee').textContent = `$${fee.toFixed(2)}`;

  /* Reset selections */
  UD.selectedDate = null;
  UD.selectedTime = null;
  document.getElementById('udNote').value = '';

  udBuildCalendar();
  udBuildTimeSlots();

  document.getElementById('udBookModal').classList.add('open');
}

function udCloseBookModal() {
  document.getElementById('udBookModal').classList.remove('open');
}

function udCloseModal(e) {
  if (e.target === document.getElementById('udBookModal')) udCloseBookModal();
}

/* ── Mini calendar ──────────────────────────────────────────────────────── */
function udBuildCalendar() {
  const now   = new Date();
  const year  = now.getFullYear();
  const month = now.getMonth();
  const today = now.getDate();

  const monthNames = ['January','February','March','April','May','June',
                      'July','August','September','October','November','December'];

  const firstDay   = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const dayNames = ['Su','Mo','Tu','We','Th','Fr','Sa'];
  const headerHtml = dayNames.map(d =>
    `<div class="ud-cal-day-name">${d}</div>`).join('');

  let cells = '';
  /* Empty cells before first day */
  for (let i = 0; i < firstDay; i++) cells += `<div class="ud-cal-day other-month"></div>`;
  /* Day cells */
  for (let day = 1; day <= daysInMonth; day++) {
    const isPast  = day < today;
    const isToday = day === today;
    let cls = 'ud-cal-day';
    if (isPast) cls += ' unavail';
    else cls += ' available';
    if (isToday && !isPast) cls += ' selected';
    if (isToday) UD.selectedDate = `${monthNames[month]} ${day}, ${year}`;
    cells += `<div class="${cls}" onclick="udSelectDate(this,'${monthNames[month]} ${day}, ${year}')">${day}</div>`;
  }

  document.getElementById('udCal').innerHTML = `
    <div class="ud-cal-header">
      <button class="ud-cal-nav"><i class="ti ti-chevron-left"></i></button>
      <span class="ud-cal-month">${monthNames[month]} ${year}</span>
      <button class="ud-cal-nav"><i class="ti ti-chevron-right"></i></button>
    </div>
    <div class="ud-cal-grid">
      ${headerHtml}
      ${cells}
    </div>`;
}

function udSelectDate(el, dateStr) {
  if (el.classList.contains('unavail')) return;
  document.querySelectorAll('.ud-cal-day').forEach(d => d.classList.remove('selected'));
  el.classList.add('selected');
  UD.selectedDate = dateStr;
}

/* ── Time slots ─────────────────────────────────────────────────────────── */
function udBuildTimeSlots() {
  const slots  = ['09:00','10:00','11:00','14:00','15:00','16:00'];
  const booked = ['11:00']; /* mock booked slot */
  document.getElementById('udTimeGrid').innerHTML = slots.map(t => {
    const isBk  = booked.includes(t);
    const cls   = 'ud-time-slot' + (isBk ? ' booked' : '');
    const click = isBk ? '' : `onclick="udSelectTime(this,'${t}')"`;
    return `<div class="${cls}" ${click}>${t}</div>`;
  }).join('');
}

function udSelectTime(el, time) {
  document.querySelectorAll('.ud-time-slot').forEach(s => s.classList.remove('selected'));
  el.classList.add('selected');
  UD.selectedTime = time;
}

/* ── Confirm booking — saves to database ────────────────────────────────── */
async function udConfirmBooking() {
  if (!UD.selectedDate) {
    udShowToast(I18n.t('toast_select_date') || 'Please select a date.', 'warning');
    return;
  }
  if (!UD.selectedTime) {
    udShowToast(I18n.t('toast_select_time') || 'Please select a time slot.', 'warning');
    return;
  }

  /* Convert "May 26, 2026" → "2026-05-26" */
  const parsed = new Date(UD.selectedDate);
  if (isNaN(parsed)) {
    udShowToast('Invalid date selected.', 'error');
    return;
  }
  const isoDate = parsed.toISOString().split('T')[0];   // YYYY-MM-DD

  /* Show loading on the confirm button */
  const btn = document.querySelector('.ud-btn-confirm');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled  = true;
    btn.innerHTML = `<span class="ud-btn-spinner"></span>${I18n.t('modal_booking') || 'Booking…'}`;
  }

  try {
    const res  = await API.post('/api/appointments', {
      doctor_id:        UD.activeDoctorId,
      appointment_date: isoDate,
      appointment_time: UD.selectedTime,
      note:             (document.getElementById('udNote')?.value || '').trim() || null,
    });
    const data = await res.json();

    if (res.status === 201) {
      /* Add the newly created appointment to local state */
      UD.bookedAppointments.push(data.appointment);
      udCloseBookModal();
      udRenderAppointments();
      document.getElementById('appt-section').scrollIntoView({ behavior: 'smooth' });
      udShowToast(I18n.t('toast_booked') || 'Appointment booked successfully!', 'success');
    } else if (res.status === 409) {
      udShowToast(data.error || 'You already have this appointment.', 'warning');
    } else {
      udShowToast(data.error || 'Booking failed. Please try again.', 'error');
    }
  } catch {
    udShowToast('Network error. Please try again.', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
  }
}

/* ════════════════════════════════════════════════════════════════════════════
   SCAN DETAIL DRAWER  — opens from history "View" button
   ════════════════════════════════════════════════════════════════════════════ */

function udOpenScanDetailModal(scanId) {
  const s = UD.scanMap[scanId];
  if (!s) { udShowToast('Scan data not found.', 'error'); return; }

  const isPneu  = s.prediction === 'PNEUMONIA';
  const conf    = parseFloat(s.confidence) || 0;
  const scanLabel = '#SCN-' + String(s.id).padStart(3, '0');

  /* ── Header ─────────────────────────────────────────────────────── */
  document.getElementById('sdmScanId').textContent = scanLabel;
  const dt = s.created_at ? new Date(s.created_at) : null;
  document.getElementById('sdmDate').textContent = dt
    ? dt.toLocaleDateString(undefined, { day:'2-digit', month:'short', year:'numeric' }) +
      ' · ' + dt.toLocaleTimeString(undefined, { hour:'2-digit', minute:'2-digit' })
    : '—';

  /* ── Result label ───────────────────────────────────────────────── */
  const lbl = document.getElementById('sdmResultLabel');
  lbl.textContent = isPneu
    ? (I18n.t('result_pneumonia') || 'PNEUMONIA DETECTED')
    : (I18n.t('result_normal')    || 'NORMAL');
  lbl.className = `ud-sdm-result-label ${isPneu ? 'pneumonia' : 'normal'}`;

  /* ── Confidence ring ────────────────────────────────────────────── */
  const pct       = Math.min(conf, 100) / 100;
  const dashOff   = 283 - 283 * pct;
  const ringFill  = document.getElementById('sdmRingFill');
  ringFill.style.strokeDashoffset = dashOff;
  ringFill.className = `ud-ring-fill ${isPneu ? 'pneumonia' : 'normal'}`;
  document.getElementById('sdmRingPct').textContent = conf.toFixed(1) + '%';

  /* ── Detail rows ────────────────────────────────────────────────── */
  document.getElementById('sdmDetailId').textContent      = scanLabel;
  document.getElementById('sdmDetailModel').textContent   = s.model_version || 'CNN+ANN v1.0';
  const gcStatus = s.gradcam_status === 'done'
    ? '✓ Available' : (s.gradcam_status === 'failed' ? '✗ Failed' : '—');
  document.getElementById('sdmDetailGradcam').textContent = gcStatus;
  document.getElementById('sdmDetailUni').textContent     = UD.user?.university || 'RUPP';

  /* ── X-ray viewer ───────────────────────────────────────────────── */
  SDM.zoomLevel = 1;
  SDM.reportId  = s.report_id || null;
  SDM.imageUrl  = s.image_path ? `/static/${s.image_path}` : '';

  const xrayImg = document.getElementById('sdmXrayImg');
  xrayImg.src   = SDM.imageUrl;
  xrayImg.style.transform = 'scale(1)';

  const hmImg    = document.getElementById('sdmHeatmapImg');
  const hmToggle = document.getElementById('sdmHeatmapToggle');
  const hmOverlay = document.getElementById('sdmHeatmapOverlay');

  if (s.heatmap_path && s.gradcam_status === 'done') {
    hmImg.src         = `/static/${s.heatmap_path}`;
    hmToggle.disabled = false;
    hmToggle.checked  = false;
    hmOverlay.classList.remove('visible');
  } else {
    hmImg.src         = '';
    hmToggle.disabled = true;
    hmToggle.checked  = false;
    hmOverlay.classList.remove('visible');
  }

  /* ── PDF button ─────────────────────────────────────────────────── */
  const pdfLocked = document.getElementById('sdmPdfLocked');
  const pdfPro    = document.getElementById('sdmPdfPro');
  if (UD.isPro && s.report_id) {
    pdfPro.dataset.reportId = s.report_id;
    pdfLocked.classList.add('ud-hidden');
    pdfPro.classList.remove('ud-hidden');
  } else {
    pdfLocked.classList.remove('ud-hidden');
    pdfPro.classList.add('ud-hidden');
  }

  /* ── Open drawer ────────────────────────────────────────────────── */
  document.getElementById('udScanDetailModal').classList.add('open');
  document.body.style.overflow = 'hidden';  // prevent bg scroll
}

function udCloseScanDetailModal() {
  document.getElementById('udScanDetailModal').classList.remove('open');
  document.body.style.overflow = '';
}

function udCloseScanDetail(e) {
  if (e.target === document.getElementById('udScanDetailModal')) {
    udCloseScanDetailModal();
  }
}

/* SDM viewer controls */
function sdmZoomIn()    { SDM.zoomLevel = Math.min(SDM.zoomLevel + 0.25, 3);   _sdmApplyZoom(); }
function sdmZoomOut()   { SDM.zoomLevel = Math.max(SDM.zoomLevel - 0.25, 0.5); _sdmApplyZoom(); }
function sdmZoomReset() { SDM.zoomLevel = 1; _sdmApplyZoom(); }
function _sdmApplyZoom() {
  document.getElementById('sdmXrayImg').style.transform = `scale(${SDM.zoomLevel})`;
}
function sdmToggleHeatmap(chk) {
  const ov = document.getElementById('sdmHeatmapOverlay');
  chk.checked ? ov.classList.add('visible') : ov.classList.remove('visible');
}
function sdmDownloadXray() {
  if (!SDM.imageUrl) return;
  const a = document.createElement('a');
  a.href = SDM.imageUrl; a.download = 'xray.jpg'; a.click();
}

/* Keyboard: Esc closes the drawer or delete-confirm modal */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    udCloseDeleteModal();
    udCloseScanDetailModal();
  }
});

/* ════════════════════════════════════════════════════════════════════════════
   DELETE SCAN  (single + multi-select)
   ════════════════════════════════════════════════════════════════════════════ */
let _udDeleteIds    = [];   // ids queued for deletion
let _udSelectMode   = false;

/* ── Single-row delete (trash icon button) ───────────────────────────────── */
function udConfirmDeleteScan(scanId) {
  _udDeleteIds = [scanId];
  _udOpenDeleteModal();
}

/* ── Select-mode toggle ──────────────────────────────────────────────────── */
function udToggleSelectMode() {
  _udSelectMode ? udExitSelectMode() : udEnterSelectMode();
}

function udEnterSelectMode() {
  _udSelectMode = true;

  /* Show checkbox column (table) */
  document.querySelectorAll('.ud-th-check, .ud-td-check').forEach(el => el.classList.remove('ud-hidden'));
  /* Show checkbox on mobile cards */
  document.querySelectorAll('.ud-card-chk').forEach(el => el.classList.remove('ud-hidden'));

  /* Update toggle button label */
  const btn = document.getElementById('udSelectToggleBtn');
  if (btn) btn.innerHTML = `<i class="ti ti-x"></i> <span data-i18n="hist_cancel_select">${I18n.t('hist_cancel_select')||'Cancel'}</span>`;

  /* Show bulk bar */
  _udUpdateBulkBar();
}

function udExitSelectMode() {
  _udSelectMode = false;

  /* Uncheck all */
  document.querySelectorAll('.ud-row-chk').forEach(c => c.checked = false);
  const allChk = document.getElementById('udSelectAllChk');
  if (allChk) allChk.checked = false;

  /* Hide checkbox column */
  document.querySelectorAll('.ud-th-check, .ud-td-check').forEach(el => el.classList.add('ud-hidden'));
  document.querySelectorAll('.ud-card-chk').forEach(el => el.classList.add('ud-hidden'));

  /* Restore toggle button */
  const btn = document.getElementById('udSelectToggleBtn');
  if (btn) btn.innerHTML = `<i class="ti ti-checkbox"></i> <span data-i18n="hist_select">${I18n.t('hist_select')||'Select'}</span>`;

  /* Hide bulk bar */
  const bar = document.getElementById('udBulkBar');
  if (bar) bar.classList.add('ud-hidden');
}

function udRowCheckChange() {
  /* Highlight selected rows */
  document.querySelectorAll('.ud-row-chk').forEach(c => {
    const row = c.closest('tr') || c.closest('.ud-scan-card');
    if (row) row.classList.toggle('ud-row-selected', c.checked);
  });

  _udUpdateBulkBar();
  /* Sync "select all" checkbox state */
  const all  = document.querySelectorAll('.ud-row-chk');
  const chkd = document.querySelectorAll('.ud-row-chk:checked');
  const allChk = document.getElementById('udSelectAllChk');
  if (allChk) {
    allChk.checked       = chkd.length === all.length && all.length > 0;
    allChk.indeterminate = chkd.length > 0 && chkd.length < all.length;
  }
}

function udToggleSelectAll(chk) {
  document.querySelectorAll('.ud-row-chk').forEach(c => c.checked = chk.checked);
  _udUpdateBulkBar();
}

function udSelectAll() {
  document.querySelectorAll('.ud-row-chk').forEach(c => c.checked = true);
  const allChk = document.getElementById('udSelectAllChk');
  if (allChk) allChk.checked = true;
  _udUpdateBulkBar();
}

function _udUpdateBulkBar() {
  const checked = document.querySelectorAll('.ud-row-chk:checked');
  const bar     = document.getElementById('udBulkBar');
  const count   = document.getElementById('udBulkCount');
  if (!bar) return;

  if (checked.length > 0) {
    bar.classList.remove('ud-hidden');
    const n = checked.length;
    if (count) count.textContent = `${n} ${n === 1 ? (I18n.t('hist_selected_one')||'scan selected') : (I18n.t('hist_selected_n')||'scans selected')}`;
  } else {
    bar.classList.add('ud-hidden');
  }
}

/* ── Bulk delete ─────────────────────────────────────────────────────────── */
function udConfirmBulkDelete() {
  const checked = document.querySelectorAll('.ud-row-chk:checked');
  if (!checked.length) return;
  _udDeleteIds = Array.from(checked).map(c => parseInt(c.value));
  _udOpenDeleteModal();
}

/* ── Shared confirm modal ────────────────────────────────────────────────── */
function _udOpenDeleteModal() {
  const overlay = document.getElementById('udDeleteModal');
  if (!overlay) return;

  /* Update subtitle with count */
  const sub = overlay.querySelector('.ud-del-modal-sub');
  if (sub && _udDeleteIds.length > 1) {
    sub.textContent = `${_udDeleteIds.length} ${I18n.t('hist_delete_n_sub') || 'scans will be permanently deleted. This cannot be undone.'}`;
  } else if (sub) {
    sub.setAttribute('data-i18n', 'hist_delete_sub');
    sub.textContent = I18n.t('hist_delete_sub') || 'This will permanently remove the scan record and its image. This action cannot be undone.';
  }

  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function udCloseDeleteModal() {
  const overlay = document.getElementById('udDeleteModal');
  if (overlay) { overlay.classList.remove('open'); document.body.style.overflow = ''; }
  _udDeleteIds = [];
}

async function udExecuteDeleteScan() {
  if (!_udDeleteIds.length) return;
  const ids = [..._udDeleteIds];

  const btn = document.getElementById('udDeleteConfirmBtn');
  if (btn) { btn.classList.add('loading'); btn.innerHTML = '<i class="ti ti-loader-2" style="animation:spin .8s linear infinite"></i>'; }

  let failed = 0;
  for (const id of ids) {
    try {
      const res = await api.delete(`/scan/${id}`);
      if (!res.ok) failed++;
    } catch { failed++; }
  }

  udCloseDeleteModal();
  udExitSelectMode();

  const ok = ids.length - failed;
  if (ok > 0) {
    const msg = ok === 1
      ? (I18n.t('hist_delete_ok')   || 'Scan deleted.')
      : `${ok} ${I18n.t('hist_delete_n_ok') || 'scans deleted.'}`;
    udShowToast(msg, 'success');
  }
  if (failed > 0) udShowToast(`${failed} scan(s) could not be deleted.`, 'error');

  /* Reload history */
  await udLoadHistory();
}

/* ════════════════════════════════════════════════════════════════════════════
   PDF REPORT DOWNLOAD  (uses api.get so the JWT header is sent)
   ════════════════════════════════════════════════════════════════════════════ */
async function udDownloadReport(reportId) {
  /* Called from result panel button (data-report-id) or history table */
  const id = reportId
    || document.getElementById('sdmPdfPro')?.dataset?.reportId
    || document.getElementById('udPdfBtnPro')?.dataset?.reportId;
  if (!id) return;

  udShowToast('Preparing download…', 'info', 2500);
  try {
    const res = await api.get(`/scan/report/${id}/download`);
    if (!res.ok) {
      const msg = res.status === 401 || res.status === 403
        ? 'Session expired — please log in again.'
        : 'Download failed. Please try again.';
      udShowToast(msg, 'error');
      return;
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `SmartXRay-Report-${id}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    udShowToast('Download failed. Check your connection.', 'error');
    console.error(err);
  }
}

/* ════════════════════════════════════════════════════════════════════════════
   TOAST SYSTEM
   ════════════════════════════════════════════════════════════════════════════ */
function udShowToast(msg, type='info', duration=4000) {
  const container = document.getElementById('udToastContainer');
  const icons     = { success:'ti-circle-check', error:'ti-circle-x', warning:'ti-alert-triangle', info:'ti-info-circle' };
  const toast     = document.createElement('div');
  toast.className = `ud-toast ${type}`;
  toast.innerHTML = `<i class="ti ${icons[type]||'ti-info-circle'}" style="font-size:18px;flex-shrink:0;"></i><span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity='0'; toast.style.transition='opacity .3s'; }, duration - 300);
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, duration);
}

/* Also expose as global for compatibility */
window.udShowToast = udShowToast;
