"""
Auto-download Khmer OS fonts if they are missing from static/fonts/.

Font coverage summary (important!):
  KhmerOSMuolLight.ttf   — 204 glyphs  ✅ Khmer + Latin  (headers)
  KhmerOSBattambang.ttf  — 204 glyphs  ✅ Khmer + Latin  (titles)
  KhmerOSSiemreap.ttf    — 139 glyphs  ❌ Khmer only     (no A-Z/a-z)

  Because KhmerOSSiemreap lacks Latin glyphs, pdf_service.register_khmer_fonts()
  automatically falls back to Battambang-Regular.ttf (already bundled) for the
  KhmerSiemreap font slot. This prevents □ boxes when rendering email addresses,
  English names, and status labels like "(Active)" / "(Suspended)".

  All three font files are still downloaded so they are available for:
  - Pure-Khmer rendering where desired
  - Future upgrade if a full-coverage Siemreap variant becomes available

Source:
  Fonts downloaded from Google Fonts GitHub (OFL-1.1 licensed):
  KhmerOSMuolLight  ← Moul-Regular.ttf       (same typeface, different filename)
  KhmerOSBattambang ← Battambang-Regular.ttf  (same typeface, different filename)
  KhmerOSSiemreap   ← Siemreap.ttf            (same typeface, different filename)

Usage:
  Called automatically from app.py on startup.
  Can also be run directly: python utils/download_fonts.py
"""

import os
import logging

logger = logging.getLogger(__name__)

# Google Fonts GitHub raw URLs (OFL-1.1 open source)
FONTS = {
    "KhmerOSMuolLight.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/moul/Moul-Regular.ttf"
    ),
    "KhmerOSBattambang.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/battambang/Battambang-Regular.ttf"
    ),
    "KhmerOSSiemreap.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/siemreap/Siemreap.ttf"
    ),
}


def download_khmer_fonts(font_dir: str | None = None) -> None:
    """
    Download each Khmer OS font file if it does not already exist locally.

    Parameters
    ----------
    font_dir : path to the fonts directory; defaults to ``static/fonts/``
               relative to the project root (one level above this file).
    """
    if font_dir is None:
        font_dir = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "static", "fonts")
        )

    os.makedirs(font_dir, exist_ok=True)

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed — skipping Khmer font download.")
        return

    for filename, url in FONTS.items():
        path = os.path.join(font_dir, filename)
        if os.path.exists(path):
            logger.debug("Font already present: %s", filename)
            continue

        logger.info("Downloading %s ...", filename)
        try:
            r = requests.get(url, timeout=30, allow_redirects=True)
            if r.status_code == 200 and len(r.content) > 10_000:
                with open(path, "wb") as fh:
                    fh.write(r.content)
                logger.info("Saved %s (%d bytes)", path, len(r.content))
                print(f"  ✅ Downloaded: {filename} ({len(r.content):,} bytes)")
            else:
                logger.error(
                    "Failed to download %s — HTTP %s, size=%d",
                    filename, r.status_code, len(r.content),
                )
                print(f"  ❌ Failed: {filename} — HTTP {r.status_code}")
        except Exception as exc:
            logger.error("Error downloading %s: %s", filename, exc)
            print(f"  ❌ Error: {filename} — {exc}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Checking Khmer OS fonts …")
    download_khmer_fonts()
    print("Done.")
