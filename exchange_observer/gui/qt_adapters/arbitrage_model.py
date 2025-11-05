import pandas as pd

from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex

from exchange_observer.gui.gui_models import FilterMode, FilterSettings


class ArbitrageOpportunitiesModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_data = pd.DataFrame()
        self.filtered_data = pd.DataFrame()
        self.sort_column = -1
        self.sort_order = Qt.SortOrder.AscendingOrder
        self.filter_mode = FilterMode.ALL
        self.whitelist = set()
        self.blacklist = set()

    def set_filter(self, settings: FilterSettings) -> None:
        self.filter_mode = settings.mode
        self.whitelist = set(settings.whitelist)
        self.blacklist = set(settings.blacklist)

        self.layoutAboutToBeChanged.emit()
        self.apply_filter()
        self.re_sort()
        self.layoutChanged.emit()

    def apply_filter(self) -> None:
        if self.raw_data.empty:
            self.filtered_data = self.raw_data.copy()
            return

        if self.filter_mode == FilterMode.WHITELIST:
            mode_mask = self.raw_data["symbol"].isin(self.whitelist)
        elif self.filter_mode == FilterMode.ONLY_BTC:
            mode_mask = self.raw_data["symbol"].str.contains("BTC")
        elif self.filter_mode == FilterMode.ONLY_ETH:
            mode_mask = self.raw_data["symbol"].str.contains("ETH")
        elif self.filter_mode == FilterMode.ONLY_USDT:
            mode_mask = self.raw_data["symbol"].str.contains("USDT")
        else:
            mode_mask = pd.Series(True, index=self.raw_data.index)

        if self.blacklist:
            blacklist_mask = ~self.raw_data["symbol"].isin(self.blacklist)
        else:
            blacklist_mask = pd.Series(True, index=self.raw_data.index)

        final_mask = mode_mask & blacklist_mask
        self.filtered_data = self.raw_data[final_mask].copy()

    def re_sort(self) -> None:
        if self.sort_column != -1 and not self.filtered_data.empty:
            try:
                column_name = self.filtered_data.columns[self.sort_column]
                self.filtered_data.sort_values(
                    by=column_name,
                    ascending=(self.sort_order == Qt.SortOrder.AscendingOrder),
                    inplace=True,
                )
            except IndexError:
                self.sort_column = -1

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self.filtered_data.shape[0]

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self.filtered_data.shape[1]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            value = self.filtered_data.iloc[index.row(), index.column()]
            column_name = self.filtered_data.columns[index.column()]

            if isinstance(value, float):
                if column_name in ["buy_price", "sell_price"]:
                    return f"{value:.8f}"
                if column_name == "profit":
                    return f"{value:.4f}%"
                if "age" in column_name:
                    return f"{value:.2f}s"

            return str(value)

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return str(self.filtered_data.columns[section]).replace("_", " ").title()
        return None

    def sort(self, column: int, order: Qt.SortOrder) -> None:
        self.sort_column = column
        self.sort_order = order
        self.layoutAboutToBeChanged.emit()
        self.re_sort()
        self.layoutChanged.emit()

    def update_data(self, new_opportunities: list[dict]) -> None:
        self.layoutAboutToBeChanged.emit()
        if new_opportunities:
            df = pd.DataFrame(new_opportunities)
            df.rename(columns={"profit_percent": "profit"}, inplace=True)

            self.raw_data = df[
                [
                    "symbol",
                    "buy_exchange",
                    "sell_exchange",
                    "buy_price",
                    "sell_price",
                    "profit",
                    "buy_data_age",
                    "sell_data_age",
                ]
            ].copy()
        else:
            empty_cols = [
                "symbol",
                "buy_exchange",
                "sell_exchange",
                "buy_price",
                "sell_price",
                "profit",
                "buy_data_age",
                "sell_data_age",
            ]
            self.raw_data = pd.DataFrame(columns=empty_cols)

        self.apply_filter()
        self.re_sort()
        self.layoutChanged.emit()
