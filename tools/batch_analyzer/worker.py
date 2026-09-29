from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from tools.batch_analyzer.engine import BatchImageAnalyzer, discover_images
from tools.batch_analyzer.models import BatchConfig, BatchResult, BatchSummary


class BatchWorker(QObject):
    result_ready = Signal(object)
    progress = Signal(int, int)
    failed_file = Signal(str, str)
    completed = Signal(object)
    fatal_error = Signal(str)

    def __init__(self, config: BatchConfig) -> None:
        super().__init__()
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            config = self._config.validated()
            paths = discover_images(config)
            analyzer = BatchImageAnalyzer()
        except Exception as error:
            self.fatal_error.emit(str(error))
            return

        totals = _ScoreTotals()
        failed = 0
        analyzed = 0
        thread = QThread.currentThread()

        for index, path in enumerate(paths, start=1):
            if thread.isInterruptionRequested():
                self.completed.emit(
                    totals.summary(
                        discovered=len(paths),
                        analyzed=analyzed,
                        failed=failed,
                        cancelled=True,
                    )
                )
                return

            try:
                result = analyzer.analyze_file(path, config)
            except Exception as error:
                failed += 1
                self.failed_file.emit(str(path), str(error))
            else:
                analyzed += 1
                totals.add(result)
                self.result_ready.emit(result)

            self.progress.emit(index, len(paths))

        self.completed.emit(
            totals.summary(
                discovered=len(paths),
                analyzed=analyzed,
                failed=failed,
                cancelled=False,
            )
        )


class _ScoreTotals:
    def __init__(self) -> None:
        self.count = 0
        self.real_mvp = 0.0
        self.real_robust = 0.0
        self.shuffled_mvp = 0.0
        self.shuffled_robust = 0.0
        self.random_mvp = 0.0
        self.random_robust = 0.0

    def add(self, result: BatchResult) -> None:
        self.count += 1
        self.real_mvp += result.real.mvp
        self.real_robust += result.real.robust
        self.shuffled_mvp += result.shuffled.mvp
        self.shuffled_robust += result.shuffled.robust
        self.random_mvp += result.random.mvp
        self.random_robust += result.random.robust

    def summary(
        self,
        *,
        discovered: int,
        analyzed: int,
        failed: int,
        cancelled: bool,
    ) -> BatchSummary:
        divisor = max(self.count, 1)
        return BatchSummary(
            discovered=discovered,
            analyzed=analyzed,
            failed=failed,
            cancelled=cancelled,
            real_mvp_average=self.real_mvp / divisor,
            real_robust_average=self.real_robust / divisor,
            shuffled_mvp_average=self.shuffled_mvp / divisor,
            shuffled_robust_average=self.shuffled_robust / divisor,
            random_mvp_average=self.random_mvp / divisor,
            random_robust_average=self.random_robust / divisor,
        )
