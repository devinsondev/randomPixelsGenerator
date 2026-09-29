from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tools.batch_analyzer.models import BatchConfig, BatchSummary
from tools.batch_analyzer.result_table import ResultTable
from tools.batch_analyzer.worker import BatchWorker
from tools.clipboard_resizer.resizer import ResizeFilter, ResizeMode


class BatchAnalyzerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Image Batch Sanity Analyzer")
        self.resize(1500, 850)

        self._thread: QThread | None = None
        self._worker: BatchWorker | None = None
        self._active_config: BatchConfig | None = None

        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_button = QPushButton("Выбрать папку")
        self.folder_button.clicked.connect(self.choose_folder)

        self.width_spin = self._spin(2, 4096, 64)
        self.height_spin = self._spin(2, 4096, 64)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Cover + crop", ResizeMode.COVER)
        self.mode_combo.addItem("Fit + поля", ResizeMode.FIT)
        self.mode_combo.addItem("Stretch", ResizeMode.STRETCH)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Nearest", ResizeFilter.NEAREST)
        self.filter_combo.addItem("Smooth", ResizeFilter.SMOOTH)

        self.preview_combo = QComboBox()
        self.preview_combo.addItem("16×16", 16)
        self.preview_combo.addItem("8×8", 8)

        self.recursive_checkbox = QCheckBox("Сканировать подпапки")
        self.recursive_checkbox.setChecked(True)

        self.start_button = QPushButton("Сканировать и анализировать")
        self.start_button.clicked.connect(self.start_batch)

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.cancel_batch)
        self.cancel_button.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        self.status_label = QLabel("Выбери папку с изображениями.")
        self.status_label.setWordWrap(True)

        self.summary_label = QLabel("Сводка: —")
        self.summary_label.setWordWrap(True)

        self.table = ResultTable()

        self._build_layout()

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _build_layout(self) -> None:
        folder = QHBoxLayout()
        folder.addWidget(self.folder_edit, 1)
        folder.addWidget(self.folder_button)

        form = QFormLayout()
        form.addRow("Папка:", folder)
        form.addRow("Ширина анализа:", self.width_spin)
        form.addRow("Высота анализа:", self.height_spin)
        form.addRow("Resize mode:", self.mode_combo)
        form.addRow("Resize filter:", self.filter_combo)
        form.addRow("Preview:", self.preview_combo)

        controls = QHBoxLayout()
        controls.addWidget(self.recursive_checkbox)
        controls.addStretch(1)
        controls.addWidget(self.start_button)
        controls.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(controls)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

    def choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Выбрать папку с изображениями",
            self.folder_edit.text() or str(Path.cwd()),
        )
        if directory:
            self.folder_edit.setText(directory)

    def _config(self) -> BatchConfig:
        return BatchConfig(
            root=Path(self.folder_edit.text()),
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            preview_size=int(self.preview_combo.currentData()),
            resize_mode=self.mode_combo.currentData(),
            resize_filter=self.filter_combo.currentData(),
            recursive=self.recursive_checkbox.isChecked(),
        ).validated()

    def start_batch(self) -> None:
        if self._thread is not None:
            return

        try:
            config = self._config()
        except Exception as error:
            QMessageBox.warning(self, "Настройки", str(error))
            return

        self.table.clear_results()
        self.progress.setRange(0, 0)
        self.summary_label.setText("Сводка: считается...")
        self.status_label.setText("Поиск изображений...")
        self._active_config = config
        self._set_running(True)

        thread = QThread(self)
        worker = BatchWorker(config)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.result_ready.connect(self._on_result)
        worker.progress.connect(self._on_progress)
        worker.failed_file.connect(self._on_failed_file)
        worker.completed.connect(self._on_completed)
        worker.completed.connect(thread.quit)
        worker.fatal_error.connect(self._on_fatal_error)
        worker.fatal_error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)

        self._thread = thread
        self._worker = worker
        thread.start()

    def cancel_batch(self) -> None:
        if self._thread is not None:
            self._thread.requestInterruption()
            self.status_label.setText(
                "Отмена запрошена; завершается текущая картинка..."
            )

    def _on_result(self, result) -> None:
        if self._active_config is None:
            return
        self.table.add_result(result, self._active_config.root)

    def _on_progress(self, current: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(current)
        self.status_label.setText(
            f"Обработано {current:,} / {total:,} | "
            f"в таблице {self.table.rowCount():,}"
        )

    def _on_failed_file(self, path: str, error: str) -> None:
        self.status_label.setToolTip(
            f"Последняя ошибка:\n{path}\n{error}"
        )

    def _on_completed(self, summary: BatchSummary) -> None:
        state = "ОТМЕНЕНО" if summary.cancelled else "ГОТОВО"
        self.status_label.setText(
            f"{state}: найдено {summary.discovered:,}, "
            f"проанализировано {summary.analyzed:,}, "
            f"ошибок {summary.failed:,}"
        )
        self.summary_label.setText(_format_summary(summary))

    def _on_fatal_error(self, message: str) -> None:
        self.status_label.setText(f"Ошибка: {message}")
        QMessageBox.critical(self, "Batch analyzer", message)

    def _thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        self._worker = None
        self._set_running(False)

        if thread is not None:
            thread.deleteLater()

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.folder_button.setEnabled(not running)

    def closeEvent(self, event) -> None:
        if self._thread is not None:
            self._thread.requestInterruption()
            self._thread.quit()
            self._thread.wait(5_000)
        event.accept()


def _format_summary(summary: BatchSummary) -> str:
    return (
        "Средние score | "
        f"Real: MVP {summary.real_mvp_average:.2f}, "
        f"Robust {summary.real_robust_average:.2f} | "
        f"Shuffled: MVP {summary.shuffled_mvp_average:.2f}, "
        f"Robust {summary.shuffled_robust_average:.2f} | "
        f"Random: MVP {summary.random_mvp_average:.2f}, "
        f"Robust {summary.random_robust_average:.2f}"
    )


def main() -> None:
    app = QApplication(sys.argv)
    window = BatchAnalyzerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
