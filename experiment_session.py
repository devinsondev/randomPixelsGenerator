from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

from worker_protocol import WorkerConfig


class ExperimentSession:
    """Create and maintain one reproducible experiment directory."""

    def __init__(self, root: Path, initial_config: WorkerConfig) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        session_id = f"{timestamp}_{uuid4().hex[:8]}"
        self.path = root / session_id
        self.path.mkdir(parents=True, exist_ok=False)

        self._manifest_path = self.path / "manifest.json"
        self._manifest = {
            "session_id": session_id,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "initial_config": asdict(initial_config),
            "runtime": {
                "python": sys.version,
                "platform": platform.platform(),
                "numpy": np.__version__,
            },
            "workers": {},
        }
        self._write_manifest()

    @property
    def session_id(self) -> str:
        return str(self._manifest["session_id"])

    def add_worker(self, worker_id: int, worker_seed: int) -> None:
        workers = self._manifest["workers"]
        workers[str(worker_id)] = {
            "worker_seed": str(int(worker_seed)),
            "database": f"workers/worker_{worker_id:02d}.sqlite3",
            "mvp_candidates": f"candidates/mvp/worker_{worker_id:02d}",
            "robust_candidates": f"candidates/robust/worker_{worker_id:02d}",
        }
        self._write_manifest()

    def _write_manifest(self) -> None:
        self._manifest_path.write_text(
            json.dumps(self._manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
