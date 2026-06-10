from datetime import date
from fastapi import APIRouter, Query

from app.models import AchievementReport
from app.modules.stats.service import calculate_achievement_rate, get_plan_vs_actual

router = APIRouter(prefix="/stats", tags=["统计分析"])


@router.get("/achievement", response_model=AchievementReport)
def get_achievement_rate(
    period_start: date | None = Query(default=None),
    period_end: date | None = Query(default=None),
):
    return calculate_achievement_rate(period_start, period_end)


@router.get("/plan-vs-actual/{order_no}")
def get_plan_vs_actual_endpoint(order_no: str):
    result = get_plan_vs_actual(order_no)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="订单不存在")
    return result
