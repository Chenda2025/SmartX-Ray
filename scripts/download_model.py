#!/usr/bin/env python3
"""
Model download script — runs during Render build (or any CI deploy).

Set the MODEL_URL environment variable to the direct download link of
best_model.h5 before running this script.

Supported hosts (all provide stable direct-download URLs):
  • GitHub Releases  https://github.com/USER/REPO/releases/download/TAG/best_model.h5
  • Hugging Face     https://huggingface.co/USER/REPO/resolve/main/best_model.h5
  • Google Drive     use the export URL — see README for instructions

Usage:
  MODEL_URL=https://... python scripts/download_model.py
"""

import os
import sys
import hashlib
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────
MODEL_PATH   = Path("models/best_model.h5")
MODEL_URL    = os.environ.get("MODEL_URL", "").strip()
MODEL_SHA256 = os.environ.get("MODEL_SHA256", "").strip().lower()  # optional checksum
MIN_BYTES    = 10 * 1024 * 1024   # anything < 10 MB is probably a placeholder/corrupt

CHUNK        = 1024 * 256          # 256 KB read chunks


def _size_str(n: int) -> str:
    return f"{n / 1_048_576:.1f} MB"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify(path: Path) -> bool:
    """Return True if file is present, large enough, and checksum matches (if provided)."""
    if not path.exists():
        return False
    size = path.stat().st_size
    if size < MIN_BYTES:
        print(f"  ✗ File too small ({_size_str(size)}) — treating as invalid.")
        return False
    if MODEL_SHA256:
        print("  Verifying SHA-256 …", end=" ", flush=True)
        digest = _sha256(path)
        if digest != MODEL_SHA256:
            print(f"MISMATCH\n  expected: {MODEL_SHA256}\n  got:      {digest}")
            return False
        print("OK")
    return True


def _download(url: str, dest: Path) -> None:
    """Download url → dest with a progress bar. Works on Python 3.8+."""
    try:
        import requests                                    # available after pip install
        _download_requests(url, dest)
    except ImportError:
        _download_urllib(url, dest)                        # stdlib fallback


def _download_requests(url: str, dest: Path) -> None:
    import requests
    print(f"  Using requests …")
    with requests.get(url, stream=True, timeout=600,
                      headers={"User-Agent": "SmartXRay-build/1.0"}) as r:
        r.raise_for_status()
        total    = int(r.headers.get("content-length", 0))
        received = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK):
                f.write(chunk)
                received += len(chunk)
                _progress(received, total)
    print()   # newline after progress


def _download_urllib(url: str, dest: Path) -> None:
    import urllib.request
    print(f"  Using urllib (no progress bar) …")

    def _reporthook(count, block_size, total):
        _progress(count * block_size, total)

    urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
    print()


def _progress(received: int, total: int) -> None:
    if total:
        pct  = min(received / total * 100, 100)
        bar  = "█" * int(pct // 2) + "░" * (50 - int(pct // 2))
        print(f"\r  [{bar}] {pct:5.1f}%  {_size_str(received)} / {_size_str(total)} ",
              end="", flush=True)
    else:
        print(f"\r  {_size_str(received)} downloaded …", end="", flush=True)


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 60)
    print("SmartX-Ray — model download")
    print("=" * 60)

    # ── 1. Already present? ─────────────────────────────────────────────────
    if _verify(MODEL_PATH):
        print(f"✓ Model already present "
              f"({_size_str(MODEL_PATH.stat().st_size)}) — skipping download.")
        return 0

    # ── 2. URL required ─────────────────────────────────────────────────────
    if not MODEL_URL:
        print("⚠  MODEL_URL is not set.")
        print("   The app will start, but X-ray scan features will be disabled")
        print("   until a valid model is placed at models/best_model.h5.")
        print()
        print("   To enable scans:")
        print("   1. Upload models/best_model.h5 to GitHub Releases or Hugging Face.")
        print("   2. Set MODEL_URL in Render → Environment → MODEL_URL.")
        print("   3. Trigger a manual deploy.")
        return 0                                   # non-fatal: app still starts

    # ── 3. Download ─────────────────────────────────────────────────────────
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MODEL_PATH.with_suffix(".h5.tmp")

    print(f"⬇  Downloading from:\n   {MODEL_URL}\n")
    try:
        _download(MODEL_URL, tmp)
    except Exception as exc:
        print(f"\n✗  Download failed: {exc}")
        tmp.unlink(missing_ok=True)
        print("   App will start without the model (scans disabled).")
        return 0                                   # non-fatal

    # ── 4. Verify ───────────────────────────────────────────────────────────
    size = tmp.stat().st_size
    print(f"  Downloaded {_size_str(size)}")

    if size < MIN_BYTES:
        print(f"✗  File too small — download may have failed or URL returned an error page.")
        tmp.unlink(missing_ok=True)
        return 0

    if MODEL_SHA256:
        print("  Verifying SHA-256 …", end=" ", flush=True)
        digest = _sha256(tmp)
        if digest != MODEL_SHA256:
            print(f"MISMATCH\n  expected: {MODEL_SHA256}\n  got:      {digest}")
            tmp.unlink(missing_ok=True)
            print("  ✗  Corrupt download — keeping app running without model.")
            return 0
        print("OK")

    # ── 5. Commit ───────────────────────────────────────────────────────────
    tmp.rename(MODEL_PATH)
    print(f"✓  Model saved → {MODEL_PATH}  ({_size_str(MODEL_PATH.stat().st_size)})")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
