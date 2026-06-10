from fastapi import APIRouter

from app.models import GanttData
from app.modules.gantt.service import gantt_by_line, gantt_by_order, gantt_by_customer

router = APIRouter(prefix="/gantt", tags=["甘特图"])


@router.get("/by-line", response_model=GanttData)
def get_gantt_by_line():
    return gantt_by_line()


@router.get("/by-order", response_model=GanttData)
def get_gantt_by_order():
    return gantt_by_order()


@router.get("/by-customer", response_model=GanttData)
def get_gantt_by_customer():
    return gantt_by_customer()
