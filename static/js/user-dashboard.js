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
  doctorFilter: 'all',
  selectedDate: null,
  selectedTime: null,
  activeDoctorFee: 15,
  activeDoctorName: '',
  activeDoctorSpec: '',
  activeDoctorColor: { bg:'#EEF2FF', color:'#6366F1' },
  bookedAppointments: [],
  uploadedFile: null,
  zoomLevel: 1,
  currentImageUrl: null,
  currentHeatmapUrl: null,
};

/* ── Sample doctor data (matches spec exactly) ───────────────────────────── */
const DOCTORS = [
  {
    id:1, initials:'SM', bg:'#EEF2FF', color:'#6366F1',
    name:'Dr. Sophal Meas', specialty:'Radiology', uni:'RUPP',
    experience:'5 yrs', rating:4.8, reviews:42, fee:15,
    available:'Available today', verified:true,
  },
  {
    id:2, initials:'PK', bg:'#ECFDF5', color:'#10B981',
    name:'Dr. Pisey Keo', specialty:'Pulmonology', uni:'NUM',
    experience:'8 yrs', rating:4.6, reviews:28, fee:20,
    available:'Available tomorrow', verified:true,
  },
  {
    id:3, initials:'KL', bg:'#FEF3C7', color:'#F59E0B',
    name:'Dr. Kosal Lim', specialty:'General', uni:'IU',
    experience:'3 yrs', rating:4.9, reviews:61, fee:10,
    available:'Available today', verified:true,
  },
  {
    id:4, initials:'SR', bg:'#FEF2F2', color:'#EF4444',
    name:'Dr. Sreymom Roth', specialty:'Cardiology', uni:'RUPP',
    experience:'10 yrs', rating:4.7, reviews:35, fee:25,
    available:'Available Mon', verified:true,
  },
  {
    id:5, initials:'BN', bg:'#EEF2FF', color:'#6366F1',
    name:'Dr. Bopha Nhem', specialty:'Radiology', uni:'AUSF',
    experience:'6 yrs', rating:4.5, reviews:19, fee:18,
    available:'Available Wed', verified:true,
  },
  {
    id:6, initials:'DC', bg:'#ECFDF5', color:'#10B981',
    name:'Dr. Dara Chan', specialty:'Pulmonology', uni:'UHS',
    experience:'4 yrs', rating:4.4, reviews:12, fee:15,
    available:'Available Fri', verified:false,
  },
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
  I18n.apply();

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

  /* Active nav link scroll */
  const sections = ['scan-section','history-section','doctor-section','appt-section'];
  const navLinks = document.querySelectorAll('.ud-nav-links a');
  window.addEventListener('scroll', () => {
    let current = '';
    sections.forEach(id => {
      const el = document.getElementById(id);
      if (el && window.scrollY >= el.offsetTop - 80) current = id;
    });
    navLinks.forEach(a => {
      a.classList.remove('active');
      if (current && a.href.includes(current)) a.classList.add('active');
      if (!current && a.href.endsWith('/dashboard')) a.classList.add('active');
    });
  });
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
  btn.textContent = I18n.lang === 'km' ? 'English' : 'ខ្មែរ';
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
    const res  = await api.get('/ads/active?placement=banner');
    const data = await res.json();
    if (data && data.ad) {
      const ad = data.ad;
      const img = document.getElementById('udAdImg');
      if (ad.image_url) {
        img.innerHTML = `<img src="${ad.image_url}" alt="Ad" />`;
      }
      document.getElementById('udAdText').textContent =
        (I18n.lang === 'km' ? 'ឧបត្ថម្ភ — ' : 'Sponsored — ') +
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
  if (I18n.lang === 'km') {
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
  if (UD.isPro && data.report_url) {
    document.getElementById('udPdfBtnLocked').classList.add('ud-hidden');
    const pdfPro = document.getElementById('udPdfBtnPro');
    pdfPro.href  = data.report_url;
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

  /* Table rows */
  tbody.innerHTML = scans.map(s => {
    const isPneu = s.prediction === 'PNEUMONIA';
    const date   = s.created_at
      ? new Date(s.created_at).toLocaleDateString(undefined,
          { day:'2-digit', month:'short', year:'numeric' })
      : '—';
    const scanId = '#SCN-' + String(s.id || 0).padStart(3,'0');
    const conf   = (parseFloat(s.confidence) || 0).toFixed(1) + '%';
    const procMs = s.processing_time_ms || 0;
    const aiTime = procMs ? (procMs / 1000).toFixed(1) + 's' : '—';
    const pillCls = isPneu ? 'pneumonia' : 'normal';
    const pillLbl = isPneu
      ? (I18n.t('hist_pill_pneumonia') || 'PNEUMONIA')
      : (I18n.t('hist_pill_normal')    || 'NORMAL');
    const pdfHtml = UD.isPro && s.report_id
      ? `<a class="ud-tbl-pdf-pro" href="/api/scan/report/${s.report_id}/download"
            title="Download PDF"><i class="ti ti-download"></i></a>`
      : `<span class="ud-tbl-pdf-locked" title="${I18n.t('hist_dl_locked')||'Upgrade to Pro'}">
            <i class="ti ti-lock"></i></span>`;
    return `
      <tr>
        <td>${date}</td>
        <td><span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted)">${scanId}</span></td>
        <td><span class="ud-result-pill ${pillCls}">${pillLbl}</span></td>
        <td>${conf}</td>
        <td>${aiTime}</td>
        <td>
          <div style="display:flex;align-items:center;gap:6px;">
            <a class="ud-tbl-view-btn" href="/scan/${s.id}" data-i18n="hist_view">${I18n.t('hist_view')||'View'}</a>
            ${pdfHtml}
          </div>
        </td>
      </tr>`;
  }).join('');

  /* Phone card list */
  mCards.innerHTML = scans.map(s => {
    const isPneu = s.prediction === 'PNEUMONIA';
    const date   = s.created_at
      ? new Date(s.created_at).toLocaleDateString() : '—';
    const scanId = '#SCN-' + String(s.id || 0).padStart(3,'0');
    const conf   = (parseFloat(s.confidence) || 0).toFixed(1) + '%';
    const pillCls = isPneu ? 'pneumonia' : 'normal';
    const pillLbl = isPneu
      ? (I18n.t('hist_pill_pneumonia')||'PNEUMONIA')
      : (I18n.t('hist_pill_normal')||'NORMAL');
    const pdfHtml = UD.isPro && s.report_id
      ? `<a class="ud-tbl-pdf-pro" href="/api/scan/report/${s.report_id}/download" style="font-size:13px;padding:6px 10px;">
            <i class="ti ti-download"></i> PDF</a>`
      : `<span class="ud-tbl-pdf-locked" style="font-size:13px;padding:6px 10px;">
            <i class="ti ti-lock"></i> PDF</span>`;
    return `
      <div class="ud-scan-card">
        <div class="ud-scan-card-top">
          <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted)">${scanId}</span>
          <span style="font-size:11px;color:var(--text-muted)">${date}</span>
        </div>
        <div class="ud-scan-card-mid">
          <span class="ud-result-pill ${pillCls}">${pillLbl}</span>
          <span style="font-size:12px;color:var(--text-muted)">${conf}</span>
        </div>
        <div class="ud-scan-card-bot">
          <a class="ud-tbl-view-btn" href="/scan/${s.id}" style="font-size:12px;">
            ${I18n.t('hist_view')||'View'}
          </a>
          ${pdfHtml}
        </div>
      </div>`;
  }).join('');
}

/* ════════════════════════════════════════════════════════════════════════════
   8. FIND DOCTOR PANEL
   ════════════════════════════════════════════════════════════════════════════ */
function udInitDoctors() {
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
  const query = (document.getElementById('udDoctorSearch')?.value || '').toLowerCase();
  const filter = UD.doctorFilter;

  const filtered = DOCTORS.filter(d => {
    const matchFilter = filter === 'all' || d.specialty === filter;
    const matchQuery  = !query ||
      d.name.toLowerCase().includes(query) ||
      d.specialty.toLowerCase().includes(query) ||
      d.uni.toLowerCase().includes(query);
    return matchFilter && matchQuery;
  });

  const grid = document.getElementById('udDoctorGrid');
  if (!filtered.length) {
    grid.innerHTML = `
      <div class="ud-empty" style="grid-column:1/-1;">
        <i class="ti ti-search-off"></i>
        <span class="ud-empty-h">No doctors found</span>
      </div>`;
    return;
  }

  grid.innerHTML = filtered.map(d => udDoctorCardHTML(d)).join('');
}

function udDoctorCardHTML(d) {
  const stars = Array.from({length:5}, (_,i) =>
    `<i class="ti ti-star${i < Math.floor(d.rating) ? '-filled' : ''}" style="font-size:13px;"></i>`
  ).join('');
  const verBadge = d.verified
    ? `<span class="ud-verified-badge">
         <i class="ti ti-shield-check" style="font-size:12px;"></i>
         ${I18n.t('doc_verified')||'Verified'}
       </span>`
    : '';
  return `
    <div class="ud-doc-card">
      <div class="ud-doc-top">
        <div class="ud-doc-info">
          <div class="ud-doc-avatar" style="background:${d.bg};color:${d.color};">${d.initials}</div>
          <div>
            <div class="ud-doc-name">${d.name}</div>
            <div class="ud-doc-spec">${d.specialty}</div>
          </div>
        </div>
        ${verBadge}
      </div>
      <div class="ud-doc-meta">
        <span class="ud-doc-uni">${d.uni}</span>
        <span class="ud-doc-exp">${d.experience}</span>
      </div>
      <div class="ud-doc-rating">
        <span class="ud-stars">${stars}</span>
        <span class="ud-rating-num">${d.rating}</span>
        <span class="ud-rating-rev">(${d.reviews} ${I18n.t('doc_reviews')||'reviews'})</span>
      </div>
      <div class="ud-doc-price">
        <i class="ti ti-currency-dollar"></i>
        $${d.fee} ${I18n.t('doc_consult')||'/ consultation'}
      </div>
      <div class="ud-doc-actions">
        <button class="ud-doc-view-btn" onclick="window.location='/marketplace'"
          data-i18n="doc_view">${I18n.t('doc_view')||'View Profile'}</button>
        <button class="ud-doc-book-btn" onclick="udOpenBookModal(${d.id})"
          data-i18n="doc_book">${I18n.t('doc_book')||'Book Now'}</button>
      </div>
    </div>`;
}

/* ════════════════════════════════════════════════════════════════════════════
   9. APPOINTMENTS
   ════════════════════════════════════════════════════════════════════════════ */
function udInitAppointments() {
  udRenderAppointments();
}

function udRenderAppointments() {
  const list  = document.getElementById('udApptList');
  const empty = document.getElementById('udApptEmpty');

  if (!UD.bookedAppointments.length) {
    list.innerHTML = '';
    empty.classList.remove('ud-hidden');
    return;
  }
  empty.classList.add('ud-hidden');
  list.innerHTML = UD.bookedAppointments.map(a => `
    <div class="ud-appt-row">
      <div class="ud-appt-avatar" style="background:${a.color.bg};color:${a.color.fg};">${a.initials}</div>
      <div class="ud-appt-info">
        <div class="ud-appt-name">${a.docName}</div>
        <div class="ud-appt-time">${a.date} · ${a.time}</div>
      </div>
      <span class="ud-status-pill confirmed">${I18n.t('appt_confirmed')||'Confirmed'}</span>
      <button class="ud-join-btn">
        <i class="ti ti-video"></i>
        ${I18n.t('appt_join')||'Join Meeting'}
      </button>
    </div>`
  ).join('');
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
  const d = DOCTORS.find(x => x.id === doctorId);
  if (!d) return;

  UD.activeDoctorFee  = d.fee;
  UD.activeDoctorName = d.name;
  UD.activeDoctorSpec = d.specialty;
  UD.activeDoctorColor = { bg: d.bg, color: d.color };

  /* Avatar */
  const av = document.getElementById('mdAvatar');
  av.textContent  = d.initials;
  av.style.background = d.bg;
  av.style.color      = d.color;

  document.getElementById('mdDocName').textContent = d.name;
  document.getElementById('mdDocSpec').textContent = d.specialty;
  document.getElementById('mdFee').textContent = `$${d.fee}.00`;

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

/* ── Confirm booking ────────────────────────────────────────────────────── */
function udConfirmBooking() {
  if (!UD.selectedDate) {
    udShowToast('Please select a date.', 'warning');
    return;
  }
  if (!UD.selectedTime) {
    udShowToast('Please select a time slot.', 'warning');
    return;
  }

  /* Add to local appointments */
  UD.bookedAppointments.push({
    docName:  UD.activeDoctorName,
    spec:     UD.activeDoctorSpec,
    initials: UD.activeDoctorName.split(' ').slice(1).map(w=>w[0]).join('').slice(0,2).toUpperCase() || 'DR',
    date:     UD.selectedDate,
    time:     UD.selectedTime,
    color:    { bg: UD.activeDoctorColor.bg, fg: UD.activeDoctorColor.color },
  });

  udCloseBookModal();
  udRenderAppointments();
  document.getElementById('appt-section').scrollIntoView({ behavior:'smooth' });
  udShowToast(I18n.t('toast_booked') || 'Appointment booked successfully!', 'success');
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
