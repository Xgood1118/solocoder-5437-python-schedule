import os
from datetime import date, timedelta
from typing import List

PORT = int(os.getenv("PORT", "9090"))

SOLVER_TIMEOUT_SECONDS = 30

DEFAULT_SHIFT_START_HOUR = 8
DEFAULT_SHIFT_END_HOUR = 16
WORK_HOURS_PER_DAY = 8
MOLD_SETUP_MINUTES = 120


def _generate_default_holidays() -> List[date]:
    today = date.today()
    year = today.year
    holidays = []
    
    holidays.append(date(year, 1, 1))
    holidays.append(date(year, 1, 2))
    holidays.append(date(year, 1, 3))
    
    holidays.append(date(year, 5, 1))
    holidays.append(date(year, 5, 2))
    holidays.append(date(year, 5, 3))
    holidays.append(date(year, 5, 4))
    holidays.append(date(year, 5, 5))
    
    holidays.append(date(year, 10, 1))
    holidays.append(date(year, 10, 2))
    holidays.append(date(year, 10, 3))
    holidays.append(date(year, 10, 4))
    holidays.append(date(year, 10, 5))
    holidays.append(date(year, 10, 6))
    holidays.append(date(year, 10, 7))
    
    return holidays


DEFAULT_HOLIDAYS = _generate_default_holidays()
