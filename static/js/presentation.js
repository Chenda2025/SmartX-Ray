/**
 * presentation.js
 * Slide navigation, scaling, fullscreen, and keyboard control
 * for /admin/presentation
 */

/* ── Constants ──────────────────────────────────────────────────── */
const PRES_TOTAL = 10;

/* ── State ──────────────────────────────────────────────────────── */
let presSlide = 0;

/* ═══════════════════════════════════════════════════════════════════
   goToSlide(n)
   ─────────────────────────────────────────────────────────────────
   1. Clamp n to [0, PRES_TOTAL-1]
   2. Show matching .pres-slide, hide all others
   3. Mark matching .pres-thumb as active
   4. Update counter text + progress bar width
   5. Enable/disable Prev / Next buttons
   6. Scroll active thumbnail into view
   ═══════════════════════════════════════════════════════════════════ */
function goToSlide(n) {
  n = Math.max(0, Math.min(PRES_TOTAL - 1, n));
  presSlide = n;

  /* Slides */
  document.querySelectorAll('.pres-slide').forEach((s, i) => {
    s.classList.toggle('active', i === n);
  });

  /* Thumbnails */
  document.querySelectorAll('.pres-thumb').forEach((t, i) => {
    t.classList.toggle('active', i === n);
  });

  /* Counter */
  const counter = document.getElementById('pres-counter');
  if (counter) counter.textContent = `Slide ${n + 1} of ${PRES_TOTAL}`;

  /* Progress bar */
  const fill = document.getElementById('pres-progress-fill');
  if (fill) fill.style.width = `${((n + 1) / PRES_TOTAL) * 100}%`;

  /* Prev / Next buttons */
  const prev = document.getElementById('pres-prev');
  const next = document.getElementById('pres-next');
  if (prev) prev.disabled = (n === 0);
  if (next) next.disabled = (n === PRES_TOTAL - 1);

  /* Scroll thumb into view (mobile / overflow-y) */
  const thumb = document.querySelectorAll('.pres-thumb')[n];
  if (thumb) thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ── Scale stage to fit outer container ─────────────────────────── */
function updateScale() {
  const outer = document.getElementById('pres-stage-outer');
  const stage = document.getElementById('pres-stage');
  if (!outer || !stage) return;

  const pad  = 8;                             /* visual breathing room */
  const avW  = outer.clientWidth  - pad * 2;
  const avH  = outer.clientHeight - pad * 2;
  const scale = Math.min(avW / 960, avH / 540);

  const scaledW = 960 * scale;
  const scaledH = 540 * scale;
  const offX    = (outer.clientWidth  - scaledW) / 2;
  const offY    = (outer.clientHeight - scaledH) / 2;

  stage.style.transform       = `scale(${scale})`;
  stage.style.transformOrigin = 'top left';
  stage.style.left            = `${offX}px`;
  stage.style.top             = `${offY}px`;
}

/* ── Fullscreen ──────────────────────────────────────────────────── */
function enterFullscreen() {
  const el = document.documentElement;
  if (el.requestFullscreen)       el.requestFullscreen();
  else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
}

function exitPresentationFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
  } else if (document.webkitFullscreenElement) {
    document.webkitExitFullscreen?.();
  }
}

/* ── Print / Export ──────────────────────────────────────────────── */
function printPresentation() {
  window.print();
}

/* ── Keyboard navigation ─────────────────────────────────────────── */
document.addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

  switch (e.key) {
    case 'ArrowRight':
    case 'ArrowDown':
    case ' ':          e.preventDefault(); goToSlide(presSlide + 1); break;

    case 'ArrowLeft':
    case 'ArrowUp':    e.preventDefault(); goToSlide(presSlide - 1); break;

    case 'Home':       e.preventDefault(); goToSlide(0);            break;
    case 'End':        e.preventDefault(); goToSlide(PRES_TOTAL-1); break;

    case 'f':
    case 'F':          enterFullscreen(); break;

    case 'Escape':
      if (document.fullscreenElement || document.webkitFullscreenElement) {
        exitPresentationFullscreen();
      }
      break;

    case 'p':
    case 'P':          printPresentation(); break;
  }
});

/* ── Fullscreen change — rescale when entering/leaving ──────────── */
document.addEventListener('fullscreenchange',       () => updateScale());
document.addEventListener('webkitfullscreenchange', () => updateScale());

/* ── ResizeObserver — rescale on container resize ───────────────── */
(function watchResize() {
  const outer = document.getElementById('pres-stage-outer');
  if (!outer) return;
  const ro = new ResizeObserver(() => updateScale());
  ro.observe(outer);
})();

/* ── Thumbnail click delegation ─────────────────────────────────── */
document.querySelectorAll('.pres-thumb').forEach((thumb, i) => {
  thumb.addEventListener('click', () => goToSlide(i));
});

/* ── Touch swipe support ─────────────────────────────────────────── */
(function initSwipe() {
  const outer = document.getElementById('pres-stage-outer');
  if (!outer) return;
  let startX = 0;
  outer.addEventListener('touchstart', e => { startX = e.touches[0].clientX; }, { passive: true });
  outer.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - startX;
    if (Math.abs(dx) < 40) return;      /* ignore micro-swipes */
    if (dx < 0) goToSlide(presSlide + 1);
    else        goToSlide(presSlide - 1);
  }, { passive: true });
})();

/* ── i18n hook ───────────────────────────────────────────────────── */
function _applyI18n() {
  if (typeof I18n !== 'undefined' && typeof I18n.applyAll === 'function') {
    I18n.applyAll();
  }
}

/* ── Bootstrap ───────────────────────────────────────────────────── */
(function init() {
  _applyI18n();
  goToSlide(0);
  updateScale();
})();
