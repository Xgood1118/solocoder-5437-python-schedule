from fastapi import APIRouter, Query

from app.models import ScheduleResult, ObjectiveType
from app.modules.schedule.service import run_schedule, get_current_schedule

router = APIRouter(prefix="/schedule", tags=["排产计划"])


@router.post("/run", response_model=ScheduleResult)
def run_scheduling(
    objective: ObjectiveType = Query(default=ObjectiveType.MAX_ON_TIME),
    use_cp_sat: bool = Query(default=True),
):
    return run_schedule(objective=objective, use_cp_sat=use_cp_sat)


@router.get("", response_model=ScheduleResult)
def get_schedule():
    return get_current_schedule()
