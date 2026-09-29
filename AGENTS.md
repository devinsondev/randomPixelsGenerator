# AGENTS.md

## Project goal

Build a fast random-pixel image generator and a procedural pipeline that detects
images with unusually strong spatial structure. The analyzer detects structure,
not semantic meaning. A later vision model may inspect only the rare candidates.

## Architecture rules

1. Keep generation, UI, analysis, persistence, and future VLM integration in
   separate modules. No module may become the place where "everything happens".
2. Hard limit: **377 physical lines per hand-written source file**. Target
   250 lines or fewer. If a file approaches the limit, split by responsibility
   before adding more behavior.
3. No god classes. A class should have one primary reason to change. Prefer
   small pure functions for mathematical operations.
4. No circular imports. Dependency direction should remain simple:
   UI -> application/service layer -> analyzers/generator -> shared models.
5. Analyzer code must not import PySide6. Pass NumPy RGB arrays into analyzers.
   UI conversion belongs at the UI boundary.
6. The generator must not know how images are scored or saved.
7. Do not duplicate metric implementations between analyzers. Shared primitives
   belong in a small common module; scoring policy belongs in each analyzer.
8. Avoid hidden global mutable state. Randomness must be explicit or seeded when
   deterministic behavior matters.
9. Do not add a dependency when NumPy or the standard library can implement the
   feature clearly and efficiently.

## Analyzer contract

- Input: C-compatible numpy.ndarray, shape (height, width, 3), dtype uint8,
  RGB channel order.
- Output: AnalysisResult.
- score is always in [0, 100].
- A higher score means "more procedurally structured / less like independently
  shuffled pixels". It does **not** mean "more meaningful".
- Thresholds are configuration, not universal truths. Tune them from collected
  score distributions.
- The MVP analyzer is the cheap first pass and may run on every generated image.
- The robust analyzer is the slower second pass and is intended for candidates
  that survive the MVP threshold; during calibration it is fine to log both.
- Robust comparisons should preserve the original pixel/color distribution when
  possible, so the score measures spatial organization instead of merely palette.
- Keep robust analysis deterministic for a given image and configuration.

## Performance rules

- Vectorize image math with NumPy. Never iterate Python-side over individual
  pixels in a hot path.
- Avoid unnecessary array copies. Copy only when ownership/contiguity requires it.
- Do not serialize images to disk just to analyze them.
- Benchmark before micro-optimizing.
- The UI thread must remain responsive. If robust analysis becomes noticeable,
  move it to a worker thread/process rather than calling processEvents() loops.
- Future batch mode should be able to disable rendering completely.

## Quality rules

- Use type hints on public functions and methods.
- Validate public boundaries and fail with specific errors.
- No bare except, silent exception swallowing, or magic fallback behavior.
- Prefer descriptive metric names and explicit units.
- Comments explain why, invariants, or non-obvious math; do not narrate syntax.
- Keep functions focused. As a guideline, refactor functions that exceed roughly
  40-60 lines unless the algorithm is clearer as one unit.
- Use dataclasses for stable data contracts.
- New scoring logic must be reproducible and testable without the GUI.

## Tests

- Every new analyzer metric needs at least one deterministic synthetic test.
- Keep a fixed-seed white-noise sample as a baseline.
- Include synthetic structured patterns: gradients, stripes, grids, blobs, lines,
  and later saved real candidates such as the observed "web" patterns.
- Tests should verify ordering/discrimination, not brittle exact floating values,
  unless the exact value is part of the contract.
- Bug fixes require a regression test when practical.
- Before committing, run:
  - python -m unittest discover -s tests
  - python -m compileall .

## Repository hygiene

- Do not commit .venv, generated images, caches, IDE metadata, or benchmark
  dumps unless intentionally curated as test fixtures.
- Generated candidate images should live under a gitignored output directory.
- Keep README usage examples current when public APIs or startup commands change.
- Commit messages should describe one coherent change.

## Current pipeline

random RGB image
  -> MvpAnalyzer (cheap, runtime-configurable threshold)
  -> if MVP passes: optional auto-save to candidates/
  -> if MVP passes: RobustAnalyzer (shuffled-control comparison)
  -> if Robust passes: mark as robust candidate / future VLM inspection

This ordering is intentional: reject obvious white noise cheaply, spend more CPU
only on anomalous candidates, and reserve any future VLM calls for the tiny tail.


## Multiprocessing rules

- CPU-bound generation and analysis use processes, not Python threads.
- Maximum interactive worker count is 16 unless a benchmark justifies changing it.
- Every worker owns its RNG, AnalysisPipeline, SessionStats, and candidate directory.
- Workers never touch Qt objects. Only the main process owns PySide6 widgets.
- IPC queues must be bounded. Prefer dropping stale preview snapshots over blocking
  a generator worker.
- Generation speed and UI refresh speed are separate concerns. Publish previews at
  a human-visible rate; never ship every generated frame through IPC.
- Runtime settings are distributed as immutable WorkerConfig values.
- On Windows the application must remain safe with multiprocessing spawn and
  freeze_support(); never put process-spawning side effects at import time.
- Numerical libraries inside each worker should stay single-threaded to avoid
  process x BLAS-thread oversubscription.
- Candidate paths must be worker-specific so simultaneous workers cannot overwrite
  each other's output.


## Experiment integrity rules

- Every generated frame must have a deterministic frame_seed derived from the
  persisted worker_seed and frame_id. Do not change the derivation algorithm
  silently; treat it as experiment format.
- Every analyzed frame must be logged to the worker SQLite database. Candidate
  images are a convenience subset, never the source of truth for statistics.
- Keep one SQLite database per worker and batch writes. Do not make 16 workers
  contend on one SQLite writer.
- Candidate PNG files require JSON sidecars containing seeds, frame_id, dimensions,
  analyzer scores, thresholds, all metric values, and an RGB pixel hash.
- Maintain separate MVP and Robust candidate directories. Robust passes may exist
  in both stages intentionally.
- Percentile thresholds must be based only on prior observations for the current
  frame size. Reset calibration when dimensions or warmup policy changes.
- During percentile warmup use the configured fixed threshold; never pretend the
  percentile estimate is calibrated before the minimum sample count.
- CSV is an offline export format. Do not add per-frame live CSV writes to the hot
  path when the SQLite journal already contains the data.
- Runtime errors that disable SQLite logging must be visible in the worker UI;
  never silently continue while claiming the experiment is fully recorded.
