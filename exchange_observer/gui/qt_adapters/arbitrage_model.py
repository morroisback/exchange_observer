import pandas as pd

from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex


class ArbitrageOpportunitiesModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: pd.DataFrame = pd.DataFrame()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self.data.shape[0]

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self.data.shape[1]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            value = self.data.iloc[index.row(), index.column()]
            column_name = self.data.columns[index.column()]

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
            return str(self.data.columns[section]).replace("_", " ").title()
        return None

    def sort(self, column: int, order: Qt.SortOrder) -> None:
        try:
            column_name = self.data.columns[column]
            self.layoutAboutToBeChanged.emit()
            self.data.sort_values(by=column_name, ascending=(order == Qt.SortOrder.AscendingOrder), inplace=True)
            self.layoutChanged.emit()
        except IndexError:
            pass

    def update_data(self, new_opportunities: list[dict]) -> None:
        self.layoutAboutToBeChanged.emit()
        if new_opportunities:
            df = pd.DataFrame(new_opportunities)
            df.rename(columns={"profit_percent": "profit"}, inplace=True)

            self.data = df[
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
            ]
        else:
            self.data = pd.DataFrame(
                columns=self.data.columns
                if not self.data.empty
                else [
                    "symbol",
                    "buy_exchange",
                    "sell_exchange",
                    "buy_price",
                    "sell_price",
                    "profit",
                    "buy_data_age",
                    "sell_data_age",
                ]
            )
        self.layoutChanged.emit()
