#!/usr/bin/env python
"""Push every active policy's Rego into a running OPA instance.

    python scripts/sync_opa.py     # or: python -m scripts.sync_opa
"""

from __future__ import annotations

import sys
from pathlib import Path

# See scripts/seed.py: make the repository root importable regardless of how this is run.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import session_scope  # noqa: E402
from app.services.policy import PolicyService  # noqa: E402

if __name__ == "__main__":
    with session_scope() as db:
        print(PolicyService(db).sync_all_to_opa())
