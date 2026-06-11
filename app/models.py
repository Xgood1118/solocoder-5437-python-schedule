from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class CustomerImportance(str, Enum):
    NORMAL = "普通客户"
    BIG = "大客户"
    VIP = "VIP"


class MoldStatus(str, Enum):
    INSTALLED = "已装好"
    TO_SWITCH = "待切换"
    MISSING = "缺模"


class WorkerShift(str, Enum):
    DAY = "白班"
    NIGHT = "夜班"
    BOTH = "两班倒"


class OrderStatus(str, Enum):
    PENDING = "待排产"
    SCHEDULED = "已排产"
    IN_PROGRESS = "进行中"
    COMPLETED = "已完工"
    CANCELLED = "已取消"


class MaterialItem(BaseModel):
    material_code: str
    material_name: str
    required_qty: float
    stock_qty: float
    is_ok: bool


class Order(BaseModel):
    order_no: str
    product_code: str
    quantity: float
    due_date: date
    priority: Priority
    customer_importance: CustomerImportance
    customer_name: str
    materials: List[MaterialItem] = []
    status: OrderStatus = OrderStatus.PENDING
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None


class OrderCreate(BaseModel):
    order_no: str
    product_code: str
    quantity: float
    due_date: date
    priority: Priority
    customer_importance: CustomerImportance
    customer_name: str
    materials: List[MaterialItem] = []


class OrderUpdate(BaseModel):
    quantity: Optional[float] = None
    due_date: Optional[date] = None
    priority: Optional[Priority] = None
    customer_importance: Optional[CustomerImportance] = None
    materials: Optional[List[MaterialItem]] = None


class ProductionLine(BaseModel):
    line_id: str
    line_name: str
    supported_products: List[str]
    daily_capacity: float
    mold_status: MoldStatus
    current_mold: Optional[str] = None
    worker_shift: WorkerShift
    efficiency: float = 1.0


class ProductionLineCreate(BaseModel):
    line_id: str
    line_name: str
    supported_products: List[str]
    daily_capacity: float
    mold_status: MoldStatus
    current_mold: Optional[str] = None
    worker_shift: WorkerShift
    efficiency: float = 1.0


class ProductionLineUpdate(BaseModel):
    line_name: Optional[str] = None
    supported_products: Optional[List[str]] = None
    daily_capacity: Optional[float] = None
    mold_status: Optional[MoldStatus] = None
    current_mold: Optional[str] = None
    worker_shift: Optional[WorkerShift] = None
    efficiency: Optional[float] = None


class WorkOrder(BaseModel):
    order_no: str
    line_id: str
    start_time: datetime
    end_time: datetime
    worker_shift: WorkerShift
    mold_code: str
    quantity: float
    setup_minutes: int = 0
    is_overtime: bool = False
    is_frozen: bool = False
    needs_manual_adjustment: bool = False


class ScheduledWorkOrder(WorkOrder):
    scheduled_start_time: datetime
    scheduled_end_time: datetime


class BottleneckItem(BaseModel):
    order_no: str
    delayed_days: int
    reason: str
    suggestion: str


class UnscheduledOrder(BaseModel):
    order_no: str
    product_code: str
    reason: str


class ScheduleResult(BaseModel):
    work_orders: List[WorkOrder]
    bottleneck_analysis: List[BottleneckItem]
    unscheduled_orders: List[UnscheduledOrder] = []
    solver_used: str
    solve_time_seconds: float
    has_conflicts: bool = False
    conflict_details: List[str] = []


class ShiftDefinition(BaseModel):
    shift_name: str
    start_hour: int
    end_hour: int


class MoldInfo(BaseModel):
    mold_code: str
    mold_name: str
    compatible_products: List[str]
    setup_minutes: int = 120


class ObjectiveType(str, Enum):
    MAX_ON_TIME = "最大化按时交付订单数"
    MIN_DELAY = "最小化总延期天数"
    MAX_UTILIZATION = "最大化设备利用率"


class ManualAdjustRequest(BaseModel):
    order_no: str
    new_line_id: Optional[str] = None
    new_start_time: Optional[datetime] = None


class ConflictDetail(BaseModel):
    order_no_1: str
    order_no_2: str
    line_id: str
    conflict_start: datetime
    conflict_end: datetime
    reason: str


class ManualAdjustResult(BaseModel):
    success: bool
    message: str
    conflicts: List[ConflictDetail] = []


class ReplanDiff(BaseModel):
    order_no: str
    old_start_time: Optional[datetime] = None
    new_start_time: Optional[datetime] = None
    old_end_time: Optional[datetime] = None
    new_end_time: Optional[datetime] = None
    old_line_id: Optional[str] = None
    new_line_id: Optional[str] = None
    change_type: str


class ReplanResult(BaseModel):
    work_orders: List[WorkOrder]
    diffs: List[ReplanDiff]
    solver_used: str
    is_incremental: bool


class GanttBar(BaseModel):
    id: str
    name: str
    start: datetime
    end: datetime
    color: str
    order_no: Optional[str] = None
    line_id: Optional[str] = None
    customer_name: Optional[str] = None


class GanttRow(BaseModel):
    row_id: str
    row_name: str
    bars: List[GanttBar]


class GanttData(BaseModel):
    rows: List[GanttRow]
    time_start: datetime
    time_end: datetime


class AchievementRateItem(BaseModel):
    category: str
    category_value: str
    total_orders: int
    on_time_orders: int
    achievement_rate: float


class AchievementReport(BaseModel):
    period: str
    overall_rate: float
    by_line: List[AchievementRateItem]
    by_product: List[AchievementRateItem]


class HolidayUpdateRequest(BaseModel):
    dates: List[date]
