from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from worker_protocol import WorkerSnapshot


class LaneWidget(QFrame):
    save_requested = Signal(int)

    def __init__(self, worker_id: int) -> None:
        super().__init__()
        self.worker_id = worker_id
        self._current_image: QImage | None = None

        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(260)

        self.title_label = QLabel(f"Параллель #{worker_id}")
        self.title_label.setStyleSheet("font-weight: 600;")

        self.state_label = QLabel("Ожидание запуска")
        self.state_label.setWordWrap(True)

        self.mvp_label = QLabel("MVP: —")
        self.mvp_label.setWordWrap(True)

        self.threshold_label = QLabel("Порог: —")
        self.threshold_label.setWordWrap(True)

        self.robust_label = QLabel("Robust: —")
        self.robust_label.setWordWrap(True)

        self.top_label = QLabel("Top-10: —")
        self.top_label.setWordWrap(True)

        self.image_label = QLabel("Нет кадра")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(220, 220)
        self.image_label.setStyleSheet(
            "QLabel { background: #151515; color: #888; border: 1px solid #444; }"
        )

        self.save_button = QPushButton("Сохранить этот кадр")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(
            lambda: self.save_requested.emit(self.worker_id)
        )

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.state_label)
        layout.addWidget(self.mvp_label)
        layout.addWidget(self.threshold_label)
        layout.addWidget(self.robust_label)
        layout.addWidget(self.top_label)
        layout.addWidget(self.image_label, 1)
        layout.addWidget(self.save_button)

    @property
    def current_image(self) -> QImage | None:
        return self._current_image

    def update_snapshot(self, snapshot: WorkerSnapshot) -> None:
        self.state_label.setText(
            f"Кадров: {snapshot.frame_index:,} | "
            f"{snapshot.fps:,.1f} кадр/с | "
            f"{snapshot.width}×{snapshot.height} | "
            f"MVP PNG: {snapshot.saved_mvp} | "
            f"Robust PNG: {snapshot.saved_robust}"
        )

        self.mvp_label.setText(
            f"MVP: {snapshot.current_mvp:.2f}/{snapshot.mvp_threshold:.2f} | "
            f"avg {snapshot.average_mvp:.2f} | "
            f"max {snapshot.max_mvp:.2f} на #{snapshot.max_mvp_frame:,} | "
            f"прошло: {snapshot.mvp_passed}"
        )

        self.threshold_label.setText(self._threshold_text(snapshot))

        robust = "пропущен"
        if snapshot.robust_score is not None:
            robust = (
                f"{snapshot.robust_score:.2f}/"
                f"{snapshot.robust_threshold:.1f}"
            )
        self.robust_label.setText(
            f"Robust: {robust} | запусков: {snapshot.robust_runs} | "
            f"прошло: {snapshot.robust_candidates}"
        )

        top = ", ".join(
            f"{score:.2f} (#{frame:,})"
            for frame, score in snapshot.top_scores
        )
        self.top_label.setText(f"Top-10 MVP: {top or '—'}")

        if snapshot.error:
            self.state_label.setText(
                f"{self.state_label.text()} | ОШИБКА: {snapshot.error}"
            )

        if snapshot.image_rgb is not None:
            image = QImage(
                snapshot.image_rgb,
                snapshot.width,
                snapshot.height,
                snapshot.width * 3,
                QImage.Format_RGB888,
            ).copy()
            self._current_image = image
            self.save_button.setEnabled(True)
            self._render_image()

    @staticmethod
    def _threshold_text(snapshot: WorkerSnapshot) -> str:
        if snapshot.threshold_mode == "fixed":
            return f"Порог: fixed {snapshot.mvp_threshold:.2f}"

        if snapshot.threshold_mode == "auto_warmup":
            return (
                f"Порог: auto top {snapshot.top_percent:g}% | "
                f"прогрев {snapshot.percentile_samples:,}/"
                f"{snapshot.threshold_warmup:,} | "
                f"пока fixed {snapshot.mvp_threshold:.2f}"
            )

        return (
            f"Порог: auto top {snapshot.top_percent:g}% | "
            f"эффективный {snapshot.mvp_threshold:.2f} | "
            f"выборка {snapshot.percentile_samples:,}"
        )

    def set_stopped(self) -> None:
        self.state_label.setText(f"{self.state_label.text()} | остановлено")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_image()

    def _render_image(self) -> None:
        if self._current_image is None:
            return

        pixmap = QPixmap.fromImage(self._current_image)
        self.image_label.setPixmap(
            pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
        )
