from __future__ import annotations

import multiprocessing as mp
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from control_panel import ControlPanel
from lane_widget import LaneWidget
from process_manager import MAX_WORKERS, ProcessManager
from worker_protocol import WorkerSnapshot


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

        self.controls = ControlPanel()
        self.controls.config_changed.connect(self._push_config)
        self.controls.start_requested.connect(self.start_generation)
        self.controls.stop_requested.connect(self.stop_generation)
        self.controls.add_requested.connect(self.add_parallel)
        self.controls.remove_requested.connect(self.remove_parallel)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(8)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_host)

        layout = QVBoxLayout()
        layout.addWidget(self.controls)
        layout.addWidget(self.scroll, 1)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        self._create_lane(1)

    def _push_config(self) -> None:
        if self.manager is not None:
            try:
                self.manager.update_config(self.controls.config())
            except ValueError as error:
                QMessageBox.warning(self, "Некорректная настройка", str(error))

    def start_generation(self) -> None:
        if self.manager is not None:
            return

        try:
            manager = ProcessManager(self.controls.config())
            for _ in range(len(self.lanes)):
                manager.add_worker()
        except Exception as error:
            if "manager" in locals():
                manager.stop_all()
            QMessageBox.critical(self, "Ошибка запуска", str(error))
            return

        self.manager = manager
        self.latest.clear()
        self.poll_timer.start()
        self.controls.set_running(True)
        self.controls.set_session_path(str(manager.session_dir.resolve()))
        self.controls.summary_label.setText(
            "Генерация запущена; SQLite пишет каждый кадр пакетами."
        )

    def stop_generation(self) -> None:
        if self.manager is None:
            return

        self.poll_timer.stop()
        self.manager.stop_all()
        self.manager = None

        for lane in self.lanes.values():
            lane.set_stopped()

        self.controls.set_running(False)
        self._update_summary()

    def add_parallel(self) -> None:
        if len(self.lanes) >= MAX_WORKERS:
            return

        if self.manager is not None:
            try:
                worker_id = self.manager.add_worker()
            except Exception as error:
                QMessageBox.critical(
                    self,
                    "Ошибка запуска параллели",
                    str(error),
                )
                return
        else:
            worker_id = self._first_free_lane_id()

        self._create_lane(worker_id)

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
        self._update_summary()

    def _create_lane(self, worker_id: int) -> None:
        lane = LaneWidget(worker_id)
        lane.save_requested.connect(self.save_lane_image)
        self.lanes[worker_id] = lane

        index = worker_id - 1
        self.grid.addWidget(lane, index // 4, index % 4)
        self.controls.set_parallel_count(len(self.lanes))

    def _remove_lane(self, worker_id: int) -> None:
        lane = self.lanes.pop(worker_id)
        self.latest.pop(worker_id, None)
        self.grid.removeWidget(lane)
        lane.deleteLater()
        self.controls.set_parallel_count(len(self.lanes))

    def _first_free_lane_id(self) -> int:
        for worker_id in range(1, MAX_WORKERS + 1):
            if worker_id not in self.lanes:
                return worker_id
        raise RuntimeError("Нет свободного ID параллели.")

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
        snapshots = [
            self.latest[worker_id]
            for worker_id in self.lanes
            if worker_id in self.latest
        ]
        if not snapshots:
            self.controls.summary_label.setText(
                f"Параллелей: {len(self.lanes)} | данных пока нет"
            )
            return

        frames = sum(item.frame_index for item in snapshots)
        fps = sum(item.fps for item in snapshots)
        mvp_passed = sum(item.mvp_passed for item in snapshots)
        saved_mvp = sum(item.saved_mvp for item in snapshots)
        saved_robust = sum(item.saved_robust for item in snapshots)
        robust_runs = sum(item.robust_runs for item in snapshots)
        robust_passed = sum(item.robust_candidates for item in snapshots)

        self.controls.summary_label.setText(
            f"Всего кадров: {frames:,} | {fps:,.0f} кадр/с | "
            f"MVP прошло: {mvp_passed:,} | "
            f"MVP PNG: {saved_mvp:,} | Robust PNG: {saved_robust:,} | "
            f"Robust запусков: {robust_runs:,} | "
            f"Robust прошло: {robust_passed:,}"
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
