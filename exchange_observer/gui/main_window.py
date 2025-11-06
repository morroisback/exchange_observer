import sys

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent

from exchange_observer.core import Exchange
from exchange_observer.gui.gui_models import FilterMode, FilterSettings, AppSettings
from .qt_adapters import AppController


class MainWindow(QMainWindow):
    filter_settings_changed = pyqtSignal(FilterSettings)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Exchange Observer")
        self.setGeometry(25, 0, 1400, 900)

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

        exchanges_panel = self.create_exchanges_panel()
        settings_panel = self.create_settings_panel()
        self.table_view = self.create_table_view()

        self.main_layout.addWidget(exchanges_panel, 0, 0, 2, 1)
        self.main_layout.addWidget(settings_panel, 0, 1)
        self.main_layout.addWidget(self.table_view, 1, 1)

        self.main_layout.setColumnStretch(0, 1)
        self.main_layout.setColumnStretch(1, 7)
        self.main_layout.setRowStretch(0, 1)
        self.main_layout.setRowStretch(1, 3)

    def create_exchanges_panel(self) -> QWidget:
        panel = QWidget()
        main_exchanges_layout = QHBoxLayout(panel)
        main_exchanges_layout.setSpacing(10)
        main_exchanges_layout.setContentsMargins(0, 0, 0, 0)

        self.exchanges_group = QGroupBox("Биржи")
        self.exchanges_group.setAlignment(Qt.AlignmentFlag.AlignTop)
        exchanges_offset_layout = QHBoxLayout(self.exchanges_group)
        exchanges_layout = QVBoxLayout()

        self.exchange_checkboxes: dict[str, QCheckBox] = {}
        for exchange in Exchange:
            if exchange != Exchange.NONE:
                checkbox = QCheckBox(exchange.value.title())
                self.exchange_checkboxes[exchange.value] = checkbox
                exchanges_layout.addWidget(checkbox)
        exchanges_layout.addStretch()
        exchanges_offset_layout.addLayout(exchanges_layout)

        main_exchanges_layout.addWidget(self.exchanges_group)
        return panel

    def create_settings_panel(self) -> QWidget:
        panel = QWidget()
        main_settings_layout = QHBoxLayout(panel)
        main_settings_layout.setSpacing(10)
        main_settings_layout.setContentsMargins(0, 0, 0, 0)

        self.filters_group = self.create_filters_group()

        self.params_group = QGroupBox("Параметры")
        params_offset_layout = QHBoxLayout(self.params_group)
        form_layout = QFormLayout()
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
        params_offset_layout.addLayout(form_layout)

        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(5)
        self.start_btn = QPushButton("Старт")
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setEnabled(False)
        buttons_layout.addWidget(self.start_btn)
        buttons_layout.addWidget(self.stop_btn)
        buttons_layout.addStretch()

        main_settings_layout.addWidget(self.filters_group, 4)
        main_settings_layout.addWidget(self.params_group, 2)
        main_settings_layout.addLayout(buttons_layout, 1)

        return panel

    def create_filters_group(self) -> QGroupBox:
        filters_group = QGroupBox("Фильтры символов")
        main_filters_layout = QHBoxLayout(filters_group)

        mode_layout = QVBoxLayout()
        self.filter_mode_all_radio = QRadioButton("Все символы")
        self.filter_mode_all_radio.setChecked(True)
        self.filter_mode_whitelist_radio = QRadioButton("Белый список")
        self.filter_mode_btc_radio = QRadioButton("Только с BTC")
        self.filter_mode_eth_radio = QRadioButton("Только с ETH")
        self.filter_mode_usdt_radio = QRadioButton("Только с USDT")

        mode_layout.addWidget(self.filter_mode_all_radio)
        mode_layout.addWidget(self.filter_mode_whitelist_radio)
        mode_layout.addWidget(self.filter_mode_btc_radio)
        mode_layout.addWidget(self.filter_mode_eth_radio)
        mode_layout.addWidget(self.filter_mode_usdt_radio)
        mode_layout.addStretch()

        lists_layout = QHBoxLayout()
        whitelist_group = self.create_list_management_group("Белый список")
        blacklist_group = self.create_list_management_group("Черный список")
        lists_layout.addWidget(whitelist_group)
        lists_layout.addWidget(blacklist_group)

        main_filters_layout.addLayout(mode_layout)
        main_filters_layout.addLayout(lists_layout)

        main_filters_layout.setStretch(0, 1)
        main_filters_layout.setStretch(1, 3)

        return filters_group

    def create_list_management_group(self, title: str) -> QGroupBox:
        group_box = QGroupBox(title)
        layout = QVBoxLayout(group_box)

        list_widget = QListWidget()

        buttons_layout = QHBoxLayout()
        add_button = QPushButton("Добавить")
        remove_button = QPushButton("Удалить")
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(remove_button)

        if "Белый" in title:
            self.whitelist_list = list_widget
            self.whitelist_add_btn = add_button
            self.whitelist_remove_btn = remove_button
        else:
            self.blacklist_list = list_widget
            self.blacklist_add_btn = add_button
            self.blacklist_remove_btn = remove_button

        layout.addWidget(list_widget)
        layout.addLayout(buttons_layout)

        return group_box

    def create_table_view(self) -> QTableView:
        table_view = QTableView()
        table_view.setModel(self.controller.opportunities_model)
        table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_view.setAlternatingRowColors(True)
        table_view.setSortingEnabled(True)
        return table_view

    def connect_signals(self) -> None:
        self.start_btn.clicked.connect(self.on_start_clicked)
        self.stop_btn.clicked.connect(self.on_stop_clicked)

        self.whitelist_add_btn.clicked.connect(self.on_whitelist_add_clicked)
        self.blacklist_add_btn.clicked.connect(self.on_blacklist_add_clicked)

        self.whitelist_remove_btn.clicked.connect(self.on_whitelist_remove_clicked)
        self.blacklist_remove_btn.clicked.connect(self.on_blacklist_remove_clicked)

        self.filter_mode_all_radio.clicked.connect(self.emit_filter_settings)
        self.filter_mode_whitelist_radio.clicked.connect(self.emit_filter_settings)
        self.filter_mode_btc_radio.clicked.connect(self.emit_filter_settings)
        self.filter_mode_eth_radio.clicked.connect(self.emit_filter_settings)
        self.filter_mode_usdt_radio.clicked.connect(self.emit_filter_settings)
        self.whitelist_list.model().rowsInserted.connect(self.emit_filter_settings)
        self.whitelist_list.model().rowsRemoved.connect(self.emit_filter_settings)
        self.blacklist_list.model().rowsInserted.connect(self.emit_filter_settings)
        self.blacklist_list.model().rowsRemoved.connect(self.emit_filter_settings)

        self.filter_settings_changed.connect(self.controller.opportunities_model.set_filter)

        self.controller.status_updated.connect(self.statusBar().showMessage)
        self.controller.app_stopped.connect(self.on_app_stopped_ui_update)
        self.controller.finished.connect(self.on_cleanup_finished)

    def emit_filter_settings(self) -> None:
        if self.filter_mode_all_radio.isChecked():
            mode = FilterMode.ALL
        elif self.filter_mode_whitelist_radio.isChecked():
            mode = FilterMode.WHITELIST
        elif self.filter_mode_btc_radio.isChecked():
            mode = FilterMode.ONLY_BTC
        elif self.filter_mode_eth_radio.isChecked():
            mode = FilterMode.ONLY_ETH
        elif self.filter_mode_usdt_radio.isChecked():
            mode = FilterMode.ONLY_USDT
        else:
            mode = FilterMode.ALL

        whitelist = [self.whitelist_list.item(i).text() for i in range(self.whitelist_list.count())]
        blacklist = [self.blacklist_list.item(i).text() for i in range(self.blacklist_list.count())]

        settings = FilterSettings(mode, whitelist, blacklist)
        self.filter_settings_changed.emit(settings)

    def on_whitelist_add_clicked(self) -> None:
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Добавить символ в белый список")
        dialog.setLabelText("Символ:")
        dialog.resize(300, 100)
        ok = dialog.exec()
        text = dialog.textValue().upper()

        if ok and text:
            existing_items = [self.whitelist_list.item(i).text() for i in range(self.whitelist_list.count())]
            if text not in existing_items:
                self.whitelist_list.addItem(text)
            else:
                QMessageBox.warning(self, "Дубликат", f"Символ '{text}' уже есть в списке.")

    def on_blacklist_add_clicked(self) -> None:
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Добавить символ в черный список")
        dialog.setLabelText("Символ:")
        dialog.resize(300, 100)
        ok = dialog.exec()
        text = dialog.textValue().upper()

        if ok and text:
            existing_items = [self.blacklist_list.item(i).text() for i in range(self.blacklist_list.count())]
            if text not in existing_items:
                self.blacklist_list.addItem(text)
            else:
                QMessageBox.warning(self, "Дубликат", f"Символ '{text}' уже есть в списке.")

    def on_whitelist_remove_clicked(self) -> None:
        for item in self.whitelist_list.selectedItems():
            self.whitelist_list.takeItem(self.whitelist_list.row(item))

    def on_blacklist_remove_clicked(self) -> None:
        for item in self.blacklist_list.selectedItems():
            self.blacklist_list.takeItem(self.blacklist_list.row(item))

    def set_controls_enabled(self, enabled: bool) -> None:
        self.exchanges_group.setEnabled(enabled)
        self.params_group.setEnabled(enabled)

    def on_start_clicked(self) -> None:
        exchanges_config = {name: cb.isChecked() for name, cb in self.exchange_checkboxes.items()}

        if sum(exchanges_config.values()) < 2:
            QMessageBox.warning(self, "Недостаточно бирж", "Для арбитража необходимо выбрать хотя бы 2 биржи.")
            return

        config = AppSettings(
            exchanges_config,
            self.update_frequency_spinbox.value(),
            self.min_profit_spinbox.value() / 100,
            self.data_age_spinbox.value(),
        )

        self.controller.start_app(config)
        self.set_controls_enabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def on_stop_clicked(self) -> None:
        self.controller.stop_app()
        self.stop_btn.setEnabled(False)

    def on_app_stopped_ui_update(self) -> None:
        self.controller.opportunities_model.update_data([])
        if self.is_closing:
            self.controller.finalize_shutdown()
        else:
            self.set_controls_enabled(True)
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def on_cleanup_finished(self) -> None:
        self.cleanup_finished = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_closing:
            if self.cleanup_finished:
                event.accept()
            else:
                event.ignore()
            return

        self.is_closing = True
        self.statusBar().showMessage("Завершение работы... Пожалуйста, подождите")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.set_controls_enabled(False)

        self.controller.cleanup()
        event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
