from datetime import datetime, date, time, timedelta
from typing import List, Dict, Tuple, Optional

from app.models import (
    Order, ProductionLine, WorkOrder, ObjectiveType,
    Priority, CustomerImportance, WorkerShift
)
from app.config import SOLVER_TIMEOUT_SECONDS, MOLD_SETUP_MINUTES, WORK_HOURS_PER_DAY, DEFAULT_SHIFT_START_HOUR
from app.time_utils import calculate_end_time, is_holiday
from app.store import store


PRIORITY_WEIGHT = {
    Priority.P0: 100,
    Priority.P1: 50,
    Priority.P2: 10,
}

CUSTOMER_WEIGHT_MULTIPLIER = {
    CustomerImportance.VIP: 10,
    CustomerImportance.BIG: 3,
    CustomerImportance.NORMAL: 1,
}


def _get_order_weight(order: Order) -> int:
    base = PRIORITY_WEIGHT.get(order.priority, 10)
    mult = CUSTOMER_WEIGHT_MULTIPLIER.get(order.customer_importance, 1)
    return base * mult


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


def _get_schedule_horizon_minutes() -> int:
    return 42 * 24 * 60


def _generate_working_minute_mask(base_date: date, holidays: list, total_days: int = 14) -> List[bool]:
    mask = []
    for day_offset in range(total_days):
        d = base_date + timedelta(days=day_offset)
        is_workday = d.weekday() < 5 and d not in holidays
        day_minutes = [is_workday] * (8 * 60)
        mask.extend(day_minutes)
    return mask


def solve_with_cp_sat(
    orders: List[Order],
    lines: List[ProductionLine],
    holidays: List[date],
    objective: ObjectiveType = ObjectiveType.MAX_ON_TIME,
    frozen_order_nos: Optional[List[str]] = None,
    frozen_work_orders: Optional[List[WorkOrder]] = None,
) -> Tuple[List[WorkOrder], List[str], float, str]:
    from ortools.sat.python import cp_model

    start_time = datetime.now()
    frozen_order_nos = frozen_order_nos or []
    frozen_work_orders = frozen_work_orders or []

    if not orders or not lines:
        return [], ["无订单或无产线"], 0.0, "cp-sat"

    model = cp_model.CpModel()
    schedule_start = _get_schedule_start(holidays)
    horizon_minutes = _get_schedule_horizon_minutes()
    holidays_set = set(holidays)

    base_date = schedule_start.date()
    working_day_slots = []
    for day_offset in range(42):
        d = base_date + timedelta(days=day_offset)
        if d.weekday() < 5 and d not in holidays_set:
            working_day_slots.append(day_offset)

    orders_to_schedule = [o for o in orders if o.order_no not in frozen_order_nos]

    order_line_map: Dict[Tuple[str, str], dict] = {}
    all_intervals_by_line: Dict[str, list] = {line.line_id: [] for line in lines}

    for order in orders_to_schedule:
        for line in lines:
            if order.product_code not in line.supported_products:
                continue
            work_minutes = _calculate_work_minutes(order, line)
            if work_minutes <= 0:
                continue

            mold = store.get_mold_for_product(order.product_code)
            needs_setup = True
            if mold and line.current_mold and mold.mold_code == line.current_mold:
                needs_setup = False
            setup_min = MOLD_SETUP_MINUTES if needs_setup else 0
            total_duration = work_minutes + setup_min

            key = (order.order_no, line.line_id)
            presence = model.NewBoolVar(f"pres_{order.order_no}_{line.line_id}")
            start_var = model.NewIntVar(0, horizon_minutes, f"start_{order.order_no}_{line.line_id}")
            end_var = model.NewIntVar(0, horizon_minutes, f"end_{order.order_no}_{line.line_id}")
            interval = model.NewOptionalIntervalVar(
                start_var, total_duration, end_var, presence,
                f"interval_{order.order_no}_{line.line_id}"
            )

            order_line_map[key] = {
                "presence": presence,
                "start": start_var,
                "end": end_var,
                "interval": interval,
                "work_minutes": work_minutes,
                "total_duration": total_duration,
                "setup_minutes": setup_min,
                "order": order,
                "line": line,
            }
            all_intervals_by_line[line.line_id].append(interval)

    for order in orders_to_schedule:
        presences = []
        for line in lines:
            key = (order.order_no, line.line_id)
            if key in order_line_map:
                presences.append(order_line_map[key]["presence"])
        if presences:
            model.Add(sum(presences) == 1)

    for line_id, intervals in all_intervals_by_line.items():
        if intervals:
            model.AddNoOverlap(intervals)

    obj_exprs = []
    for key, info in order_line_map.items():
        order = info["order"]
        presence = info["presence"]
        end_var = info["end"]
        weight = _get_order_weight(order)

        due_date_dt = datetime.combine(order.due_date, time(17, 0))
        due_minutes = int((due_date_dt - schedule_start).total_seconds() / 60)

        if objective == ObjectiveType.MAX_ON_TIME:
            on_time = model.NewBoolVar(f"ontime_{order.order_no}")
            model.Add(end_var <= due_minutes).OnlyEnforceIf(on_time)
            model.Add(end_var > due_minutes).OnlyEnforceIf(on_time.Not())
            model.Add(on_time == 1).OnlyEnforceIf(presence)
            model.Add(on_time == 0).OnlyEnforceIf(presence.Not())
            obj_exprs.append(weight * on_time)
            obj_exprs.append(-info["setup_minutes"] * presence)

        elif objective == ObjectiveType.MIN_DELAY:
            delay = model.NewIntVar(0, horizon_minutes, f"delay_{order.order_no}")
            model.Add(delay >= end_var - due_minutes).OnlyEnforceIf(presence)
            model.Add(delay == 0).OnlyEnforceIf(presence.Not())
            obj_exprs.append(-weight * delay)
            obj_exprs.append(-info["setup_minutes"] * presence)

        elif objective == ObjectiveType.MAX_UTILIZATION:
            obj_exprs.append(weight * info["work_minutes"] * presence)
            obj_exprs.append(-info["setup_minutes"] * presence)

    model.Maximize(sum(obj_exprs))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIMEOUT_SECONDS
    solver.parameters.num_workers = 4
    status = solver.Solve(model)

    solve_time = (datetime.now() - start_time).total_seconds()

    work_orders: List[WorkOrder] = []
    warnings: List[str] = []

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for key, info in order_line_map.items():
            if solver.BooleanValue(info["presence"]):
                order = info["order"]
                line = info["line"]
                start_min = solver.Value(info["start"])

                raw_start_dt = schedule_start + timedelta(minutes=start_min)

                if raw_start_dt.weekday() >= 5 or is_holiday(raw_start_dt.date(), holidays):
                    actual_start_dt = calculate_end_time(
                        raw_start_dt, 0, holidays,
                        DEFAULT_SHIFT_START_HOUR, WORK_HOURS_PER_DAY
                    )
                else:
                    actual_start_dt = raw_start_dt

                actual_end_dt = calculate_end_time(
                    actual_start_dt, info["total_duration"], holidays,
                    DEFAULT_SHIFT_START_HOUR, WORK_HOURS_PER_DAY
                )

                mold = store.get_mold_for_product(order.product_code)
                mold_code = mold.mold_code if mold else "UNKNOWN"
                setup_minutes = info["setup_minutes"]

                work_order = WorkOrder(
                    order_no=order.order_no,
                    line_id=line.line_id,
                    start_time=actual_start_dt,
                    end_time=actual_end_dt,
                    worker_shift=line.worker_shift if line.worker_shift != WorkerShift.BOTH else WorkerShift.DAY,
                    mold_code=mold_code,
                    quantity=order.quantity,
                    setup_minutes=setup_minutes,
                    is_frozen=False,
                )
                work_orders.append(work_order)

        for fwo in frozen_work_orders:
            work_orders.append(fwo)

        solver_type = "cp-sat-optimal" if status == cp_model.OPTIMAL else "cp-sat-feasible"
    else:
        warnings.append("CP-SAT 求解器未找到可行解")
        solver_type = "cp-sat-no-solution"

    return work_orders, warnings, solve_time, solver_type
