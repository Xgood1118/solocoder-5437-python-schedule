from fastapi import APIRouter, Query, HTTPException
from typing import List

from app.models import (
    ManualAdjustRequest, ManualAdjustResult,
    ReplanResult, ObjectiveType
)
from app.modules.replan.service import (
    manual_adjust, auto_optimize, incremental_replan,
    full_replan, freeze_order, unfreeze_order, holiday_change_replan
)

router = APIRouter(prefix="/replan", tags=["重排管理"])


@router.post("/manual", response_model=ManualAdjustResult)
def manual_adjust_endpoint(request: ManualAdjustRequest):
    return manual_adjust(request)


@router.post("/auto-optimize", response_model=ReplanResult)
def auto_optimize_endpoint(
    objective: ObjectiveType = Query(default=ObjectiveType.MAX_ON_TIME)
):
    return auto_optimize(objective)


@router.post("/incremental", response_model=ReplanResult)
def incremental_replan_endpoint(modified_order_nos: List[str]):
    if not modified_order_nos:
        raise HTTPException(status_code=400, detail="请提供变更的订单号列表")
    return incremental_replan(modified_order_nos)


@router.post("/full", response_model=ReplanResult)
def full_replan_endpoint(
    objective: ObjectiveType = Query(default=ObjectiveType.MAX_ON_TIME)
):
    return full_replan(objective)


@router.post("/freeze/{order_no}")
def freeze_order_endpoint(order_no: str):
    return freeze_order(order_no)


@router.post("/unfreeze/{order_no}")
def unfreeze_order_endpoint(order_no: str):
    return unfreeze_order(order_no)


@router.post("/holiday-change", response_model=ReplanResult)
def holiday_change_replan_endpoint():
    return holiday_change_replan()
