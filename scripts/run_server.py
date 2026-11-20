#!/usr/bin/env python3
"""Run the local BASIRA backend service (loopback only).

The service binds to 127.0.0.1:8765 and requires a bearer token that is
generated on first run and stored in the local database. Print it with:
    python scripts/run_server.py --show-token
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from any working directory: ensure the project root
# (parent of scripts/) is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from basira.config import database_path, load_settings
from basira.db.database import Database
from basira.intelligence.orchestrator import BASIRACore
from basira.server.app import LocalServer, get_or_create_token


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-token", action="store_true")
    args = ap.parse_args()
    settings = load_settings()
    db = Database(database_path())
    token = get_or_create_token(db)
    if args.show_token:
        print(token)
        return 0
    core = BASIRACore(db, settings)
    server = LocalServer(core, db, settings)
    server.start()
    print(f"BASIRA local service on {server.url} (loopback only, token required)")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        core.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
