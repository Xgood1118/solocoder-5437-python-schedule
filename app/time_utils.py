from datetime import date, datetime, time, timedelta
from typing import Optional

from app.config import WORK_HOURS_PER_DAY, DEFAULT_SHIFT_START_HOUR


def minutes_from_start_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def is_holiday(d: date, holidays: list) -> bool:
    return d in holidays


def add_working_days(start_date: date, days: int, holidays: list) -> date:
    current = start_date
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5 and not is_holiday(current, holidays):
            added += 1
    return current


def count_working_minutes(start: datetime, end: datetime, holidays: list) -> int:
    if end <= start:
        return 0
    total = 0
    current = start
    while current < end:
        day_start = datetime.combine(current.date(), time(DEFAULT_SHIFT_START_HOUR, 0))
        day_end = datetime.combine(current.date(), time(DEFAULT_SHIFT_START_HOUR + WORK_HOURS_PER_DAY, 0))
        if is_holiday(current.date(), holidays) or current.weekday() >= 5:
            current = datetime.combine(current.date() + timedelta(days=1), time(DEFAULT_SHIFT_START_HOUR, 0))
            continue
        seg_start = max(current, day_start)
        seg_end = min(end, day_end)
        if seg_end > seg_start:
            total += int((seg_end - seg_start).total_seconds() / 60)
        current = datetime.combine(current.date() + timedelta(days=1), time(DEFAULT_SHIFT_START_HOUR, 0))
    return total


def calculate_end_time(start: datetime, work_minutes: int, holidays: list,
                       shift_start_hour: int = DEFAULT_SHIFT_START_HOUR,
                       shift_hours: int = WORK_HOURS_PER_DAY) -> datetime:
    remaining = work_minutes
    current = start
    while remaining > 0:
        if is_holiday(current.date(), holidays) or current.weekday() >= 5:
            current = datetime.combine(current.date() + timedelta(days=1), time(shift_start_hour, 0))
            continue
        day_end = datetime.combine(current.date(), time(shift_start_hour + shift_hours, 0))
        if current >= day_end:
            current = datetime.combine(current.date() + timedelta(days=1), time(shift_start_hour, 0))
            continue
        day_start = datetime.combine(current.date(), time(shift_start_hour, 0))
        if current < day_start:
            current = day_start
        available = int((day_end - current).total_seconds() / 60)
        if available >= remaining:
            current += timedelta(minutes=remaining)
            remaining = 0
        else:
            remaining -= available
            current = datetime.combine(current.date() + timedelta(days=1), time(shift_start_hour, 0))
    return current


def is_within_working_hours(dt: datetime, holidays: list,
                            shift_start_hour: int = DEFAULT_SHIFT_START_HOUR,
                            shift_hours: int = WORK_HOURS_PER_DAY) -> bool:
    if is_holiday(dt.date(), holidays) or dt.weekday() >= 5:
        return False
    start_min = shift_start_hour * 60
    end_min = (shift_start_hour + shift_hours) * 60
    cur_min = dt.hour * 60 + dt.minute
    return start_min <= cur_min < end_min
