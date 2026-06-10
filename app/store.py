from datetime import date
from typing import Dict, List, Optional

from app.config import DEFAULT_HOLIDAYS
from app.models import (
    Order, ProductionLine, WorkOrder, MoldInfo, ShiftDefinition,
    Priority, CustomerImportance, MoldStatus, WorkerShift, OrderStatus
)


class MemoryStore:
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.lines: Dict[str, ProductionLine] = {}
        self.holidays: List[date] = list(DEFAULT_HOLIDAYS)
        self.molds: Dict[str, MoldInfo] = {}
        self.shifts: Dict[str, ShiftDefinition] = {}
        self.scheduled_work_orders: List[WorkOrder] = []
        self.last_schedule_time: Optional[str] = None
        self._init_default_data()

    def _init_default_data(self):
        self.shifts["白班"] = ShiftDefinition(
            shift_name="白班", start_hour=8, end_hour=16
        )
        self.shifts["夜班"] = ShiftDefinition(
            shift_name="夜班", start_hour=16, end_hour=24
        )

        self.molds["M001"] = MoldInfo(
            mold_code="M001", mold_name="模具A",
            compatible_products=["P001", "P002"], setup_minutes=120
        )
        self.molds["M002"] = MoldInfo(
            mold_code="M002", mold_name="模具B",
            compatible_products=["P003"], setup_minutes=120
        )
        self.molds["M003"] = MoldInfo(
            mold_code="M003", mold_name="模具C",
            compatible_products=["P001", "P004"], setup_minutes=90
        )

    def get_order(self, order_no: str) -> Optional[Order]:
        return self.orders.get(order_no)

    def list_orders(self) -> List[Order]:
        return list(self.orders.values())

    def add_order(self, order: Order):
        self.orders[order.order_no] = order

    def update_order(self, order_no: str, **kwargs) -> Optional[Order]:
        if order_no not in self.orders:
            return None
        order = self.orders[order_no]
        for key, value in kwargs.items():
            if value is not None and hasattr(order, key):
                setattr(order, key, value)
        return order

    def delete_order(self, order_no: str) -> bool:
        if order_no in self.orders:
            del self.orders[order_no]
            return True
        return False

    def get_line(self, line_id: str) -> Optional[ProductionLine]:
        return self.lines.get(line_id)

    def list_lines(self) -> List[ProductionLine]:
        return list(self.lines.values())

    def add_line(self, line: ProductionLine):
        self.lines[line.line_id] = line

    def update_line(self, line_id: str, **kwargs) -> Optional[ProductionLine]:
        if line_id not in self.lines:
            return None
        line = self.lines[line_id]
        for key, value in kwargs.items():
            if value is not None and hasattr(line, key):
                setattr(line, key, value)
        return line

    def delete_line(self, line_id: str) -> bool:
        if line_id in self.lines:
            del self.lines[line_id]
            return True
        return False

    def get_holidays(self) -> List[date]:
        return self.holidays

    def set_holidays(self, dates: List[date]):
        self.holidays = sorted(set(dates))

    def add_holiday(self, d: date):
        if d not in self.holidays:
            self.holidays.append(d)
            self.holidays.sort()

    def remove_holiday(self, d: date) -> bool:
        if d in self.holidays:
            self.holidays.remove(d)
            return True
        return False

    def get_mold(self, mold_code: str) -> Optional[MoldInfo]:
        return self.molds.get(mold_code)

    def list_molds(self) -> List[MoldInfo]:
        return list(self.molds.values())

    def add_mold(self, mold: MoldInfo):
        self.molds[mold.mold_code] = mold

    def get_mold_for_product(self, product_code: str) -> Optional[MoldInfo]:
        for mold in self.molds.values():
            if product_code in mold.compatible_products:
                return mold
        return None

    def get_shift(self, shift_name: str) -> Optional[ShiftDefinition]:
        return self.shifts.get(shift_name)

    def list_shifts(self) -> List[ShiftDefinition]:
        return list(self.shifts.values())

    def set_scheduled_work_orders(self, work_orders: List[WorkOrder]):
        self.scheduled_work_orders = work_orders

    def get_scheduled_work_orders(self) -> List[WorkOrder]:
        return self.scheduled_work_orders

    def find_work_order(self, order_no: str) -> Optional[WorkOrder]:
        for wo in self.scheduled_work_orders:
            if wo.order_no == order_no:
                return wo
        return None


store = MemoryStore()
