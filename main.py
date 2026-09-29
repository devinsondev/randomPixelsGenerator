from __future__ import annotations

import multiprocessing as mp
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from lane_widget import LaneWidget
from process_manager import MAX_WORKERS, ProcessManager
from worker_protocol import WorkerConfig, WorkerSnapshot


class RandomImageGenerator(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Random RGB Image Generator")
        self.resize(1450, 900)

        self.manager: ProcessManager | None = None
        self.lanes: dict[int, LaneWidget] = {}
        self.latest: dict[int, WorkerSnapshot] = {}

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(30)
        self.poll_timer.timeout.connect(self._poll_workers)

        self.width_spin = self._int_spin(2, 4096, 64)
        self.height_spin = self._int_spin(2, 4096, 64)
        self.interval_spin = self._int_spin(1, 60_000, 1)
        self.interval_spin.setSuffix(" ms")

        self.mvp_threshold_spin = QDoubleSpinBox()
        self.mvp_threshold_spin.setRange(0.0, 100.0)
        self.mvp_threshold_spin.setDecimals(1)
        self.mvp_threshold_spin.setSingleStep(0.5)
        self.mvp_threshold_spin.setValue(18.0)
        self.mvp_threshold_spin.setSuffix(" / 100")

        self.render_checkbox = QCheckBox("Показывать изображения")
        self.render_checkbox.setChecked(True)

        self.auto_save_checkbox = QCheckBox("Автосохранять прошедшие MVP")
        self.auto_save_checkbox.setChecked(True)

        self.start_button = QPushButton("Старт")
        self.start_button.clicked.connect(self.start_generation)

        self.stop_button = QPushButton("Стоп")
        self.stop_button.clicked.connect(self.stop_generation)
        self.stop_button.setEnabled(False)

        self.add_parallel_button = QPushButton("+ параллель")
        self.add_parallel_button.clicked.connect(self.add_parallel)

        self.remove_parallel_button = QPushButton("− параллель")
        self.remove_parallel_button.clicked.connect(self.remove_parallel)

        self.parallel_label = QLabel("Параллелей: 1 / 16")
        self.summary_label = QLabel("Готово к запуску")
        self.summary_label.setWordWrap(True)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(8)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_host)

        self._build_layout()
        self._create_lane(1)
        self._connect_live_settings()

    @staticmethod
    def _int_spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("Ширина:", self.width_spin)
        form.addRow("Высота:", self.height_spin)
        form.addRow("Интервал:", self.interval_spin)
        form.addRow("Порог MVP:", self.mvp_threshold_spin)

        options = QHBoxLayout()
        options.addWidget(self.render_checkbox)
        options.addWidget(self.auto_save_checkbox)
        options.addStretch(1)

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addSpacing(20)
        controls.addWidget(self.add_parallel_button)
        controls.addWidget(self.remove_parallel_button)
        controls.addWidget(self.parallel_label)
        controls.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(options)
        layout.addLayout(controls)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.scroll, 1)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

    def _connect_live_settings(self) -> None:
        self.width_spin.valueChanged.connect(self._push_config)
        self.height_spin.valueChanged.connect(self._push_config)
        self.interval_spin.valueChanged.connect(self._push_config)
        self.mvp_threshold_spin.valueChanged.connect(self._push_config)
        self.render_checkbox.toggled.connect(self._push_config)
        self.auto_save_checkbox.toggled.connect(self._push_config)

    def _worker_config(self) -> WorkerConfig:
        return WorkerConfig(
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            interval_ms=self.interval_spin.value(),
            mvp_threshold=self.mvp_threshold_spin.value(),
            auto_save=self.auto_save_checkbox.isChecked(),
            send_image=self.render_checkbox.isChecked(),
        )

    def _push_config(self, *_args) -> None:
        if self.manager is not None:
            self.manager.update_config(self._worker_config())

    def start_generation(self) -> None:
        if self.manager is not None:
            return

        try:
            manager = ProcessManager(self._worker_config())
            for _ in range(len(self.lanes)):
                manager.add_worker()
        except Exception as error:
            QMessageBox.critical(self, "Ошибка запуска", str(error))
            return

        self.manager = manager
        self.latest.clear()
        self.poll_timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.summary_label.setText("Генерация запущена")

    def stop_generation(self) -> None:
        if self.manager is None:
            return

        self.poll_timer.stop()
        self.manager.stop_all()
        self.manager = None

        for lane in self.lanes.values():
            lane.set_stopped()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._update_summary()

    def add_parallel(self) -> None:
        if len(self.lanes) >= MAX_WORKERS:
            return

        if self.manager is not None:
            worker_id = self.manager.add_worker()
        else:
            worker_id = self._first_free_lane_id()

        self._create_lane(worker_id)
        self._update_parallel_label()

    def remove_parallel(self) -> None:
        if len(self.lanes) <= 1:
            return

        if self.manager is not None:
            worker_id = self.manager.remove_last_worker()
            if worker_id is None:
                return
        else:
            worker_id = max(self.lanes)

        self._remove_lane(worker_id)
        self._update_parallel_label()
        self._update_summary()

    def _create_lane(self, worker_id: int) -> None:
        lane = LaneWidget(worker_id)
        lane.save_requested.connect(self.save_lane_image)
        self.lanes[worker_id] = lane

        index = worker_id - 1
        row = index // 4
        column = index % 4
        self.grid.addWidget(lane, row, column)
        self._update_parallel_label()

    def _remove_lane(self, worker_id: int) -> None:
        lane = self.lanes.pop(worker_id)
        self.latest.pop(worker_id, None)
        self.grid.removeWidget(lane)
        lane.deleteLater()

    def _first_free_lane_id(self) -> int:
        for worker_id in range(1, MAX_WORKERS + 1):
            if worker_id not in self.lanes:
                return worker_id
        raise RuntimeError("Нет свободного ID параллели.")

    def _update_parallel_label(self) -> None:
        self.parallel_label.setText(
            f"Параллелей: {len(self.lanes)} / {MAX_WORKERS}"
        )
        self.remove_parallel_button.setEnabled(len(self.lanes) > 1)
        self.add_parallel_button.setEnabled(len(self.lanes) < MAX_WORKERS)

    def _poll_workers(self) -> None:
        if self.manager is None:
            return

        for snapshot in self.manager.poll_latest():
            self.latest[snapshot.worker_id] = snapshot
            lane = self.lanes.get(snapshot.worker_id)
            if lane is not None:
                lane.update_snapshot(snapshot)

        self._update_summary()

    def _update_summary(self) -> None:
        if not self.latest:
            self.summary_label.setText(
                f"Параллелей: {len(self.lanes)} | данных пока нет"
            )
            return

        snapshots = [
            self.latest[worker_id]
            for worker_id in self.lanes
            if worker_id in self.latest
        ]
        frames = sum(item.frame_index for item in snapshots)
        fps = sum(item.fps for item in snapshots)
        passed = sum(item.mvp_passed for item in snapshots)
        saved = sum(item.saved for item in snapshots)
        robust_runs = sum(item.robust_runs for item in snapshots)
        robust_candidates = sum(item.robust_candidates for item in snapshots)

        self.summary_label.setText(
            f"Всего кадров: {frames:,} | суммарно: {fps:,.0f} кадр/с | "
            f"MVP прошло: {passed:,} | сохранено: {saved:,} | "
            f"Robust запусков: {robust_runs:,} | "
            f"Robust прошло: {robust_candidates:,}"
        )

    def save_lane_image(self, worker_id: int) -> None:
        lane = self.lanes.get(worker_id)
        if lane is None or lane.current_image is None:
            return

        snapshot = self.latest.get(worker_id)
        frame = snapshot.frame_index if snapshot is not None else 0
        default_name = f"worker_{worker_id:02d}_frame_{frame:09d}.png"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Сохранить кадр параллели #{worker_id}",
            str(Path.cwd() / default_name),
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)",
        )
        if file_path and not lane.current_image.save(file_path):
            QMessageBox.critical(
                self,
                "Ошибка",
                "Не удалось сохранить изображение.",
            )

    def closeEvent(self, event) -> None:
        if self.manager is not None:
            self.poll_timer.stop()
            self.manager.stop_all()
            self.manager = None
        event.accept()


def main() -> None:
    mp.freeze_support()
    app = QApplication(sys.argv)
    window = RandomImageGenerator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
