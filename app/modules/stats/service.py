from datetime import date, datetime
from typing import List, Tuple

from app.models import (
    AchievementReport, AchievementRateItem, Order, OrderStatus, WorkOrder
)
from app.store import store


def _is_order_on_time(order: Order, scheduled_wo: WorkOrder | None) -> bool:
    if not order.actual_end_time or not scheduled_wo:
        return False
    return order.actual_end_time <= scheduled_wo.end_time


def calculate_achievement_rate(
    period_start: date | None = None,
    period_end: date | None = None,
) -> AchievementReport:
    orders = store.list_orders()
    work_orders = store.get_scheduled_work_orders()
    wo_map = {wo.order_no: wo for wo in work_orders}

    completed_orders = [o for o in orders if o.status == OrderStatus.COMPLETED]

    if period_start:
        completed_orders = [
            o for o in completed_orders
            if o.actual_end_time and o.actual_end_time.date() >= period_start
        ]
    if period_end:
        completed_orders = [
            o for o in completed_orders
            if o.actual_end_time and o.actual_end_time.date() <= period_end
        ]

    total = len(completed_orders)
    on_time = 0
    for o in completed_orders:
        wo = wo_map.get(o.order_no)
        if _is_order_on_time(o, wo):
            on_time += 1

    overall_rate = on_time / total if total > 0 else 0.0

    by_line_data: dict = {}
    for o in completed_orders:
        wo = wo_map.get(o.order_no)
        if not wo:
            continue
        line_id = wo.line_id
        if line_id not in by_line_data:
            by_line_data[line_id] = {"total": 0, "on_time": 0}
        by_line_data[line_id]["total"] += 1
        if _is_order_on_time(o, wo):
            by_line_data[line_id]["on_time"] += 1

    by_line = []
    for line_id, data in by_line_data.items():
        line = store.get_line(line_id)
        line_name = line.line_name if line else line_id
        rate = data["on_time"] / data["total"] if data["total"] > 0 else 0.0
        by_line.append(AchievementRateItem(
            category="产线",
            category_value=line_name,
            total_orders=data["total"],
            on_time_orders=data["on_time"],
            achievement_rate=round(rate, 4),
        ))

    by_product_data: dict = {}
    for o in completed_orders:
        product = o.product_code
        if product not in by_product_data:
            by_product_data[product] = {"total": 0, "on_time": 0}
        by_product_data[product]["total"] += 1
        wo = wo_map.get(o.order_no)
        if _is_order_on_time(o, wo):
            by_product_data[product]["on_time"] += 1

    by_product = []
    for product, data in by_product_data.items():
        rate = data["on_time"] / data["total"] if data["total"] > 0 else 0.0
        by_product.append(AchievementRateItem(
            category="产品",
            category_value=product,
            total_orders=data["total"],
            on_time_orders=data["on_time"],
            achievement_rate=round(rate, 4),
        ))

    period_str = "全部"
    if period_start or period_end:
        period_str = f"{period_start or '开始'} 至 {period_end or '至今'}"

    return AchievementReport(
        period=period_str,
        overall_rate=round(overall_rate, 4),
        by_line=by_line,
        by_product=by_product,
    )


def get_plan_vs_actual(order_no: str) -> dict:
    order = store.get_order(order_no)
    if not order:
        return None

    wo = store.find_work_order(order_no)

    return {
        "order_no": order_no,
        "planned_start_time": wo.start_time if wo else None,
        "planned_end_time": wo.end_time if wo else None,
        "actual_start_time": order.actual_start_time,
        "actual_end_time": order.actual_end_time,
        "status": order.status,
        "is_on_time": _is_order_on_time(order, wo) if wo and order.actual_end_time else None,
    }
