import sys

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QTableView,
    QHeaderView,
    QCheckBox,
    QDoubleSpinBox,
    QSpinBox,
    QLabel,
    QStatusBar,
    QGroupBox,
    QFormLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent

from exchange_observer.core import Exchange
from .qt_adapters.app_controller import AppController


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Exchange Observer")
        self.setGeometry(100, 100, 1200, 800)

        self.controller = AppController(self)
        self.is_closing = False
        self.cleanup_finished = False

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.create_ui()
        self.setStatusBar(QStatusBar(self))
        self.connect_signals()

        self.controller.opportunities_model.update_data([])

    def create_ui(self) -> None:
        self.main_layout = QGridLayout(self.central_widget)

        exchanges_group = self.create_exchanges_panel()
        settings_panel = self.create_settings_panel()
        self.table_view = self.create_table_view()

        self.main_layout.addWidget(exchanges_group, 0, 0, 2, 1)
        self.main_layout.addWidget(settings_panel, 0, 1)
        self.main_layout.addWidget(self.table_view, 1, 1)

        self.main_layout.setColumnStretch(0, 1)
        self.main_layout.setColumnStretch(1, 5)
        self.main_layout.setRowStretch(0, 1)
        self.main_layout.setRowStretch(1, 5)

    def create_exchanges_panel(self) -> QWidget:
        panel = QWidget()
        main_exchanges_layout = QVBoxLayout(panel)
        main_exchanges_layout.setSpacing(10)
        main_exchanges_layout.setContentsMargins(0, 0, 0, 0)

        self.exchanges_group = QGroupBox("Биржи")
        self.exchanges_group.setAlignment(Qt.AlignmentFlag.AlignTop)
        exchanges_layout = QVBoxLayout()
        self.exchange_checkboxes: dict[str, QCheckBox] = {}
        for exchange in Exchange:
            if exchange != Exchange.NONE:
                checkbox = QCheckBox(exchange.value.title())
                self.exchange_checkboxes[exchange.value] = checkbox
                exchanges_layout.addWidget(checkbox)
        exchanges_layout.addStretch()
        self.exchanges_group.setLayout(exchanges_layout)

        main_exchanges_layout.addWidget(self.exchanges_group)
        return panel

    def create_settings_panel(self) -> QWidget:
        panel = QWidget()
        main_settings_layout = QHBoxLayout(panel)
        main_settings_layout.setSpacing(10)
        main_settings_layout.setContentsMargins(0, 0, 0, 0)

        self.filters_group = QGroupBox("Фильтры символов")
        filters_layout = QHBoxLayout(self.filters_group)
        filters_layout.addWidget(QLabel("В разработке..."))
        filters_layout.addWidget(QLabel("В разработке..."))
        filters_layout.addWidget(QLabel("В разработке..."))
        filters_layout.addStretch()

        self.params_group = QGroupBox("Параметры")
        form_layout = QFormLayout(self.params_group)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.update_frequency_spinbox = QSpinBox()
        self.update_frequency_spinbox.setRange(1, 3600)
        self.update_frequency_spinbox.setValue(10)

        self.min_profit_spinbox = QDoubleSpinBox()
        self.min_profit_spinbox.setRange(0.1, 100.0)
        self.min_profit_spinbox.setSingleStep(0.1)
        self.min_profit_spinbox.setValue(1)

        self.data_age_spinbox = QSpinBox()
        self.data_age_spinbox.setRange(1, 3600)
        self.data_age_spinbox.setValue(60)

        spinbox_width = 60
        self.update_frequency_spinbox.setFixedWidth(spinbox_width)
        self.min_profit_spinbox.setFixedWidth(spinbox_width)
        self.data_age_spinbox.setFixedWidth(spinbox_width)

        form_layout.addRow("Частота обновления (сек):", self.update_frequency_spinbox)
        form_layout.addRow("Мин. порог прибыли (%):", self.min_profit_spinbox)
        form_layout.addRow("Длительность истории (сек):", self.data_age_spinbox)

        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(5)
        self.start_button = QPushButton("Старт")
        self.stop_button = QPushButton("Стоп")
        self.stop_button.setEnabled(False)
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addStretch()

        main_settings_layout.addWidget(self.filters_group, 4)
        main_settings_layout.addWidget(self.params_group, 2)
        main_settings_layout.addLayout(buttons_layout, 1)

        return panel

    def create_table_view(self) -> QTableView:
        table_view = QTableView()
        table_view.setModel(self.controller.opportunities_model)
        table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_view.setAlternatingRowColors(True)
        table_view.setSortingEnabled(True)
        return table_view

    def connect_signals(self) -> None:
        self.start_button.clicked.connect(self.on_start_clicked)
        self.stop_button.clicked.connect(self.on_stop_clicked)

        self.controller.status_updated.connect(self.statusBar().showMessage)
        self.controller.app_stopped.connect(self.on_app_stopped_ui_update)
        self.controller.finished.connect(self.on_cleanup_finished)

    def set_controls_enabled(self, enabled: bool) -> None:
        self.exchanges_group.setEnabled(enabled)
        self.filters_group.setEnabled(enabled)
        self.params_group.setEnabled(enabled)

    def on_start_clicked(self) -> None:
        exchanges_config = {name: cb.isChecked() for name, cb in self.exchange_checkboxes.items()}

        if not any(exchanges_config.values()):
            QMessageBox.warning(self, "Нет выбора", "Пожалуйста, выберите хотя бы одну биржу.")
            return

        config = {
            "exchanges": exchanges_config,
            "arbitrage_check_interval_seconds": self.update_frequency_spinbox.value(),
            "min_profit": self.min_profit_spinbox.value() / 100,
            "max_data_age_seconds": self.data_age_spinbox.value(),
        }
        self.controller.start_app(config)
        self.set_controls_enabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def on_stop_clicked(self) -> None:
        self.controller.stop_app()
        self.stop_button.setEnabled(False)

    def on_app_stopped_ui_update(self) -> None:
        self.controller.opportunities_model.update_data([])
        if self.is_closing:
            self.controller.finalize_shutdown()
        else:
            self.set_controls_enabled(True)
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def on_cleanup_finished(self) -> None:
        self.cleanup_finished = True
        self.close()

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if self.is_closing:
            if self.cleanup_finished:
                event.accept()
            else:
                event.ignore()
            return

        self.is_closing = True
        self.statusBar().showMessage("Завершение работы... Пожалуйста, подождите.")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.set_controls_enabled(False)

        self.controller.cleanup()
        event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
