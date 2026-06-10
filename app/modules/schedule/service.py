from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from app.models import (
    Order, ProductionLine, WorkOrder, ScheduleResult,
    BottleneckItem, ObjectiveType, OrderStatus, WorkerShift
)
from app.config import SOLVER_TIMEOUT_SECONDS
from app.store import store
from app.modules.schedule.cp_sat_solver import solve_with_cp_sat
from app.modules.schedule.greedy_solver import solve_greedy, validate_schedule


def _get_frozen_orders() -> List[str]:
    frozen = []
    for order in store.list_orders():
        if order.status == OrderStatus.IN_PROGRESS:
            frozen.append(order.order_no)
    return frozen


def _get_frozen_work_orders() -> List[WorkOrder]:
    frozen_nos = _get_frozen_orders()
    result = []
    for wo in store.get_scheduled_work_orders():
        if wo.order_no in frozen_nos:
            wo.is_frozen = True
            result.append(wo)
    return result


def _check_material_readiness(order: Order) -> Tuple[bool, List[str]]:
    issues = []
    for mat in order.materials:
        if not mat.is_ok:
            issues.append(f"物料 {mat.material_code} 缺料")
    return len(issues) == 0, issues


def _analyze_bottlenecks(
    work_orders: List[WorkOrder],
    orders: List[Order],
) -> List[BottleneckItem]:
    bottlenecks = []
    order_map = {o.order_no: o for o in orders}

    for wo in work_orders:
        order = order_map.get(wo.order_no)
        if not order:
            continue

        due_date = order.due_date
        due_dt = datetime.combine(due_date, datetime.min.time()) + timedelta(hours=17)

        if wo.end_time > due_dt:
            delay_days = (wo.end_time.date() - due_date).days
            delay_days = max(1, delay_days)

            reasons = []
            suggestions = []

            mat_ok, mat_issues = _check_material_readiness(order)
            if not mat_ok:
                reasons.extend(mat_issues)
                suggestions.append("建议优先补齐缺料物料")

            line = store.get_line(wo.line_id)
            if line:
                reasons.append(f"产线 {line.line_name} 产能紧张")
                other_lines = [
                    l for l in store.list_lines()
                    if order.product_code in l.supported_products and l.line_id != wo.line_id
                ]
                if other_lines:
                    suggestions.append(f"可考虑转产到产线 {other_lines[0].line_name}")

            if order.priority.value in ("P2", "P1"):
                suggestions.append(f"建议推迟低优先级订单以释放产能")

            if not reasons:
                reasons.append("产能不足导致延期")

            bottleneck = BottleneckItem(
                order_no=wo.order_no,
                delayed_days=delay_days,
                reason="；".join(reasons),
                suggestion="；".join(suggestions) if suggestions else "建议增加产能或协商交期",
            )
            bottlenecks.append(bottleneck)

    return bottlenecks


def run_schedule(
    objective: ObjectiveType = ObjectiveType.MAX_ON_TIME,
    use_cp_sat: bool = True,
) -> ScheduleResult:
    orders = store.list_orders()
    lines = store.list_lines()
    holidays = store.get_holidays()

    orders_to_schedule = [o for o in orders if o.status not in (OrderStatus.COMPLETED, OrderStatus.CANCELLED)]

    if not orders_to_schedule:
        return ScheduleResult(
            work_orders=[],
            bottleneck_analysis=[],
            solver_used="none",
            solve_time_seconds=0.0,
        )

    frozen_work_orders = _get_frozen_work_orders()
    frozen_order_nos = [wo.order_no for wo in frozen_work_orders]

    solver_used = "greedy"
    solve_time = 0.0
    all_warnings: List[str] = []
    work_orders: List[WorkOrder] = []
    has_conflicts = False
    conflict_details: List[str] = []

    if use_cp_sat:
        try:
            cp_orders, cp_warnings, cp_time, cp_solver_type = solve_with_cp_sat(
                orders_to_schedule, lines, holidays, objective,
                frozen_order_nos=frozen_order_nos,
                frozen_work_orders=frozen_work_orders,
            )
            solve_time = cp_time
            all_warnings.extend(cp_warnings)

            if cp_orders and cp_solver_type != "cp-sat-no-solution":
                work_orders = cp_orders
                solver_used = cp_solver_type
            else:
                use_cp_sat = False
        except Exception as e:
            all_warnings.append(f"CP-SAT 求解器异常: {str(e)}")
            use_cp_sat = False

    if not use_cp_sat or not work_orders:
        greedy_orders, greedy_warnings, greedy_time = solve_greedy(
            orders_to_schedule, lines, holidays, frozen_work_orders
        )
        work_orders = greedy_orders
        solver_used = "greedy"
        solve_time = greedy_time
        all_warnings.extend(greedy_warnings)

        has_conflicts, conflicts, val_warnings = validate_schedule(work_orders)
        all_warnings.extend(val_warnings)
        conflict_details = [c.reason for c in conflicts]

    bottlenecks = _analyze_bottlenecks(work_orders, orders_to_schedule)

    store.set_scheduled_work_orders(work_orders)

    for wo in work_orders:
        order = store.get_order(wo.order_no)
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.SCHEDULED

    return ScheduleResult(
        work_orders=work_orders,
        bottleneck_analysis=bottlenecks,
        solver_used=solver_used,
        solve_time_seconds=round(solve_time, 2),
        has_conflicts=has_conflicts,
        conflict_details=conflict_details,
    )


def get_current_schedule() -> ScheduleResult:
    work_orders = store.get_scheduled_work_orders()
    orders = store.list_orders()
    bottlenecks = _analyze_bottlenecks(work_orders, orders)
    has_conflicts, conflicts, _ = validate_schedule(work_orders)

    return ScheduleResult(
        work_orders=work_orders,
        bottleneck_analysis=bottlenecks,
        solver_used="cached",
        solve_time_seconds=0.0,
        has_conflicts=has_conflicts,
        conflict_details=[c.reason for c in conflicts],
    )
