#!/usr/bin/env python
"""Seed baseline data: jurisdictions, policies, users and sample AI systems.

    python scripts/seed.py     # or: python -m scripts.seed
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running `python scripts/seed.py` puts `scripts/` on sys.path, not the repository root,
# so `import app` would fail. Fix that before importing anything from the application.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.seed import run_seed  # noqa: E402

if __name__ == "__main__":
    print(run_seed())
