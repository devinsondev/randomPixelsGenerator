import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from analysis_pipeline import AnalysisPipeline, PipelineResult


class RandomImageGenerator(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Random RGB Image Generator")
        self.resize(900, 700)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.generate_image)

        self.analysis_pipeline = AnalysisPipeline()
        self.current_image: QImage | None = None
        self.generated_count = 0
        self.robust_analysis_count = 0
        self.candidate_count = 0

        self.width_spin = QSpinBox()
        self.width_spin.setRange(2, 4096)
        self.width_spin.setValue(64)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(2, 4096)
        self.height_spin.setValue(64)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60_000)
        self.interval_spin.setValue(250)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.valueChanged.connect(self.update_timer_interval)

        self.render_checkbox = QCheckBox("Показывать изображение")
        self.render_checkbox.setChecked(True)

        self.start_button = QPushButton("Старт")
        self.start_button.clicked.connect(self.start_generation)

        self.stop_button = QPushButton("Стоп")
        self.stop_button.clicked.connect(self.stop_generation)
        self.stop_button.setEnabled(False)

        self.generate_once_button = QPushButton("Сгенерировать 1 раз")
        self.generate_once_button.clicked.connect(self.generate_image)

        self.save_button = QPushButton("Сохранить текущую")
        self.save_button.clicked.connect(self.save_current_image)
        self.save_button.setEnabled(False)

        self.image_label = QLabel("Нажми «Старт» или «Сгенерировать 1 раз»")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(500, 400)
        self.image_label.setStyleSheet(
            "QLabel { background: #181818; color: #d0d0d0; border: 1px solid #444; }"
        )

        self.stats_label = QLabel("Сгенерировано: 0")
        self.analysis_label = QLabel(
            "MVP: — | Robust: — | Robust запусков: 0 | Кандидатов: 0"
        )

        form = QFormLayout()
        form.addRow("Ширина:", self.width_spin)
        form.addRow("Высота:", self.height_spin)
        form.addRow("Интервал:", self.interval_spin)

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.generate_once_button)
        controls.addWidget(self.save_button)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.render_checkbox)
        layout.addLayout(controls)
        layout.addWidget(self.stats_label)
        layout.addWidget(self.analysis_label)
        layout.addWidget(self.image_label, 1)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

    def update_timer_interval(self, value: int):
        if self.timer.isActive():
            self.timer.setInterval(value)

    def start_generation(self):
        self.timer.start(self.interval_spin.value())
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.generate_image()

    def stop_generation(self):
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def generate_image(self):
        width = self.width_spin.value()
        height = self.height_spin.value()

        pixels = np.random.randint(
            0,
            256,
            size=(height, width, 3),
            dtype=np.uint8,
        )

        analysis = self.analysis_pipeline.analyze(pixels)

        qimage = QImage(
            pixels.data,
            width,
            height,
            width * 3,
            QImage.Format_RGB888,
        ).copy()

        self.current_image = qimage
        self.generated_count += 1
        self._record_analysis(analysis)
        self._update_stats(width, height, analysis)
        self.save_button.setEnabled(True)

        if self.render_checkbox.isChecked():
            self.show_current_image()

    def _record_analysis(self, analysis: PipelineResult):
        if analysis.robust is not None:
            self.robust_analysis_count += 1
        if analysis.is_candidate:
            self.candidate_count += 1

    def _update_stats(
        self,
        width: int,
        height: int,
        analysis: PipelineResult,
    ):
        self.stats_label.setText(
            f"Сгенерировано: {self.generated_count} | "
            f"Размер: {width}×{height}"
        )

        mvp = analysis.mvp
        robust_text = "пропущен"
        if analysis.robust is not None:
            robust = analysis.robust
            robust_text = f"{robust.score:.1f}/{robust.threshold:.1f}"

        candidate_text = " | КАНДИДАТ" if analysis.is_candidate else ""
        self.analysis_label.setText(
            f"MVP: {mvp.score:.1f}/{mvp.threshold:.1f} | "
            f"Robust: {robust_text} | "
            f"Robust запусков: {self.robust_analysis_count} | "
            f"Кандидатов: {self.candidate_count}"
            f"{candidate_text}"
        )

    def show_current_image(self):
        if self.current_image is None:
            return

        pixmap = QPixmap.fromImage(self.current_image)
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.render_checkbox.isChecked():
            self.show_current_image()

    def save_current_image(self):
        if self.current_image is None:
            return

        default_name = (
            f"random_{self.current_image.width()}x"
            f"{self.current_image.height()}_{self.generated_count}.png"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить изображение",
            str(Path.cwd() / default_name),
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)",
        )

        if not file_path:
            return

        if not self.current_image.save(file_path):
            QMessageBox.critical(
                self,
                "Ошибка",
                "Не удалось сохранить изображение.",
            )


def main():
    app = QApplication(sys.argv)
    window = RandomImageGenerator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
