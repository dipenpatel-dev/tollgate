"""
module_name: cache_write.py
description: Atomic cache file writer. Writes a temp file, syncs it, then replaces the target so a crash never leaves a half written file.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported. A temp file named for the process id keeps two writers from colliding.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_replace(path: Path, data: dict[str, Any]) -> None:
    """Write data as JSON to path atomically via temp file, fsync and os.replace().

    If interrupted before os.replace(), the temp file is removed and path is untouched.
    The caller makes sure path.parent exists.
    """
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
