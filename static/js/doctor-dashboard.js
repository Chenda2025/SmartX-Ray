/* ══════════════════════════════════════════════════════════════
   Doctor Dashboard JS — doctor-dashboard.js
   Prefix: dd  (functions: ddXxx, state: DD.xxx)
   ══════════════════════════════════════════════════════════════ */
'use strict';

/* ── Module state ─────────────────────────────────────────── */
const DD = {
  state: 'approved',          // current dashboard state
  dropdownOpen: false,
  toastTimers: [],
};

/* ══════════════════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  _ddInitState();
  _ddInitLang();
  _ddInitNav();
  _ddInitClickOutside();
  _ddInitKeyboard();
});

/* ── Boot: load real doctor profile from API ──────────────── */
async function _ddInitState() {
  // Try to load real profile; fall back to the body class (dev/demo mode)
  const token = localStorage.getItem('access_token');
  if (token) {
    try {
      const res  = await fetch('/api/doctor/profile', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        _ddPopulate(data.doctor);
        // Also load full dashboard data (KPIs + appointments)
        _ddLoadDashboard(token);
        return; // _ddPopulate calls ddSwitchState internally
      }
      // 404 = no doctor profile yet — show registration form
      if (res.status === 404) {
        ddSwitchState('not_registered');
        return;
      }
    } catch (_) { /* no network — fall through to dev mode */ }
  }

  // Dev / demo mode: read body class
  const body = document.body;
  if      (body.classList.contains('dd-state-pending'))         DD.state = 'pending';
  else if (body.classList.contains('dd-state-rejected'))        DD.state = 'rejected';
  else if (body.classList.contains('dd-state-not_registered'))  DD.state = 'not_registered';
  else                                                           DD.state = 'approved';

  const sel = document.getElementById('ddStateSwitcher');
  if (sel) sel.value = DD.state;
  _ddApplyStatusPill(DD.state);
}

/* ── Populate all real data from doctor object ────────────── */
function _ddPopulate(doc) {
  if (!doc) return;

  // Switch state
  ddSwitchState(doc.status || 'pending');

  // Initials helper
  const initials = (doc.full_name || 'DR')
    .split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();

  // Nav avatar + dropdown
  document.querySelectorAll('#ddAvatar, .dd-profile-avatar').forEach(el => {
    el.textContent = initials;
  });
  const nameEl = document.getElementById('ddDropName');
  const specEl = document.getElementById('ddDropSpec');
  if (nameEl) nameEl.textContent = doc.full_name || '—';
  if (specEl) specEl.textContent = doc.specialty  || '—';

  // Profile preview (pending / approved)
  document.querySelectorAll('.dd-profile-name').forEach(el => {
    el.textContent = doc.full_name || '—';
  });

  // Profile rows in pending view
  const rowMap = {
    dd_license_no:   doc.license_no      || doc.qualifications || '—',
    dd_specialty:    doc.specialty        || '—',
    dd_university:   doc.hospital         || '—',
    dd_experience:   doc.qualifications   || '—',
    dd_rate:         doc.rate_per_session ? `$${doc.rate_per_session}/session` : '—',
    dd_availability: doc.availability     || '—',
  };
  document.querySelectorAll('.dd-profile-row').forEach(row => {
    const lbl = row.querySelector('.dd-profile-lbl');
    if (!lbl) return;
    const key = lbl.getAttribute('data-i18n');
    if (key && rowMap[key] !== undefined) {
      const val = row.querySelector('span:last-child');
      if (val && val !== lbl) val.textContent = rowMap[key];
    }
  });

  // Bio
  document.querySelectorAll('.dd-profile-bio').forEach(el => {
    if (doc.bio) el.textContent = doc.bio;
  });

  // Fill the approved-state "My Profile" edit form
  _ddFillApprovedForm(doc);

  // Show "complete profile" banner if key fields are missing
  const missing = !doc.license_no || !doc.rate_per_session || !doc.availability;
  const banner  = document.getElementById('ddCompleteBanner');
  if (banner && doc.status === 'approved' && missing) {
    banner.style.display = 'flex';
  } else if (banner) {
    banner.style.display = 'none';
  }

  // Rejection reason
  if (doc.status === 'rejected' && doc.rejection_reason) {
    document.querySelectorAll('.dd-rejection-text').forEach(el => {
      el.textContent = doc.rejection_reason;
    });
    // Pre-fill flagged license field in the edit form
    const licInput = document.querySelector('.dd-form-input.error');
    if (licInput) licInput.value = doc.license_no || '';
  }

  // Pre-fill edit form fields (rejected state)
  _ddFillForm(doc);

  // Sync dev switcher
  const sel = document.getElementById('ddStateSwitcher');
  if (sel) sel.value = doc.status || 'pending';
}

/* ══════════════════════════════════════════════════════════════
   DASHBOARD DATA  —  KPIs + Upcoming Appointments
   ══════════════════════════════════════════════════════════════ */
async function _ddLoadDashboard(token) {
  try {
    const res  = await fetch('/api/doctor/dashboard', {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) return;
    const data = await res.json();

    // ── KPI cards ───────────────────────────────────────────
    _ddSetKpi('ddKpiTotal',    data.kpi?.total_appointments);
    _ddSetKpi('ddKpiToday',    data.kpi?.today_count);
    _ddSetKpi('ddKpiPatients', data.kpi?.total_patients);
    _ddSetKpi('ddKpiEarnings', data.kpi?.earnings_this_month != null
      ? `$${Number(data.kpi.earnings_this_month).toFixed(0)}` : null);

    // ── Earnings summary card ────────────────────────────────
    const es = data.earnings_summary;
    if (es) {
      _ddSetText('ddEarnMonth',   `$${Number(es.this_month   || 0).toFixed(2)}`);
      _ddSetText('ddEarnPending', `$${Number(es.pending      || 0).toFixed(2)}`);
      _ddSetText('ddEarnTotal',   `$${Number(es.total_all_time || 0).toFixed(2)}`);
    }

    // ── Upcoming Appointments table ──────────────────────────
    const upcoming = data.upcoming || [];
    _ddRenderUpcoming(upcoming);

  } catch (_) { /* network error — keep loading placeholder */ }
}

function _ddSetKpi(id, val) {
  const el = document.getElementById(id);
  if (el && val != null) el.textContent = val;
}

function _ddSetText(id, val) {
  const el = document.getElementById(id);
  if (el && val != null) el.textContent = val;
}

const _DD_COLORS = [
  ['#4F46E5','#EEF2FF'], ['#10B981','#ECFDF5'], ['#F59E0B','#FEF3C7'],
  ['#EF4444','#FEF2F2'], ['#0891B2','#ECFEFF'], ['#7C3AED','#F5F3FF'],
];
function _ddColorFor(name) {
  let h = 0;
  for (let i = 0; i < (name || '').length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return _DD_COLORS[h % _DD_COLORS.length];
}
function _ddInitials(name) {
  if (!name) return '?';
  return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
}
function _ddFmtDateTime(a) {
  const date = a.date || (a.scheduled_at || '').slice(0, 10);
  const time = a.time || (a.scheduled_at || '').slice(11, 16);
  if (!date) return '—';
  try {
    const d = new Date(date + 'T00:00:00');
    const mon = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return `${mon} · ${time || '—'}`;
  } catch (_) { return `${date} ${time}`; }
}

function _ddRenderUpcoming(list) {
  const tbody = document.getElementById('ddUpcomingTbody');
  if (!tbody) return;

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:1.5rem;color:var(--dd-muted);font-size:.85rem;">
      <i class="ti ti-calendar-off" style="font-size:1.4rem;display:block;margin-bottom:.4rem;"></i>
      No upcoming appointments
    </td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(a => {
    const [fg, bg] = _ddColorFor(a.patient_name || '');
    const initials = _ddInitials(a.patient_name || '—');
    const dateStr  = _ddFmtDateTime(a);
    const note     = a.patient_note || '—';
    const isPast   = a.status === 'confirmed' &&
                     (a.date || '') < new Date().toISOString().slice(0, 10);
    const pillCls  = isPast ? 'upcoming' : 'confirmed';
    const pillLbl  = isPast ? 'Upcoming' : 'Confirmed';

    // Attached scan badge + PDF link
    let scanHtml = '';
    if (a.attached_scan) {
      const sc      = a.attached_scan;
      const isPneu  = sc.prediction === 'PNEUMONIA';
      const color   = isPneu ? '#DC2626' : '#059669';
      const bg      = isPneu ? '#FEF2F2' : '#ECFDF5';
      const label   = isPneu ? 'Pneumonia' : 'Normal';
      const conf    = parseFloat(sc.confidence || 0).toFixed(1);
      const pdfBtn  = sc.report_url
        ? `<a href="${_ddEsc(sc.report_url)}" target="_blank"
              style="margin-left:6px;font-size:10px;color:#DC2626;text-decoration:none;
                     background:#FEF2F2;border:1px solid #FECACA;border-radius:4px;padding:1px 5px;"
              title="Download patient PDF report">
             <i class="ti ti-file-type-pdf"></i> PDF
           </a>`
        : '';
      scanHtml = `
        <div style="margin-top:4px;display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
          <i class="ti ti-x-ray" style="font-size:12px;color:#6366F1;"></i>
          <span style="font-size:10px;background:${bg};color:${color};
                       border-radius:4px;padding:1px 6px;font-weight:600;">
            ${label} ${conf}%
          </span>
          <span style="font-size:10px;color:#94A3B8;">#SCN-${String(sc.id).padStart(3,'0')}</span>
          ${pdfBtn}
        </div>`;
    }

    return `
    <tr>
      <td>
        <div class="dd-pat-cell">
          <div class="dd-pat-av" style="background:${bg};color:${fg};">${initials}</div>
          <span>${_ddEsc(a.patient_name || '—')}</span>
        </div>
      </td>
      <td>${dateStr}</td>
      <td>
        <span class="dd-note-text ${note === '—' ? 'muted' : ''}">${_ddEsc(note)}</span>
        ${scanHtml}
      </td>
      <td><span class="dd-appt-pill ${pillCls}">${pillLbl}</span></td>
      <td>
        <div class="dd-tbl-actions">
          ${a.meeting_link
            ? `<a href="${_ddEsc(a.meeting_link)}" target="_blank" class="dd-btn-sm-join" title="Join">
                 <i class="ti ti-video"></i>
               </a>`
            : `<button class="dd-btn-sm-join" onclick="ddShowToast('Meeting link not ready yet','info')" title="Join">
                 <i class="ti ti-video"></i>
               </button>`
          }
          <button class="dd-btn-sm-cancel" title="Cancel"
            onclick="ddConfirmCancel(${a.appointment_id})">
            <i class="ti ti-x"></i>
          </button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function _ddEsc(s) {
  return String(s || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function ddConfirmCancel(aptId) {
  if (!confirm('Cancel this appointment?')) return;
  const token = localStorage.getItem('access_token');
  try {
    const res = await fetch(`/api/appointments/${aptId}/cancel`, {
      method: 'PATCH',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    });
    const data = await res.json();
    if (res.ok) {
      ddShowToast('Appointment cancelled.', 'success');
      _ddLoadDashboard(token);   // refresh table
    } else {
      ddShowToast(data.error || 'Could not cancel.', 'error');
    }
  } catch (_) { ddShowToast('Network error.', 'error'); }
}

/* ── Fill the approved-state "My Profile" form ────────────── */
function _ddFillApprovedForm(doc) {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val || '';
  };
  set('prof_full_name',    doc.full_name);
  set('prof_specialty',    doc.specialty);
  set('prof_license_no',   doc.license_no);
  set('prof_hospital',     doc.hospital);
  set('prof_qualifications', doc.qualifications);
  set('prof_rate',         doc.rate_per_session != null ? String(doc.rate_per_session) : '');
  set('prof_availability', doc.availability);
  set('prof_phone',        doc.phone);
  set('prof_bio',          doc.bio);
}

/* ── Pre-fill the rejected state edit form ────────────────── */
function _ddFillForm(doc) {
  const map = {
    'dd_full_name':    doc.full_name      || '',
    'dd_specialty':    doc.specialty      || '',
    'dd_license_no':   doc.license_no     || '',
    'dd_experience':   doc.qualifications || '',
    'dd_rate':         doc.rate_per_session != null ? String(doc.rate_per_session) : '',
    'dd_availability': doc.availability   || '',
    'dd_prof_bio':     doc.bio            || '',
  };
  document.querySelectorAll('.dd-form-input, .dd-form-textarea').forEach(el => {
    const lbl = el.closest('.dd-form-group')?.querySelector('.dd-form-label');
    if (!lbl) return;
    const key = lbl.getAttribute('data-i18n');
    if (key && map[key] !== undefined && map[key] !== '') {
      el.value = map[key];
    }
  });
}

/* ── Restore persisted language ───────────────────────────── */
function _ddInitLang() {
  const saved = localStorage.getItem('lang') || 'en';
  if (saved === 'km') {
    document.body.classList.add('kh');
    document.getElementById('dd-html')?.setAttribute('lang', 'km');
    const btn = document.getElementById('ddLangBtn');
    if (btn) btn.textContent = 'English';
  }
  // i18n.js applyAll handles data-i18n elements
  if (typeof I18n !== 'undefined' && I18n.applyAll) I18n.applyAll();
}

/* ── Highlight active nav link ────────────────────────────── */
function _ddInitNav() {
  // Intercept all nav + tab clicks to prevent any browser hash navigation
  document.querySelectorAll('.dd-nav-center a, .dd-tab').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      // active state is managed by ddNavTo via onclick already
    });
  });
}

/* ══════════════════════════════════════════════════════════════
   NAVIGATION — SCROLL & ACTIVE STATE
   ══════════════════════════════════════════════════════════════ */
function ddNavTo(sectionId) {
  // ── Mark active nav link & tab ────────────────────────────
  document.querySelectorAll('.dd-nav-center a, .dd-tab').forEach(el => {
    const fn = el.getAttribute('onclick') || '';
    el.classList.toggle('active', fn.includes(`'${sectionId}'`));
  });

  if (sectionId === 'top') {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  // ── Find the target ONLY inside the currently visible state section
  // Elements in hidden sections have display:none — getBoundingClientRect()
  // returns zeros on them, so we must scope the search.
  const activeSelector =
    'body.dd-state-pending   .dd-pending-view,'  +
    'body.dd-state-approved  .dd-approved-view,' +
    'body.dd-state-rejected  .dd-rejected-view';

  const activeSection = document.querySelector(activeSelector);
  if (!activeSection) return;

  // Search order: data-nav attribute first, then id
  let target =
    activeSection.querySelector(`[data-nav="${sectionId}"]`) ||
    activeSection.querySelector(`#${sectionId}`);

  // Section doesn't exist in this state (e.g. Appointments/Earnings in pending) —
  // scroll to top so the click always does something visible.
  if (!target) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  const navH = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue('--dd-nav-h')
  ) || 68;
  const top = target.getBoundingClientRect().top + window.scrollY - navH - 20;
  window.scrollTo({ top, behavior: 'smooth' });
}

/* ── Close dropdown when clicking outside ─────────────────── */
function _ddInitClickOutside() {
  document.addEventListener('click', e => {
    const wrap = document.getElementById('ddAvatar')?.closest('.dd-avatar-wrap');
    if (DD.dropdownOpen && wrap && !wrap.contains(e.target)) {
      ddCloseDropdown();
    }
  });
}

/* ── Keyboard shortcuts ───────────────────────────────────── */
function _ddInitKeyboard() {
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') ddCloseDropdown();
  });
}

/* ══════════════════════════════════════════════════════════════
   STATE SWITCHER (dev tool)
   ══════════════════════════════════════════════════════════════ */
function ddSwitchState(value) {
  const body = document.body;
  body.classList.remove(
    'dd-state-pending', 'dd-state-approved',
    'dd-state-rejected', 'dd-state-not_registered'
  );

  const validStates = ['pending','approved','rejected','not_registered'];
  const state = validStates.includes(value) ? value : 'approved';
  body.classList.add(`dd-state-${state}`);
  DD.state = state;

  _ddApplyStatusPill(state);

  // Reset nav to Dashboard active on state change
  ddNavTo('top');

  const labels = {
    pending:        'Pending',
    approved:       'Approved',
    rejected:       'Rejected',
    not_registered: 'Registration',
  };
  ddShowToast(`Switched to ${labels[state]} state`, 'info', 1800);
}

/* ── Update the status pill in the nav ───────────────────── */
function _ddApplyStatusPill(state) {
  const pill = document.getElementById('ddStatusPill');
  if (!pill) return;

  pill.className = 'dd-status-pill'; // reset
  pill.classList.add(state);

  const configs = {
    pending:        { icon: 'ti-clock',        key: 'dd_status_pending'  },
    approved:       { icon: 'ti-shield-check', key: 'dd_status_approved' },
    rejected:       { icon: 'ti-alert-circle', key: 'dd_status_rejected' },
    not_registered: { icon: 'ti-user-plus',    key: 'dd_reg_apply'       },
  };
  const cfg = configs[state] || configs.pending;
  const lang = (typeof I18n !== 'undefined') ? I18n.getLang() : 'en';
  const text = (typeof TRANSLATIONS !== 'undefined' && TRANSLATIONS[cfg.key])
    ? TRANSLATIONS[cfg.key][lang]
    : cfg.key;

  pill.innerHTML = `<i class="ti ${cfg.icon}"></i><span>${text}</span>`;
}

/* ══════════════════════════════════════════════════════════════
   LANGUAGE TOGGLE
   ══════════════════════════════════════════════════════════════ */
function ddToggleLang() {
  if (typeof I18n === 'undefined') return;

  I18n.toggle();

  const lang = I18n.getLang();
  const btn  = document.getElementById('ddLangBtn');
  if (btn) btn.textContent = lang === 'km' ? 'English' : 'ខ្មែរ';

  document.body.classList.toggle('kh', lang === 'km');
  document.getElementById('dd-html')?.setAttribute('lang', lang === 'km' ? 'km' : 'en');

  _ddApplyStatusPill(DD.state);
}

/* ══════════════════════════════════════════════════════════════
   AVATAR DROPDOWN
   ══════════════════════════════════════════════════════════════ */
function ddToggleDropdown() {
  if (DD.dropdownOpen) {
    ddCloseDropdown();
  } else {
    ddOpenDropdown();
  }
}

function ddOpenDropdown() {
  const dd = document.getElementById('ddDropdown');
  if (!dd) return;
  dd.classList.add('open');
  DD.dropdownOpen = true;
}

function ddCloseDropdown() {
  const dd = document.getElementById('ddDropdown');
  if (!dd) return;
  dd.classList.remove('open');
  DD.dropdownOpen = false;
}

/* ══════════════════════════════════════════════════════════════
   FILE UPLOAD HELPERS
   ══════════════════════════════════════════════════════════════ */
/**
 * Show the selected filename inside the upload zone label.
 * @param {HTMLInputElement} input  — the hidden file input
 * @param {string}           labelId — id of the <span> to update
 */
function ddHandleFileSelect(input, labelId) {
  const label = document.getElementById(labelId);
  const zone  = input.closest('.dd-form-group')?.querySelector('.dd-upload-zone')
              || input.parentElement?.querySelector('.dd-upload-zone');

  if (input.files && input.files[0]) {
    const name = input.files[0].name;
    const size = (input.files[0].size / 1024).toFixed(0);
    if (label) label.textContent = `✓ ${name}  (${size} KB)`;
    if (zone)  zone.classList.add('has-file');
  } else {
    // reset
    if (label) {
      // restore i18n default text
      const key = label.getAttribute('data-i18n');
      const lang = (typeof I18n !== 'undefined') ? I18n.getLang() : 'en';
      label.textContent = (typeof TRANSLATIONS !== 'undefined' && TRANSLATIONS[key])
        ? TRANSLATIONS[key][lang]
        : (key || 'Upload a file');
    }
    if (zone) zone.classList.remove('has-file');
  }
}

/**
 * Handle file drag-and-drop onto the upload zone.
 */
function ddHandleDrop(event, inputId, labelId) {
  event.preventDefault();
  const zone  = event.currentTarget;
  zone.classList.remove('drag-over');

  const input = document.getElementById(inputId);
  if (!input) return;

  const dt    = event.dataTransfer;
  if (dt.files && dt.files.length) {
    // Assign dragged file to the hidden input via DataTransfer
    try {
      const transfer = new DataTransfer();
      transfer.items.add(dt.files[0]);
      input.files = transfer.files;
    } catch (_) {
      // DataTransfer not supported — ignore, user can click to choose
    }
    ddHandleFileSelect(input, labelId);
  }
}

/* ══════════════════════════════════════════════════════════════
   REGISTER AS DOCTOR (not_registered state — first time)
   ══════════════════════════════════════════════════════════════ */
async function ddRegister() {
  // Hide previous error
  const errBanner = document.getElementById('ddRegError');
  const errMsg    = document.getElementById('ddRegErrorMsg');
  if (errBanner) errBanner.style.display = 'none';

  // Collect form
  const full_name    = document.getElementById('reg_full_name')?.value.trim()    || '';
  const specialty    = document.getElementById('reg_specialty')?.value.trim()    || '';
  const license_no   = document.getElementById('reg_license_no')?.value.trim()   || '';
  const hospital     = document.getElementById('reg_hospital')?.value.trim()     || '';
  const qualifications = document.getElementById('reg_qualifications')?.value.trim() || '';
  const rate_str     = document.getElementById('reg_rate')?.value.trim()         || '';
  const availability = document.getElementById('reg_availability')?.value.trim() || '';
  const bio          = document.getElementById('reg_bio')?.value.trim()          || '';

  // Validate required
  if (!full_name || !specialty) {
    if (errBanner && errMsg) {
      errMsg.textContent = 'Full name and specialty are required.';
      errBanner.style.display = 'flex';
    } else {
      ddShowToast('Full name and specialty are required.', 'error');
    }
    return;
  }

  const token = localStorage.getItem('access_token');
  if (!token) {
    ddShowToast('You must be logged in to apply.', 'error');
    setTimeout(() => { window.location.href = '/login'; }, 1500);
    return;
  }

  // Disable button while submitting
  const btn = document.getElementById('ddRegBtn');
  if (btn) { btn.disabled = true; btn.style.opacity = '0.7'; }

  try {
    const res  = await fetch('/api/doctor/profile', {
      method:  'POST',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        full_name, specialty, license_no, hospital,
        qualifications, availability, bio,
        rate_per_session: parseFloat(rate_str) || 0,
      }),
    });
    const data = await res.json();

    if (res.status === 201) {
      ddShowToast('Application submitted! Admin will review within 24 hours.', 'success', 5000);
      _ddPopulate(data.doctor);   // switches to "pending" state with real data
    } else if (res.status === 409) {
      // Profile already exists — load it
      ddShowToast('Profile already exists — loading your dashboard.', 'info');
      _ddPopulate(data.doctor);
    } else {
      const msg = data.error || 'Submission failed. Please try again.';
      if (errBanner && errMsg) { errMsg.textContent = msg; errBanner.style.display = 'flex'; }
      else ddShowToast(msg, 'error');
    }
  } catch {
    ddShowToast('Network error. Please check your connection.', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.style.opacity = ''; }
  }
}

/* ══════════════════════════════════════════════════════════════
   RESUBMIT APPLICATION (rejected state)
   ══════════════════════════════════════════════════════════════ */
async function ddResubmit() {
  // Collect form fields
  const getVal = (i18nKey) => {
    const lbl = document.querySelector(`.dd-form-label[data-i18n="${i18nKey}"]`);
    if (!lbl) return null;
    const input = lbl.closest('.dd-form-group')?.querySelector('input,textarea');
    return input ? input.value.trim() : null;
  };

  const payload = {
    full_name:       getVal('dd_full_name'),
    specialty:       getVal('dd_specialty'),
    license_no:      getVal('dd_license_no'),
    qualifications:  getVal('dd_experience'),
    rate_per_session:parseFloat(getVal('dd_rate')) || 0,
    availability:    getVal('dd_availability'),
    bio:             getVal('dd_prof_bio'),
  };

  const token = localStorage.getItem('access_token');
  if (!token) { ddShowToast('Not logged in.', 'error'); return; }

  try {
    const res  = await fetch('/api/doctor/profile', {
      method:  'PUT',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok) {
      ddShowToast('Application resubmitted! Admin will review within 24 hours.', 'success', 4000);
      _ddPopulate(data.doctor);
    } else {
      ddShowToast(data.error || 'Resubmit failed.', 'error');
    }
  } catch {
    ddShowToast('Network error. Please try again.', 'error');
  }
}

/* ══════════════════════════════════════════════════════════════
   SAVE PROFILE (approved state — complete / update info)
   ══════════════════════════════════════════════════════════════ */
async function ddSaveProfile() {
  const errBanner = document.getElementById('ddProfError');
  const errMsg    = document.getElementById('ddProfErrorMsg');
  if (errBanner) errBanner.style.display = 'none';

  const payload = {
    mode:            'complete',   // keeps doctor verified, no pending reset
    full_name:        (document.getElementById('prof_full_name')?.value    || '').trim(),
    specialty:        (document.getElementById('prof_specialty')?.value    || '').trim(),
    license_no:       (document.getElementById('prof_license_no')?.value   || '').trim(),
    hospital:         (document.getElementById('prof_hospital')?.value     || '').trim(),
    qualifications:   (document.getElementById('prof_qualifications')?.value || '').trim(),
    rate_per_session: parseFloat(document.getElementById('prof_rate')?.value) || 0,
    availability:     (document.getElementById('prof_availability')?.value || '').trim(),
    phone:            (document.getElementById('prof_phone')?.value        || '').trim(),
    bio:              (document.getElementById('prof_bio')?.value          || '').trim(),
  };

  if (!payload.full_name || !payload.specialty) {
    if (errBanner && errMsg) {
      errMsg.textContent = 'Full name and specialty are required.';
      errBanner.style.display = 'flex';
    }
    return;
  }

  const token = localStorage.getItem('access_token');
  if (!token) { ddShowToast('Not logged in.', 'error'); return; }

  const btn = document.getElementById('ddProfSaveBtn');
  if (btn) { btn.disabled = true; btn.style.opacity = '0.7'; }

  try {
    const res  = await fetch('/api/doctor/profile', {
      method:  'PUT',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok) {
      ddShowToast('Profile saved successfully!', 'success', 3500);
      _ddPopulate(data.doctor);   // refresh all UI with latest data
    } else {
      const msg = data.error || 'Save failed.';
      if (errBanner && errMsg) { errMsg.textContent = msg; errBanner.style.display = 'flex'; }
      else ddShowToast(msg, 'error');
    }
  } catch {
    ddShowToast('Network error. Please try again.', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.style.opacity = ''; }
  }
}

/* ══════════════════════════════════════════════════════════════
   LOGOUT
   ══════════════════════════════════════════════════════════════ */
function ddLogout() {
  ddCloseDropdown();
  ddShowToast('Signing out…', 'info', 1500);
  setTimeout(() => {
    // Clear stored tokens
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    sessionStorage.clear();
    window.location.href = '/login';
  }, 1200);
}

/* ══════════════════════════════════════════════════════════════
   TOAST SYSTEM
   Usage: ddShowToast('Message', 'success'|'error'|'info'|'warning', ms?)
   ══════════════════════════════════════════════════════════════ */
function ddShowToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('ddToastContainer');
  if (!container) return;

  const icons = {
    success: 'ti-circle-check',
    error:   'ti-circle-x',
    info:    'ti-info-circle',
    warning: 'ti-alert-triangle',
  };

  const toast = document.createElement('div');
  toast.className = `dd-toast ${type}`;
  toast.innerHTML = `<i class="ti ${icons[type] || icons.info}"></i><span>${_ddEsc(message)}</span>`;
  container.appendChild(toast);

  const timer = setTimeout(() => _ddDismissToast(toast), duration);
  DD.toastTimers.push(timer);

  // Click to dismiss
  toast.addEventListener('click', () => _ddDismissToast(toast));
}

function _ddDismissToast(toast) {
  toast.classList.add('out');
  setTimeout(() => toast.remove(), 220);
}

/* ══════════════════════════════════════════════════════════════
   UTILS
   ══════════════════════════════════════════════════════════════ */
function _ddEsc(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
