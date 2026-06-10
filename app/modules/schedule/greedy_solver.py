from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Optional

from app.models import (
    Order, ProductionLine, WorkOrder, ConflictDetail,
    Priority, CustomerImportance, WorkerShift
)
from app.config import MOLD_SETUP_MINUTES, WORK_HOURS_PER_DAY
from app.time_utils import calculate_end_time, is_holiday
from app.store import store


PRIORITY_ORDER = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2}
CUSTOMER_ORDER = {CustomerImportance.VIP: 0, CustomerImportance.BIG: 1, CustomerImportance.NORMAL: 2}


def _sort_orders(orders: List[Order]) -> List[Order]:
    return sorted(
        orders,
        key=lambda o: (
            PRIORITY_ORDER.get(o.priority, 99),
            CUSTOMER_ORDER.get(o.customer_importance, 99),
            o.due_date,
            -o.quantity,
        )
    )


def _calculate_work_minutes(order: Order, line: ProductionLine) -> int:
    daily_capacity = line.daily_capacity * line.efficiency
    days_needed = order.quantity / daily_capacity if daily_capacity > 0 else 999
    return int(days_needed * WORK_HOURS_PER_DAY * 60)


def _get_schedule_start(holidays: list = None) -> datetime:
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    start = datetime.combine(next_monday, time(8, 0))
    holidays = holidays or []
    while start.weekday() >= 5 or is_holiday(start.date(), holidays):
        start += timedelta(days=1)
        start = datetime.combine(start.date(), time(8, 0))
    return start


def _find_earliest_slot(
    line: ProductionLine,
    work_minutes: int,
    holidays: list,
    existing_jobs: List[WorkOrder],
    product_code: str,
) -> Tuple[datetime, datetime, int]:
    schedule_start = _get_schedule_start(holidays)
    shift_start_hour = 8

    line_jobs = sorted(
        [j for j in existing_jobs if j.line_id == line.line_id],
        key=lambda j: j.start_time
    )

    mold = store.get_mold_for_product(product_code)
    setup_needed = MOLD_SETUP_MINUTES

    if not line_jobs:
        if mold and line.current_mold and mold.mold_code == line.current_mold:
            setup_needed = 0
        start = schedule_start
        end = calculate_end_time(start, work_minutes + setup_needed, holidays, shift_start_hour, WORK_HOURS_PER_DAY)
        return start, end, setup_needed

    best_start = None
    best_end = None
    best_setup = setup_needed

    candidate_start = schedule_start
    prev_mold = line.current_mold

    for i, job in enumerate(line_jobs):
        if candidate_start < job.start_time:
            gap_minutes = int((job.start_time - candidate_start).total_seconds() / 60)
            setup_for_gap = setup_needed
            if prev_mold and mold and prev_mold == mold.mold_code:
                setup_for_gap = 0

            total_needed = work_minutes + setup_for_gap
            effective_gap = 0
            tmp = candidate_start
            while tmp < job.start_time and effective_gap < total_needed:
                day_start = datetime.combine(tmp.date(), time(shift_start_hour, 0))
                day_end = datetime.combine(tmp.date(), time(shift_start_hour + WORK_HOURS_PER_DAY, 0))
                if tmp.date() in holidays or tmp.weekday() >= 5:
                    tmp = datetime.combine(tmp.date() + timedelta(days=1), time(shift_start_hour, 0))
                    continue
                seg_start = max(tmp, day_start)
                seg_end = min(job.start_time, day_end)
                if seg_end > seg_start:
                    effective_gap += int((seg_end - seg_start).total_seconds() / 60)
                if tmp < day_end:
                    tmp = day_end
                else:
                    tmp = datetime.combine(tmp.date() + timedelta(days=1), time(shift_start_hour, 0))

            if effective_gap >= total_needed:
                actual_start = candidate_start
                actual_end = calculate_end_time(
                    actual_start, total_needed, holidays, shift_start_hour, WORK_HOURS_PER_DAY
                )
                if best_start is None or actual_start < best_start:
                    best_start = actual_start
                    best_end = actual_end
                    best_setup = setup_for_gap

        candidate_start = max(candidate_start, job.end_time)
        if mold and job.mold_code:
            prev_mold = job.mold_code

    if best_start is None:
        last_job = line_jobs[-1]
        setup_for_end = setup_needed
        if mold and last_job.mold_code == mold.mold_code:
            setup_for_end = 0
        start = last_job.end_time
        end = calculate_end_time(
            start, work_minutes + setup_for_end, holidays, shift_start_hour, WORK_HOURS_PER_DAY
        )
        best_start = start
        best_end = end
        best_setup = setup_for_end

    return best_start, best_end, best_setup


def solve_greedy(
    orders: List[Order],
    lines: List[ProductionLine],
    holidays: list,
    frozen_work_orders: Optional[List[WorkOrder]] = None,
) -> Tuple[List[WorkOrder], List[str], float]:
    start_time = datetime.now()
    frozen_work_orders = frozen_work_orders or []
    frozen_order_nos = {wo.order_no for wo in frozen_work_orders}

    orders_to_schedule = [o for o in orders if o.order_no not in frozen_order_nos]
    sorted_orders = _sort_orders(orders_to_schedule)

    work_orders: List[WorkOrder] = list(frozen_work_orders)
    warnings: List[str] = []

    for order in sorted_orders:
        compatible_lines = [
            line for line in lines
            if order.product_code in line.supported_products
        ]

        if not compatible_lines:
            warnings.append(f"订单 {order.order_no} 无可适配产线，产品 {order.product_code}")
            continue

        best_line = None
        best_start = None
        best_end = None
        best_setup = 0

        for line in compatible_lines:
            work_min = _calculate_work_minutes(order, line)
            start, end, setup = _find_earliest_slot(line, work_min, holidays, work_orders, order.product_code)
            if best_start is None or start < best_start:
                best_line = line
                best_start = start
                best_end = end
                best_setup = setup

        if best_line and best_start:
            mold = store.get_mold_for_product(order.product_code)
            mold_code = mold.mold_code if mold else "UNKNOWN"

            wo = WorkOrder(
                order_no=order.order_no,
                line_id=best_line.line_id,
                start_time=best_start,
                end_time=best_end,
                worker_shift=best_line.worker_shift if best_line.worker_shift != WorkerShift.BOTH else WorkerShift.DAY,
                mold_code=mold_code,
                quantity=order.quantity,
                setup_minutes=best_setup,
                is_frozen=False,
            )
            work_orders.append(wo)
        else:
            warnings.append(f"订单 {order.order_no} 无法安排")

    work_orders = [wo for wo in work_orders if wo.order_no not in frozen_order_nos] + frozen_work_orders

    solve_time = (datetime.now() - start_time).total_seconds()
    return work_orders, warnings, solve_time


def validate_schedule(work_orders: List[WorkOrder]) -> Tuple[bool, List[ConflictDetail], List[str]]:
    conflicts: List[ConflictDetail] = []
    warnings: List[str] = []

    by_line: dict = {}
    for wo in work_orders:
        by_line.setdefault(wo.line_id, []).append(wo)

    for line_id, jobs in by_line.items():
        sorted_jobs = sorted(jobs, key=lambda j: j.start_time)
        for i in range(len(sorted_jobs) - 1):
            curr = sorted_jobs[i]
            nxt = sorted_jobs[i + 1]
            if nxt.start_time < curr.end_time:
                conflict_start = nxt.start_time
                conflict_end = min(curr.end_time, nxt.end_time)
                conflicts.append(ConflictDetail(
                    order_no_1=curr.order_no,
                    order_no_2=nxt.order_no,
                    line_id=line_id,
                    conflict_start=conflict_start,
                    conflict_end=conflict_end,
                    reason=f"产线 {line_id} 上订单 {curr.order_no} 和 {nxt.order_no} 时间重叠",
                ))
                curr.needs_manual_adjustment = True
                nxt.needs_manual_adjustment = True

    has_conflicts = len(conflicts) > 0
    return has_conflicts, conflicts, warnings
