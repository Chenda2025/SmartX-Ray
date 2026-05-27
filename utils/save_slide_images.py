"""
save_slide_images.py
────────────────────
Utility to save base64-encoded images to static/img/.
Run once after encoding images.

Usage:
    python utils/save_slide_images.py

Images needed:
    static/img/teacher_eagle.jpg  — subject teacher photo
    static/img/team_chenda.jpg    — Tob Chenda photo
    static/img/team_heang.jpg     — Ly Heang photo
"""

import os
import base64


def save_base64_image(b64_string: str, filename: str) -> str:
    """Decode a base64 string and save it to static/img/<filename>."""
    path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', filename)
    path = os.path.normpath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Strip data-URL prefix if present  (e.g. "data:image/jpeg;base64,...")
    if ',' in b64_string:
        b64_string = b64_string.split(',', 1)[1]

    with open(path, 'wb') as f:
        f.write(base64.b64decode(b64_string))

    print(f'✓  Saved: {path}')
    return path


if __name__ == '__main__':
    # ── Replace the placeholder strings below with actual base64 data ──
    # TEACHER_B64 = "..."   # paste base64 of teacher_eagle.jpg
    # CHENDA_B64  = "..."   # paste base64 of team_chenda.jpg
    # HEANG_B64   = "..."   # paste base64 of team_heang.jpg

    # save_base64_image(TEACHER_B64, 'teacher_eagle.jpg')
    # save_base64_image(CHENDA_B64,  'team_chenda.jpg')
    # save_base64_image(HEANG_B64,   'team_heang.jpg')

    print('Edit this script to set TEACHER_B64, CHENDA_B64, HEANG_B64 then re-run.')
