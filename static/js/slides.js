/**
 * slides.js — Navigation logic for /admin/slides
 * 12-slide dark-navy presentation deck.
 * Team Work is slide 3.
 */

const TOTAL = 12;
let current = 1;

/* ── Core navigation ────────────────────────────────────────────── */
function goToSlide(n) {
  n = Math.max(1, Math.min(TOTAL, n));

  /* Hide old, show new */
  document.getElementById('slide-' + current).classList.remove('active');
  document.getElementById('dot-'   + current).classList.remove('active');
  current = n;
  document.getElementById('slide-' + current).classList.add('active');
  document.getElementById('dot-'   + current).classList.add('active');

  /* Update counters */
  const numEl = document.getElementById('slide-num');
  if (numEl) numEl.textContent = current + ' / ' + TOTAL;

  const ctrEl = document.getElementById('slide-counter');
  if (ctrEl) ctrEl.textContent = 'Slide ' + current + ' of ' + TOTAL;

  /* Update buttons */
  const prev = document.getElementById('btn-prev');
  const next = document.getElementById('btn-next');
  if (prev) prev.disabled = (current === 1);
  if (next) next.disabled = (current === TOTAL);

  /* Scroll active dot into view on narrow screens */
  const dot = document.getElementById('dot-' + current);
  if (dot) dot.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
}

function nextSlide() { goToSlide(current + 1); }
function prevSlide() { goToSlide(current - 1); }

/* ── Keyboard navigation ────────────────────────────────────────── */
document.addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') {
    e.preventDefault(); nextSlide();
  }
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    e.preventDefault(); prevSlide();
  }
  if (e.key === 'Home') { e.preventDefault(); goToSlide(1); }
  if (e.key === 'End')  { e.preventDefault(); goToSlide(TOTAL); }
  if (e.key === 'f' || e.key === 'F') toggleFullscreen();
  if (e.key === 'Escape' && document.fullscreenElement) document.exitFullscreen?.();
});

/* ── Fullscreen ─────────────────────────────────────────────────── */
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    (document.getElementById('slide-wrap') || document.documentElement)
      .requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
}
document.addEventListener('fullscreenchange', () => {
  const btn = document.getElementById('fs-btn');
  if (btn) btn.innerHTML = document.fullscreenElement
    ? '<i class="ti ti-arrows-minimize"></i> Exit'
    : '<i class="ti ti-arrows-maximize"></i> Fullscreen';
});

/* ── Touch swipe ────────────────────────────────────────────────── */
(function () {
  const wrap = document.getElementById('slide-wrap');
  if (!wrap) return;
  let sx = 0;
  wrap.addEventListener('touchstart', e => { sx = e.touches[0].clientX; }, { passive: true });
  wrap.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - sx;
    if (Math.abs(dx) < 40) return;
    if (dx < 0) nextSlide(); else prevSlide();
  }, { passive: true });
})();

/* ── Build nav dots ─────────────────────────────────────────────── */
function buildDots() {
  const c = document.getElementById('nav-dots');
  if (!c) return;
  for (let i = 1; i <= TOTAL; i++) {
    const d = document.createElement('div');
    d.className = 'dot' + (i === 1 ? ' active' : '');
    d.id        = 'dot-' + i;
    d.onclick   = () => goToSlide(i);
    d.title     = 'Slide ' + i;
    c.appendChild(d);
  }
}

/* ── Bootstrap ──────────────────────────────────────────────────── */
buildDots();
goToSlide(1);
