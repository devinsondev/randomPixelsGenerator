from __future__ import annotations

import os

# Keep one Python process close to one CPU core instead of nesting BLAS threads.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import queue
import sqlite3
import time
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from pathlib import Path

from analysis_pipeline import AnalysisPipeline, PipelineResult
from candidate_store import CandidateStore
from experiment_log import FrameLogger
from percentile_threshold import RunningPercentileThreshold
from random_frame import derive_frame_seed, generate_rgb_frame
from session_stats import SessionStats
from worker_protocol import WorkerConfig, WorkerSnapshot

_UI_PUBLISH_INTERVAL_S = 0.05


def run_generator_worker(
    worker_id: int,
    worker_seed: int,
    session_dir: Path,
    initial_config: WorkerConfig,
    command_queue: Queue,
    output_queue: Queue,
    stop_event: Event,
) -> None:
    """Generate, analyze and optionally record frames inside one child process."""
    config = initial_config.validated()
    pipeline = AnalysisPipeline()
    tracker = RunningPercentileThreshold(
        warmup_frames=config.threshold_warmup
    )
    store = CandidateStore(session_dir / "candidates", worker_id)
    stats = SessionStats()

    logger, last_error = _open_logger_if_enabled(
        enabled=config.sqlite_logging,
        session_dir=session_dir,
        worker_id=worker_id,
        worker_seed=worker_seed,
    )
    sqlite_setting = config.sqlite_logging

    frame_index = 0
    started_at = time.perf_counter()
    last_publish_at = 0.0
    previous_shape = (config.width, config.height)

    try:
        while not stop_event.is_set():
            loop_started = time.perf_counter()
            config = _latest_config(command_queue, config)

            if config.sqlite_logging != sqlite_setting:
                logger, toggle_error = _apply_sqlite_setting(
                    logger=logger,
                    enabled=config.sqlite_logging,
                    session_dir=session_dir,
                    worker_id=worker_id,
                    worker_seed=worker_seed,
                )
                sqlite_setting = config.sqlite_logging
                if toggle_error is not None:
                    last_error = toggle_error
                elif not config.sqlite_logging:
                    last_error = None

            current_shape = (config.width, config.height)
            if (
                current_shape != previous_shape
                or config.threshold_warmup != tracker.warmup_frames
            ):
                tracker.reset(warmup_frames=config.threshold_warmup)
                previous_shape = current_shape

            effective_threshold, threshold_mode = _effective_threshold(
                config=config,
                tracker=tracker,
            )
            if pipeline.mvp_threshold != effective_threshold:
                pipeline.set_mvp_threshold(effective_threshold)

            frame_index += 1
            frame_seed = derive_frame_seed(worker_seed, frame_index)
            pixels = generate_rgb_frame(
                width=config.width,
                height=config.height,
                frame_seed=frame_seed,
            )
            analysis = pipeline.analyze(pixels)
            tracker.observe(analysis.mvp.score)

            record_error = _record_analysis(
                stats=stats,
                store=store,
                logger=logger,
                worker_seed=worker_seed,
                frame_seed=frame_seed,
                frame_index=frame_index,
                pixels=pixels,
                analysis=analysis,
                auto_save=config.auto_save,
                threshold_mode=threshold_mode,
                top_percent=config.top_percent,
            )
            if record_error is not None:
                last_error = record_error
                if record_error.startswith("SQLite:"):
                    logger = _close_logger(logger)

            now = time.perf_counter()
            should_publish = (
                now - last_publish_at >= _UI_PUBLISH_INTERVAL_S
                or analysis.mvp.is_interesting
            )
            if should_publish:
                _put_latest(
                    output_queue,
                    _build_snapshot(
                        worker_id=worker_id,
                        frame_index=frame_index,
                        pixels=pixels,
                        analysis=analysis,
                        stats=stats,
                        config=config,
                        tracker=tracker,
                        threshold_mode=threshold_mode,
                        elapsed=max(now - started_at, 1e-9),
                        sqlite_active=logger is not None,
                        error=last_error,
                    ),
                )
                last_publish_at = now

            elapsed = time.perf_counter() - loop_started
            remaining = config.interval_ms / 1000.0 - elapsed
            if remaining > 0:
                stop_event.wait(remaining)
    finally:
        _close_logger(logger)


def _open_logger_if_enabled(
    *,
    enabled: bool,
    session_dir: Path,
    worker_id: int,
    worker_seed: int,
) -> tuple[FrameLogger | None, str | None]:
    if not enabled:
        return None, None

    try:
        logger = FrameLogger(
            session_dir / "workers" / f"worker_{worker_id:02d}.sqlite3",
            worker_id=worker_id,
            worker_seed=worker_seed,
        )
        return logger, None
    except sqlite3.Error as error:
        return None, f"SQLite: {error}"


def _apply_sqlite_setting(
    *,
    logger: FrameLogger | None,
    enabled: bool,
    session_dir: Path,
    worker_id: int,
    worker_seed: int,
) -> tuple[FrameLogger | None, str | None]:
    if not enabled:
        _close_logger(logger)
        return None, None

    if logger is not None:
        return logger, None

    return _open_logger_if_enabled(
        enabled=True,
        session_dir=session_dir,
        worker_id=worker_id,
        worker_seed=worker_seed,
    )


def _close_logger(logger: FrameLogger | None) -> None:
    if logger is None:
        return None

    try:
        logger.close()
    except sqlite3.Error:
        pass

    return None


def _effective_threshold(
    config: WorkerConfig,
    tracker: RunningPercentileThreshold,
) -> tuple[float, str]:
    if not config.auto_threshold:
        return config.mvp_threshold, "fixed"

    threshold = tracker.threshold(
        top_percent=config.top_percent,
        fallback=config.mvp_threshold,
    )
    mode = "auto" if tracker.is_ready else "auto_warmup"
    return threshold, mode


def _record_analysis(
    *,
    stats: SessionStats,
    store: CandidateStore,
    logger: FrameLogger | None,
    worker_seed: int,
    frame_seed: int,
    frame_index: int,
    pixels,
    analysis: PipelineResult,
    auto_save: bool,
    threshold_mode: str,
    top_percent: float,
) -> str | None:
    stats.mvp.record(frame_index, analysis.mvp.score)
    error: str | None = None

    if logger is not None:
        try:
            logger.record(
                frame_index=frame_index,
                frame_seed=frame_seed,
                width=pixels.shape[1],
                height=pixels.shape[0],
                analysis=analysis,
                threshold_mode=threshold_mode,
                top_percent=top_percent,
            )
        except sqlite3.Error as exc:
            error = f"SQLite: {exc}"

    if analysis.mvp.is_interesting:
        stats.mvp_passed += 1
        if auto_save:
            try:
                saved = store.save(
                    pixels,
                    frame_index=frame_index,
                    worker_seed=worker_seed,
                    frame_seed=frame_seed,
                    analysis=analysis,
                    threshold_mode=threshold_mode,
                    top_percent=top_percent,
                )
                stats.saved_mvp += 1
                if saved.robust_png is not None:
                    stats.saved_robust += 1
            except OSError as exc:
                error = f"автосохранение: {exc}"

    if analysis.robust is not None:
        stats.robust_runs += 1
    if analysis.is_candidate:
        stats.robust_candidates += 1

    return error


def _build_snapshot(
    *,
    worker_id: int,
    frame_index: int,
    pixels,
    analysis: PipelineResult,
    stats: SessionStats,
    config: WorkerConfig,
    tracker: RunningPercentileThreshold,
    threshold_mode: str,
    elapsed: float,
    sqlite_active: bool,
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
        threshold_mode=threshold_mode,
        top_percent=config.top_percent,
        percentile_samples=tracker.count,
        threshold_warmup=config.threshold_warmup,
        mvp_passed=stats.mvp_passed,
        robust_score=robust_score,
        robust_threshold=robust_threshold,
        robust_runs=stats.robust_runs,
        robust_candidates=stats.robust_candidates,
        saved_mvp=stats.saved_mvp,
        saved_robust=stats.saved_robust,
        sqlite_logging=sqlite_active,
        top_scores=tuple(
            (item.frame_index, item.score)
            for item in stats.mvp.top
        ),
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
