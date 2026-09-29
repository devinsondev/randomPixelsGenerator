from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from tools.batch_analyzer.models import BatchResult, ScorePair


class NumericItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.UserRole)
        right = other.data(Qt.UserRole)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return float(left) < float(right)
        return super().__lt__(other)


class ResultTable(QTableWidget):
    COLUMNS = (
        "Preview",
        "Файл",
        "Исходник",
        "Real MVP",
        "Real Robust",
        "Shuffled MVP",
        "Shuffled Robust",
        "Random MVP",
        "Random Robust",
    )

    def __init__(self) -> None:
        super().__init__(0, len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setIconSize(QSize(32, 32))
        self.verticalHeader().setDefaultSectionSize(38)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.setSortingEnabled(False)

    def begin_batch(self) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)

    def end_batch(self) -> None:
        self.setSortingEnabled(True)
        self.sortByColumn(4, Qt.DescendingOrder)

    def add_result(self, result: BatchResult, root: Path) -> None:
        row = self.rowCount()
        self.insertRow(row)

        preview_item = QTableWidgetItem()
        preview_item.setIcon(QIcon(_preview_pixmap(result)))
        preview_item.setData(Qt.UserRole, result.real.robust)
        self.setItem(row, 0, preview_item)

        try:
            display_path = result.path.relative_to(root)
        except ValueError:
            display_path = result.path

        file_item = QTableWidgetItem(str(display_path))
        file_item.setToolTip(str(result.path))
        self.setItem(row, 1, file_item)

        self.setItem(
            row,
            2,
            QTableWidgetItem(
                f"{result.source_width}×{result.source_height}"
            ),
        )

        for column, score in (
            (3, result.real),
            (5, result.shuffled),
            (7, result.random),
        ):
            self.setItem(row, column, _score_item(score.mvp, score.mvp_passed))

        for column, score in (
            (4, result.real),
            (6, result.shuffled),
            (8, result.random),
        ):
            self.setItem(
                row,
                column,
                _score_item(score.robust, score.robust_passed),
            )



def _score_item(score: float, passed: bool) -> NumericItem:
    marker = "PASS" if passed else "fail"
    item = NumericItem(f"{score:.2f} {marker}")
    item.setData(Qt.UserRole, float(score))
    return item


def _preview_pixmap(result: BatchResult) -> QPixmap:
    size = result.preview_size
    image = QImage(
        result.preview_rgb,
        size,
        size,
        size * 3,
        QImage.Format_RGB888,
    ).copy()
    return QPixmap.fromImage(image).scaled(
        32,
        32,
        Qt.IgnoreAspectRatio,
        Qt.FastTransformation,
    )
