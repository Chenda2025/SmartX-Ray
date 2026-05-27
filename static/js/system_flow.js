/**
 * system_flow.js
 * Stage navigation logic for /admin/system-flow
 *
 * Responsibilities:
 *  - goToStage(index)  — show/hide panels, update dot state, update counters
 *  - Dot click listeners
 *  - Keyboard ← / → navigation
 *  - i18n integration (applies translations after TRANSLATIONS are merged)
 */

/* ── Constants ─────────────────────────────────────────────────── */
const TOTAL_STAGES = 8;

/* ── State ──────────────────────────────────────────────────────── */
let currentStage = 0;

/* ═══════════════════════════════════════════════════════════════
   goToStage
   Clamps index to [0, TOTAL_STAGES-1], then:
     1. Shows the matching .stage-panel (hides all others)
     2. Marks dots as active / done
     3. Enables / disables Prev & Next buttons
     4. Updates every .stage-counter inside the active panel
     5. Scrolls the active dot into view on narrow screens
   ═══════════════════════════════════════════════════════════════ */
function goToStage(index) {
  const next = Math.max(0, Math.min(TOTAL_STAGES - 1, index));
  currentStage = next;

  /* 1. Show / hide panels */
  document.querySelectorAll('.stage-panel').forEach((panel, i) => {
    panel.classList.toggle('sf-active', i === currentStage);
  });

  /* 2. Dot state: done < current, active = current, default > current */
  document.querySelectorAll('.stage-dot').forEach((dot, i) => {
    dot.classList.remove('active', 'done');
    if (i < currentStage)  dot.classList.add('done');
    if (i === currentStage) dot.classList.add('active');
  });

  /* 3 + 4. Buttons and counter inside the now-active panel */
  const activePanel = document.getElementById(`stage-${currentStage}`);
  if (activePanel) {
    /* Prev / Next buttons — use attribute selector so both id= and class= variants work */
    activePanel.querySelectorAll('[id="btn-prev"], .sf-nav-btn-prev').forEach(btn => {
      btn.disabled = (currentStage === 0);
    });
    activePanel.querySelectorAll('[id="btn-next"], .sf-nav-btn-next').forEach(btn => {
      btn.disabled = (currentStage === TOTAL_STAGES - 1);
    });

    /* Stage counter text — keep it i18n-neutral (always EN here; i18n.js owns lang toggle) */
    activePanel.querySelectorAll('.stage-counter').forEach(el => {
      el.textContent = `Stage ${currentStage + 1} of ${TOTAL_STAGES}`;
    });
  }

  /* 5. Scroll active dot into view (mobile horizontal overflow) */
  const activeDot = document.querySelector(`.stage-dot[data-stage="${currentStage}"]`);
  if (activeDot) {
    activeDot.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }
}

/* ── Dot click listeners ────────────────────────────────────────── */
function _initDots() {
  document.querySelectorAll('.stage-dot').forEach((dot, i) => {
    dot.addEventListener('click', () => goToStage(i));
  });
}

/* ── Keyboard navigation ← / → ─────────────────────────────────── */
function _initKeyboard() {
  document.addEventListener('keydown', e => {
    /* Ignore when focus is inside a form control */
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown')  goToStage(currentStage + 1);
    if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')    goToStage(currentStage - 1);
    if (e.key === 'Home')                                   goToStage(0);
    if (e.key === 'End')                                    goToStage(TOTAL_STAGES - 1);
  });
}

/* ── i18n hook ──────────────────────────────────────────────────── */
function _applyI18n() {
  if (typeof I18n !== 'undefined' && typeof I18n.applyAll === 'function') {
    I18n.applyAll();
  }
}

/* ── Bootstrap ──────────────────────────────────────────────────── */
(function init() {
  _initDots();
  _initKeyboard();
  _applyI18n();
  goToStage(0);   /* render stage 1 as active on page load */
})();
