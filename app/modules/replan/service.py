from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from copy import deepcopy

from app.models import (
    WorkOrder, ManualAdjustRequest, ManualAdjustResult,
    ConflictDetail, ReplanResult, ReplanDiff, ObjectiveType,
    OrderStatus, Order
)
from app.store import store
from app.modules.schedule.greedy_solver import validate_schedule
from app.modules.schedule.service import run_schedule, _get_frozen_work_orders
from app.time_utils import is_within_working_hours, is_holiday


def _compute_diffs(
    old_orders: List[WorkOrder],
    new_orders: List[WorkOrder],
) -> List[ReplanDiff]:
    old_map = {wo.order_no: wo for wo in old_orders}
    new_map = {wo.order_no: wo for wo in new_orders}

    diffs = []
    all_order_nos = set(old_map.keys()) | set(new_map.keys())

    for order_no in all_order_nos:
        old_wo = old_map.get(order_no)
        new_wo = new_map.get(order_no)

        if old_wo and new_wo:
            changed = False
            diff = ReplanDiff(order_no=order_no, change_type="modified")

            if old_wo.start_time != new_wo.start_time:
                diff.old_start_time = old_wo.start_time
                diff.new_start_time = new_wo.start_time
                changed = True

            if old_wo.end_time != new_wo.end_time:
                diff.old_end_time = old_wo.end_time
                diff.new_end_time = new_wo.end_time
                changed = True

            if old_wo.line_id != new_wo.line_id:
                diff.old_line_id = old_wo.line_id
                diff.new_line_id = new_wo.line_id
                changed = True

            if changed:
                diffs.append(diff)

        elif old_wo and not new_wo:
            diffs.append(ReplanDiff(
                order_no=order_no,
                old_start_time=old_wo.start_time,
                old_end_time=old_wo.end_time,
                old_line_id=old_wo.line_id,
                change_type="removed",
            ))

        elif not old_wo and new_wo:
            diffs.append(ReplanDiff(
                order_no=order_no,
                new_start_time=new_wo.start_time,
                new_end_time=new_wo.end_time,
                new_line_id=new_wo.line_id,
                change_type="added",
            ))

    return diffs


def manual_adjust(request: ManualAdjustRequest) -> ManualAdjustResult:
    current_orders = store.get_scheduled_work_orders()
    target_wo = None
    other_wos = []

    for wo in current_orders:
        if wo.order_no == request.order_no:
            target_wo = wo
        else:
            other_wos.append(wo)

    if not target_wo:
        return ManualAdjustResult(success=False, message="工单不存在")

    if target_wo.is_frozen:
        return ManualAdjustResult(success=False, message="工单已冻结，无法调整")

    new_wo = deepcopy(target_wo)

    if request.new_line_id is not None:
        line = store.get_line(request.new_line_id)
        if not line:
            return ManualAdjustResult(success=False, message="目标产线不存在")
        order = store.get_order(request.order_no)
        if order and order.product_code not in line.supported_products:
            return ManualAdjustResult(
                success=False,
                message=f"产线 {line.line_name} 不支持产品 {order.product_code}"
            )
        new_wo.line_id = request.new_line_id

    if request.new_start_time is not None:
        holidays = store.get_holidays()
        if not is_within_working_hours(request.new_start_time, holidays):
            if is_holiday(request.new_start_time.date(), holidays):
                return ManualAdjustResult(
                    success=False,
                    message=f"开始时间 {request.new_start_time.strftime('%Y-%m-%d')} 是节假日，不可排产",
                )
            elif request.new_start_time.weekday() >= 5:
                return ManualAdjustResult(
                    success=False,
                    message=f"开始时间 {request.new_start_time.strftime('%Y-%m-%d')} 是周末，不可排产",
                )
            else:
                return ManualAdjustResult(
                    success=False,
                    message="开始时间不在工作时段内（8:00-16:00）",
                )
        duration = new_wo.end_time - new_wo.start_time
        new_wo.start_time = request.new_start_time
        new_wo.end_time = request.new_start_time + duration

    test_orders = other_wos + [new_wo]
    has_conflicts, conflicts, _ = validate_schedule(test_orders)

    if has_conflicts:
        return ManualAdjustResult(
            success=False,
            message="调整后存在冲突",
            conflicts=conflicts,
        )

    updated_orders = other_wos + [new_wo]
    store.set_scheduled_work_orders(updated_orders)

    return ManualAdjustResult(success=True, message="调整成功")


def auto_optimize(objective: ObjectiveType) -> ReplanResult:
    old_orders = deepcopy(store.get_scheduled_work_orders())

    result = run_schedule(objective=objective, use_cp_sat=True)
    new_orders = result.work_orders

    diffs = _compute_diffs(old_orders, new_orders)

    return ReplanResult(
        work_orders=new_orders,
        diffs=diffs,
        solver_used=result.solver_used,
        is_incremental=False,
    )


def incremental_replan(modified_order_nos: List[str]) -> ReplanResult:
    from app.modules.schedule.greedy_solver import solve_greedy

    old_orders = deepcopy(store.get_scheduled_work_orders())
    holidays = store.get_holidays()
    lines = store.list_lines()
    all_orders = store.list_orders()

    frozen_work_orders = _get_frozen_work_orders()

    removed_wos = []
    kept_wos = []
    for wo in store.get_scheduled_work_orders():
        if wo.order_no in modified_order_nos:
            removed_wos.append(wo)
        else:
            kept_wos.append(wo)

    affected_lines = set()
    affected_order_nos = set(modified_order_nos)

    for wo in removed_wos:
        affected_lines.add(wo.line_id)

    for wo in kept_wos:
        if wo.line_id in affected_lines and not wo.is_frozen:
            affected_order_nos.add(wo.order_no)

    reassign_orders = []
    fixed_orders = []

    for wo in kept_wos:
        if wo.order_no in affected_order_nos and not wo.is_frozen:
            pass
        else:
            fixed_orders.append(wo)

    orders_to_reschedule = []
    for order in all_orders:
        if order.order_no in affected_order_nos and order.status not in (
            OrderStatus.COMPLETED, OrderStatus.CANCELLED
        ):
            orders_to_reschedule.append(order)

    all_fixed = fixed_orders + frozen_work_orders

    new_wos, _, _ = solve_greedy(
        orders_to_reschedule, lines, holidays, all_fixed
    )

    final_wos = new_wos + [wo for wo in all_fixed if wo.order_no not in {w.order_no for w in new_wos}]

    store.set_scheduled_work_orders(final_wos)

    diffs = _compute_diffs(old_orders, final_wos)

    return ReplanResult(
        work_orders=final_wos,
        diffs=diffs,
        solver_used="greedy-incremental",
        is_incremental=True,
    )


def full_replan(objective: ObjectiveType = ObjectiveType.MAX_ON_TIME) -> ReplanResult:
    old_orders = deepcopy(store.get_scheduled_work_orders())

    result = run_schedule(objective=objective, use_cp_sat=True)
    new_orders = result.work_orders

    diffs = _compute_diffs(old_orders, new_orders)

    return ReplanResult(
        work_orders=new_orders,
        diffs=diffs,
        solver_used=result.solver_used,
        is_incremental=False,
    )


def freeze_order(order_no: str) -> dict:
    work_orders = store.get_scheduled_work_orders()
    found = False
    for wo in work_orders:
        if wo.order_no == order_no:
            wo.is_frozen = True
            found = True
            break

    if not found:
        return {"success": False, "message": "工单不存在"}

    store.set_scheduled_work_orders(work_orders)
    return {"success": True, "message": f"工单 {order_no} 已冻结"}


def unfreeze_order(order_no: str) -> dict:
    work_orders = store.get_scheduled_work_orders()
    found = False
    for wo in work_orders:
        if wo.order_no == order_no:
            wo.is_frozen = False
            found = True
            break

    if not found:
        return {"success": False, "message": "工单不存在"}

    store.set_scheduled_work_orders(work_orders)
    return {"success": True, "message": f"工单 {order_no} 已解冻"}


def holiday_change_replan() -> ReplanResult:
    old_orders = deepcopy(store.get_scheduled_work_orders())
    holidays = store.get_holidays()

    needs_replan = False
    for wo in old_orders:
        current = wo.start_time
        while current <= wo.end_time:
            if current.date() in holidays or current.weekday() >= 5:
                if wo.start_time <= current < wo.end_time:
                    needs_replan = True
                    break
            current += timedelta(days=1)
        if needs_replan:
            break

    if not needs_replan:
        return ReplanResult(
            work_orders=old_orders,
            diffs=[],
            solver_used="none-needed",
            is_incremental=False,
        )

    result = run_schedule(objective=ObjectiveType.MAX_ON_TIME, use_cp_sat=True)
    new_orders = result.work_orders

    diffs = _compute_diffs(old_orders, new_orders)

    return ReplanResult(
        work_orders=new_orders,
        diffs=diffs,
        solver_used=result.solver_used,
        is_incremental=False,
    )
