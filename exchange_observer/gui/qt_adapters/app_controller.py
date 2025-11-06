import logging

from concurrent.futures import Future

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from exchange_observer import ExchangeObserverApp
from exchange_observer.core import Exchange, ArbitrageOpportunity
from exchange_observer.utils import AsyncWorker
from exchange_observer.gui.gui_models import AppSettings
from .arbitrage_model import ArbitrageOpportunitiesModel


class AppController(QObject):
    status_updated = pyqtSignal(str)
    app_stopped = pyqtSignal()
    finished = pyqtSignal()
    exchange_connected = pyqtSignal(str)
    exchange_disconnected = pyqtSignal(str)
    exchange_error = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.worker = AsyncWorker()
        self.app: ExchangeObserverApp | None = None
        self.is_shutting_down = False

        self.opportunities_model = ArbitrageOpportunitiesModel()
        self.worker.start()

    def arbitrage_callback(self, opportunities: list[ArbitrageOpportunity]) -> None:
        self.opportunities_model.update_data([opp.to_dict() for opp in opportunities])

    def on_exchange_connected(self, exchange: Exchange) -> None:
        self.exchange_connected.emit(exchange.value)

    def on_exchange_disconnected(self, exchange: Exchange) -> None:
        self.exchange_disconnected.emit(exchange.value)

    def on_exchange_error(self, exchange: Exchange, error: str) -> None:
        self.exchange_error.emit(exchange.value, error)

    @pyqtSlot(dict)
    def start_app(self, config: AppSettings) -> None:
        self.logger.info("Start app command received with config: %s", config)
        self.status_updated.emit("Запуск...")

        try:
            exchanges = [Exchange(name) for name, checked in config.exchanges.items() if checked]
            min_profit = config.min_arbitrage_profit_percent
            arbitrage_check_interval_seconds = config.arbitrage_check_interval_seconds
            max_data_age_seconds = config.max_data_age_seconds

            self.app = ExchangeObserverApp(
                exchanges_to_monitor=exchanges,
                arbitrage_check_interval_seconds=arbitrage_check_interval_seconds,
                min_arbitrage_profit_percent=min_profit,
                max_data_age_seconds=max_data_age_seconds,
                arbitrage_callback=self.arbitrage_callback,
                connected_callback=self.on_exchange_connected,
                disconnected_callback=self.on_exchange_disconnected,
                error_callback=self.on_exchange_error,
            )

            self.worker.start_task(self.app)
            self.status_updated.emit("Приложение запущено")
            self.logger.info("ExchangeObserverApp task started in worker")

        except Exception as e:
            self.logger.exception("Failed to start ExchangeObserverApp")
            self.status_updated.emit(f"Ошибка при запуске: {e}")

    @pyqtSlot()
    def stop_app(self) -> None:
        self.logger.info("Stop app command received")
        self.status_updated.emit("Остановка...")

        if self.app:
            future = self.worker.stop_task(self.app)
            if future:
                future.add_done_callback(self.on_app_stopped)
        else:
            self.app_stopped.emit()
            if self.is_shutting_down:
                self.finalize_shutdown()

    def on_app_stopped(self, future: Future) -> None:
        try:
            future.result()
            self.logger.info("ExchangeObserverApp stop task finished successfully")
        except Exception as e:
            self.logger.error(f"Error during ExchangeObserverApp stop: {e}")
            self.status_updated.emit(f"Ошибка при остановке: {e}")

        self.app = None
        self.status_updated.emit("Приложение остановлено")
        self.logger.info("ExchangeObserverApp stop task finished")
        self.app_stopped.emit()

    def cleanup(self) -> None:
        self.logger.info("Cleanup initiated")
        self.is_shutting_down = True
        if self.app:
            self.stop_app()
        else:
            self.finalize_shutdown()

    def finalize_shutdown(self) -> None:
        self.logger.info("Performing final cleanup...")
        self.worker.stop_loop()
        self.worker.join()
        self.finished.emit()
        self.logger.info("Cleanup finished")
