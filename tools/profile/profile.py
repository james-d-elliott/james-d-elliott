#!/usr/bin/env python3
"""Profile README generator.

    python3 tools/profile/profile.py           # fetch + render
    python3 tools/profile/profile.py fetch     # refresh data/profile.json only
    python3 tools/profile/profile.py render    # re-render SVGs + README from cached data
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch  # noqa: E402
import render  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd not in ("all", "fetch", "render"):
        sys.exit(__doc__)
    if cmd in ("all", "fetch"):
        fetch.run(ROOT)
    if cmd in ("all", "render"):
        render.run(ROOT)
