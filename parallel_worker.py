from __future__ import annotations

import os

# Prevent one worker process from secretly creating its own BLAS thread farm.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import queue
import time
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event

import numpy as np

from analysis_pipeline import AnalysisPipeline, PipelineResult
from candidate_store import CandidateStore
from session_stats import SessionStats
from worker_protocol import WorkerConfig, WorkerSnapshot

_UI_PUBLISH_INTERVAL_S = 0.05


def run_generator_worker(
    worker_id: int,
    initial_config: WorkerConfig,
    command_queue: Queue,
    output_queue: Queue,
    stop_event: Event,
) -> None:
    """Long-running generator/analyzer loop executed in a child process."""
    config = initial_config.validated()
    pipeline = AnalysisPipeline()
    pipeline.set_mvp_threshold(config.mvp_threshold)
    store = CandidateStore()
    stats = SessionStats()
    rng = np.random.default_rng()

    frame_index = 0
    started_at = time.perf_counter()
    last_publish_at = 0.0
    error: str | None = None

    while not stop_event.is_set():
        loop_started = time.perf_counter()
        config = _latest_config(command_queue, config)
        if pipeline.mvp_threshold != config.mvp_threshold:
            pipeline.set_mvp_threshold(config.mvp_threshold)

        pixels = rng.integers(
            0,
            256,
            size=(config.height, config.width, 3),
            dtype=np.uint8,
        )
        analysis = pipeline.analyze(pixels)
        frame_index += 1

        _record_analysis(
            stats=stats,
            store=store,
            worker_id=worker_id,
            frame_index=frame_index,
            pixels=pixels,
            analysis=analysis,
            auto_save=config.auto_save,
        )

        now = time.perf_counter()
        should_publish = (
            now - last_publish_at >= _UI_PUBLISH_INTERVAL_S
            or analysis.mvp.is_interesting
        )
        if should_publish:
            snapshot = _build_snapshot(
                worker_id=worker_id,
                frame_index=frame_index,
                pixels=pixels,
                analysis=analysis,
                stats=stats,
                config=config,
                elapsed=max(now - started_at, 1e-9),
                error=error,
            )
            _put_latest(output_queue, snapshot)
            last_publish_at = now

        elapsed = time.perf_counter() - loop_started
        remaining = config.interval_ms / 1000.0 - elapsed
        if remaining > 0:
            stop_event.wait(remaining)


def _record_analysis(
    stats: SessionStats,
    store: CandidateStore,
    worker_id: int,
    frame_index: int,
    pixels: np.ndarray,
    analysis: PipelineResult,
    auto_save: bool,
) -> None:
    stats.mvp.record(frame_index, analysis.mvp.score)

    if analysis.mvp.is_interesting:
        stats.mvp_passed += 1
        if auto_save:
            worker_store = CandidateStore(
                store_root(worker_id)
            )
            worker_store.save(pixels, frame_index, analysis)
            stats.saved += 1

    if analysis.robust is not None:
        stats.robust_runs += 1
    if analysis.is_candidate:
        stats.robust_candidates += 1


def store_root(worker_id: int):
    from pathlib import Path

    return Path("candidates") / f"worker_{worker_id:02d}"


def _build_snapshot(
    worker_id: int,
    frame_index: int,
    pixels: np.ndarray,
    analysis: PipelineResult,
    stats: SessionStats,
    config: WorkerConfig,
    elapsed: float,
    error: str | None,
) -> WorkerSnapshot:
    maximum = stats.mvp.maximum
    max_score = maximum.score if maximum is not None else 0.0
    max_frame = maximum.frame_index if maximum is not None else 0

    robust_score = None
    robust_threshold = None
    if analysis.robust is not None:
        robust_score = analysis.robust.score
        robust_threshold = analysis.robust.threshold

    top_scores = tuple(
        (item.frame_index, item.score)
        for item in stats.mvp.top
    )

    return WorkerSnapshot(
        worker_id=worker_id,
        frame_index=frame_index,
        width=config.width,
        height=config.height,
        fps=frame_index / elapsed,
        current_mvp=analysis.mvp.score,
        average_mvp=stats.mvp.average,
        max_mvp=max_score,
        max_mvp_frame=max_frame,
        mvp_threshold=analysis.mvp.threshold,
        mvp_passed=stats.mvp_passed,
        robust_score=robust_score,
        robust_threshold=robust_threshold,
        robust_runs=stats.robust_runs,
        robust_candidates=stats.robust_candidates,
        saved=stats.saved,
        top_scores=top_scores,
        image_rgb=pixels.tobytes(order="C") if config.send_image else None,
        error=error,
    )


def _latest_config(command_queue: Queue, current: WorkerConfig) -> WorkerConfig:
    latest = current
    while True:
        try:
            latest = command_queue.get_nowait()
        except queue.Empty:
            return latest.validated()


def _put_latest(output_queue: Queue, snapshot: WorkerSnapshot) -> None:
    try:
        output_queue.put_nowait(snapshot)
        return
    except queue.Full:
        pass

    try:
        output_queue.get_nowait()
    except queue.Empty:
        pass

    try:
        output_queue.put_nowait(snapshot)
    except queue.Full:
        pass
