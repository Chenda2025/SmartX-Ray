#!/usr/bin/env python3
"""Print the SHA-256 of models/best_model.h5 — paste it into MODEL_SHA256 on Render."""
import hashlib, sys
from pathlib import Path

path = Path("models/best_model.h5")
if not path.exists():
    print("models/best_model.h5 not found.", file=sys.stderr)
    sys.exit(1)

h = hashlib.sha256()
with open(path, "rb") as f:
    for chunk in iter(lambda: f.read(1024 * 256), b""):
        h.update(chunk)

print(h.hexdigest())
