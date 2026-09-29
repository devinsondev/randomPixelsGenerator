from __future__ import annotations

import multiprocessing as mp
import queue
import secrets
from dataclasses import dataclass
from pathlib import Path

from experiment_session import ExperimentSession
from parallel_worker import run_generator_worker
from worker_protocol import WorkerConfig, WorkerSnapshot

MAX_WORKERS = 16


@dataclass(slots=True)
class _WorkerHandle:
    worker_id: int
    process: mp.Process
    command_queue: mp.Queue
    output_queue: mp.Queue
    stop_event: mp.Event


class ProcessManager:
    """Own child generator processes and one experiment session."""

    def __init__(self, initial_config: WorkerConfig) -> None:
        self._context = mp.get_context("spawn")
        self._config = initial_config.validated()
        self._workers: dict[int, _WorkerHandle] = {}
        self._session = ExperimentSession(
            root=Path("experiment_data"),
            initial_config=self._config,
        )

    @property
    def worker_count(self) -> int:
        return len(self._workers)

    @property
    def worker_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._workers))

    @property
    def session_dir(self) -> Path:
        return self._session.path

    def add_worker(self) -> int:
        if self.worker_count >= MAX_WORKERS:
            raise ValueError(f"Maximum worker count is {MAX_WORKERS}.")

        worker_id = self._first_free_id()
        worker_seed = secrets.randbits(64)
        self._session.add_worker(worker_id, worker_seed)

        command_queue = self._context.Queue(maxsize=1)
        output_queue = self._context.Queue(maxsize=2)
        stop_event = self._context.Event()

        process = self._context.Process(
            target=run_generator_worker,
            args=(
                worker_id,
                worker_seed,
                self._session.path,
                self._config,
                command_queue,
                output_queue,
                stop_event,
            ),
            name=f"pixel-generator-{worker_id:02d}",
            daemon=True,
        )
        process.start()

        self._workers[worker_id] = _WorkerHandle(
            worker_id=worker_id,
            process=process,
            command_queue=command_queue,
            output_queue=output_queue,
            stop_event=stop_event,
        )
        return worker_id

    def remove_last_worker(self) -> int | None:
        if not self._workers:
            return None

        worker_id = max(self._workers)
        self._stop_worker(worker_id)
        return worker_id

    def update_config(self, config: WorkerConfig) -> None:
        self._config = config.validated()
        for handle in self._workers.values():
            _put_latest(handle.command_queue, self._config)

    def poll_latest(self) -> list[WorkerSnapshot]:
        snapshots: list[WorkerSnapshot] = []

        for handle in self._workers.values():
            latest: WorkerSnapshot | None = None
            while True:
                try:
                    latest = handle.output_queue.get_nowait()
                except queue.Empty:
                    break

            if latest is not None:
                snapshots.append(latest)

        return snapshots

    def stop_all(self) -> None:
        for handle in self._workers.values():
            handle.stop_event.set()

        for handle in self._workers.values():
            handle.process.join(timeout=3.0)

        for worker_id in list(self._workers):
            self._stop_worker(worker_id, already_signaled=True)

    def _stop_worker(self, worker_id: int, already_signaled: bool = False) -> None:
        handle = self._workers.pop(worker_id)

        if not already_signaled:
            handle.stop_event.set()
            handle.process.join(timeout=3.0)

        if handle.process.is_alive():
            handle.process.terminate()
            handle.process.join(timeout=1.0)

        handle.command_queue.close()
        handle.output_queue.close()

    def _first_free_id(self) -> int:
        for worker_id in range(1, MAX_WORKERS + 1):
            if worker_id not in self._workers:
                return worker_id
        raise RuntimeError("No free worker IDs.")


def _put_latest(target_queue: mp.Queue, value: WorkerConfig) -> None:
    try:
        target_queue.put_nowait(value)
        return
    except queue.Full:
        pass

    try:
        target_queue.get_nowait()
    except queue.Empty:
        pass

    try:
        target_queue.put_nowait(value)
    except queue.Full:
        pass
