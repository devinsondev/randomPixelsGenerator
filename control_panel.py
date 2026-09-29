from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from process_manager import MAX_WORKERS
from worker_protocol import WorkerConfig


class ControlPanel(QWidget):
    """Shared runtime settings and top-level generator controls."""

    config_changed = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    add_requested = Signal()
    remove_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.width_spin = self._int_spin(2, 4096, 64)
        self.height_spin = self._int_spin(2, 4096, 64)
        self.interval_spin = self._int_spin(1, 60_000, 1)
        self.interval_spin.setSuffix(" ms")

        self.mvp_threshold_spin = QDoubleSpinBox()
        self.mvp_threshold_spin.setRange(0.0, 100.0)
        self.mvp_threshold_spin.setDecimals(2)
        self.mvp_threshold_spin.setSingleStep(0.25)
        self.mvp_threshold_spin.setValue(18.0)
        self.mvp_threshold_spin.setSuffix(" / 100")

        self.auto_threshold_checkbox = QCheckBox(
            "Автопорог по percentile"
        )
        self.auto_threshold_checkbox.setChecked(True)

        self.top_percent_spin = QDoubleSpinBox()
        self.top_percent_spin.setRange(0.0001, 50.0)
        self.top_percent_spin.setDecimals(4)
        self.top_percent_spin.setSingleStep(0.01)
        self.top_percent_spin.setValue(0.01)
        self.top_percent_spin.setSuffix(" %")

        self.warmup_spin = self._int_spin(100, 100_000_000, 10_000)
        self.warmup_spin.setSingleStep(1_000)

        self.render_checkbox = QCheckBox("Показывать изображения")
        self.render_checkbox.setChecked(True)

        self.auto_save_checkbox = QCheckBox(
            "Автосохранять прошедшие MVP"
        )
        self.auto_save_checkbox.setChecked(True)

        self.start_button = QPushButton("Старт")
        self.stop_button = QPushButton("Стоп")
        self.stop_button.setEnabled(False)
        self.add_button = QPushButton("+ параллель")
        self.remove_button = QPushButton("− параллель")

        self.parallel_label = QLabel(f"Параллелей: 1 / {MAX_WORKERS}")
        self.summary_label = QLabel("Готово к запуску")
        self.summary_label.setWordWrap(True)
        self.session_label = QLabel("Эксперимент: —")
        self.session_label.setWordWrap(True)

        self._build_layout()
        self._connect_signals()
        self.set_parallel_count(1)

    @staticmethod
    def _int_spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def config(self) -> WorkerConfig:
        return WorkerConfig(
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            interval_ms=self.interval_spin.value(),
            mvp_threshold=self.mvp_threshold_spin.value(),
            auto_threshold=self.auto_threshold_checkbox.isChecked(),
            top_percent=self.top_percent_spin.value(),
            threshold_warmup=self.warmup_spin.value(),
            auto_save=self.auto_save_checkbox.isChecked(),
            send_image=self.render_checkbox.isChecked(),
        )

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def set_parallel_count(self, count: int) -> None:
        self.parallel_label.setText(
            f"Параллелей: {count} / {MAX_WORKERS}"
        )
        self.remove_button.setEnabled(count > 1)
        self.add_button.setEnabled(count < MAX_WORKERS)

    def set_session_path(self, path: str | None) -> None:
        self.session_label.setText(
            f"Эксперимент: {path}" if path else "Эксперимент: —"
        )

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("Ширина:", self.width_spin)
        form.addRow("Высота:", self.height_spin)
        form.addRow("Интервал:", self.interval_spin)
        form.addRow("Порог MVP (fixed/warmup):", self.mvp_threshold_spin)
        form.addRow("Top percentile:", self.top_percent_spin)
        form.addRow("Прогрев кадров/worker:", self.warmup_spin)

        options = QHBoxLayout()
        options.addWidget(self.auto_threshold_checkbox)
        options.addWidget(self.render_checkbox)
        options.addWidget(self.auto_save_checkbox)
        options.addStretch(1)

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addSpacing(20)
        controls.addWidget(self.add_button)
        controls.addWidget(self.remove_button)
        controls.addWidget(self.parallel_label)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addLayout(options)
        layout.addLayout(controls)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.session_label)

    def _connect_signals(self) -> None:
        settings = (
            self.width_spin,
            self.height_spin,
            self.interval_spin,
            self.mvp_threshold_spin,
            self.top_percent_spin,
            self.warmup_spin,
        )
        for widget in settings:
            widget.valueChanged.connect(
                lambda _value: self.config_changed.emit()
            )

        self.auto_threshold_checkbox.toggled.connect(
            lambda _checked: self.config_changed.emit()
        )
        self.render_checkbox.toggled.connect(
            lambda _checked: self.config_changed.emit()
        )
        self.auto_save_checkbox.toggled.connect(
            lambda _checked: self.config_changed.emit()
        )

        self.start_button.clicked.connect(self.start_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.add_button.clicked.connect(self.add_requested.emit)
        self.remove_button.clicked.connect(self.remove_requested.emit)
