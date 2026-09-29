from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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

from resizer import ResizeFilter, ResizeMode, resize_image


class ClipboardResizerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Clipboard Image Resizer")
        self.resize(1000, 720)

        self.source_image: QImage | None = None
        self.output_image: QImage | None = None

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 8192)
        self.width_spin.setValue(64)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 8192)
        self.height_spin.setValue(64)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Растянуть", ResizeMode.STRETCH)
        self.mode_combo.addItem("Вписать + чёрные поля", ResizeMode.FIT)
        self.mode_combo.addItem("Заполнить + crop по центру", ResizeMode.COVER)
        self.mode_combo.setCurrentIndex(2)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Nearest (видны пиксели)", ResizeFilter.NEAREST)
        self.filter_combo.addItem("Smooth", ResizeFilter.SMOOTH)
        self.filter_combo.setCurrentIndex(0)

        self.paste_button = QPushButton("Взять картинку из буфера")
        self.paste_button.clicked.connect(self.load_from_clipboard)

        self.resize_button = QPushButton("Изменить размер")
        self.resize_button.clicked.connect(self.resize_current)
        self.resize_button.setEnabled(False)

        self.copy_button = QPushButton("Скопировать результат")
        self.copy_button.clicked.connect(self.copy_output)
        self.copy_button.setEnabled(False)

        self.save_button = QPushButton("Сохранить PNG")
        self.save_button.clicked.connect(self.save_output)
        self.save_button.setEnabled(False)

        self.source_info = QLabel("Исходник: —")
        self.output_info = QLabel("Результат: —")

        self.source_preview = self._preview_label("Исходное изображение")
        self.output_preview = self._preview_label("Результат")

        form = QFormLayout()
        form.addRow("Ширина:", self.width_spin)
        form.addRow("Высота:", self.height_spin)
        form.addRow("Режим:", self.mode_combo)
        form.addRow("Фильтр:", self.filter_combo)

        buttons = QHBoxLayout()
        buttons.addWidget(self.paste_button)
        buttons.addWidget(self.resize_button)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.save_button)

        previews = QHBoxLayout()

        source_box = QVBoxLayout()
        source_box.addWidget(self.source_info)
        source_box.addWidget(self.source_preview, 1)

        output_box = QVBoxLayout()
        output_box.addWidget(self.output_info)
        output_box.addWidget(self.output_preview, 1)

        previews.addLayout(source_box, 1)
        previews.addLayout(output_box, 1)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addLayout(previews, 1)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.width_spin.valueChanged.connect(self._resize_if_loaded)
        self.height_spin.valueChanged.connect(self._resize_if_loaded)
        self.mode_combo.currentIndexChanged.connect(self._resize_if_loaded)
        self.filter_combo.currentIndexChanged.connect(self._resize_if_loaded)

    @staticmethod
    def _preview_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumSize(320, 320)
        label.setStyleSheet(
            "QLabel { background: #151515; color: #888; border: 1px solid #444; }"
        )
        return label

    def load_from_clipboard(self) -> None:
        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()

        if image.isNull():
            QMessageBox.warning(
                self,
                "Буфер пуст",
                "В буфере обмена нет изображения.",
            )
            return

        self.source_image = image.convertToFormat(QImage.Format_RGB888)
        self.source_info.setText(
            f"Исходник: {self.source_image.width()}×{self.source_image.height()}"
        )
        self.resize_button.setEnabled(True)
        self._render_source()
        self.resize_current()

    def resize_current(self) -> None:
        if self.source_image is None:
            return

        mode = self.mode_combo.currentData()
        resize_filter = self.filter_combo.currentData()

        self.output_image = resize_image(
            self.source_image,
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            mode=mode,
            resize_filter=resize_filter,
        )

        self.output_info.setText(
            f"Результат: {self.output_image.width()}×"
            f"{self.output_image.height()}"
        )
        self.copy_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self._render_output()

    def _resize_if_loaded(self, *_args) -> None:
        if self.source_image is not None:
            self.resize_current()

    def copy_output(self) -> None:
        if self.output_image is None:
            return
        QGuiApplication.clipboard().setImage(self.output_image)

    def save_output(self) -> None:
        if self.output_image is None:
            return

        default_name = (
            f"resized_{self.output_image.width()}x"
            f"{self.output_image.height()}.png"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить изображение",
            str(Path.cwd() / default_name),
            "PNG (*.png)",
        )
        if path and not self.output_image.save(path, "PNG"):
            QMessageBox.critical(
                self,
                "Ошибка",
                "Не удалось сохранить PNG.",
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_source()
        self._render_output()

    def _render_source(self) -> None:
        if self.source_image is None:
            return
        self._render(self.source_preview, self.source_image)

    def _render_output(self) -> None:
        if self.output_image is None:
            return
        self._render(self.output_preview, self.output_image)

    @staticmethod
    def _render(label: QLabel, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        label.setPixmap(
            pixmap.scaled(
                label.size(),
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
        )


def main() -> None:
    app = QApplication(sys.argv)
    window = ClipboardResizerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
