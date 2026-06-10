from datetime import datetime
from typing import List

from app.models import GanttData, GanttRow, GanttBar, WorkOrder
from app.store import store


def _get_color(order_no: str) -> str:
    colors = [
        "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6",
        "#F79646", "#948A54", "#494429", "#8DB4E2", "#EB9D9D",
        "#C2D69B", "#B4A7D6", "#93CDDD", "#FAC08F", "#D7E3BC",
    ]
    idx = hash(order_no) % len(colors)
    return colors[idx]


def gantt_by_line() -> GanttData:
    work_orders = store.get_scheduled_work_orders()
    lines = store.list_lines()

    rows = []
    all_starts = []
    all_ends = []

    for line in lines:
        line_jobs = [wo for wo in work_orders if wo.line_id == line.line_id]
        line_jobs.sort(key=lambda j: j.start_time)

        bars = []
        for wo in line_jobs:
            order = store.get_order(wo.order_no)
            bars.append(GanttBar(
                id=f"{wo.order_no}-{wo.line_id}",
                name=wo.order_no,
                start=wo.start_time,
                end=wo.end_time,
                color=_get_color(wo.order_no),
                order_no=wo.order_no,
                line_id=wo.line_id,
                customer_name=order.customer_name if order else "",
            ))
            all_starts.append(wo.start_time)
            all_ends.append(wo.end_time)

        rows.append(GanttRow(
            row_id=line.line_id,
            row_name=line.line_name,
            bars=bars,
        ))

    time_start = min(all_starts) if all_starts else datetime.now()
    time_end = max(all_ends) if all_ends else datetime.now()

    return GanttData(rows=rows, time_start=time_start, time_end=time_end)


def gantt_by_order() -> GanttData:
    work_orders = store.get_scheduled_work_orders()
    orders = store.list_orders()
    order_map = {o.order_no: o for o in orders}

    rows = []
    all_starts = []
    all_ends = []

    for order in orders:
        order_jobs = [wo for wo in work_orders if wo.order_no == order.order_no]
        order_jobs.sort(key=lambda j: j.start_time)

        bars = []
        for wo in order_jobs:
            bars.append(GanttBar(
                id=f"{wo.order_no}-{wo.line_id}",
                name=f"{wo.line_id}",
                start=wo.start_time,
                end=wo.end_time,
                color=_get_color(wo.order_no),
                order_no=wo.order_no,
                line_id=wo.line_id,
                customer_name=order.customer_name,
            ))
            all_starts.append(wo.start_time)
            all_ends.append(wo.end_time)

        rows.append(GanttRow(
            row_id=order.order_no,
            row_name=f"{order.order_no} ({order.product_code})",
            bars=bars,
        ))

    time_start = min(all_starts) if all_starts else datetime.now()
    time_end = max(all_ends) if all_ends else datetime.now()

    return GanttData(rows=rows, time_start=time_start, time_end=time_end)


def gantt_by_customer() -> GanttData:
    work_orders = store.get_scheduled_work_orders()
    orders = store.list_orders()
    order_map = {o.order_no: o for o in orders}

    customers = {}
    for order in orders:
        customers.setdefault(order.customer_name, []).append(order)

    rows = []
    all_starts = []
    all_ends = []

    for customer_name, customer_orders in customers.items():
        bars = []
        for order in customer_orders:
            order_jobs = [wo for wo in work_orders if wo.order_no == order.order_no]
            for wo in order_jobs:
                bars.append(GanttBar(
                    id=f"{wo.order_no}-{wo.line_id}",
                    name=f"{wo.order_no} ({wo.line_id})",
                    start=wo.start_time,
                    end=wo.end_time,
                    color=_get_color(wo.order_no),
                    order_no=wo.order_no,
                    line_id=wo.line_id,
                    customer_name=customer_name,
                ))
                all_starts.append(wo.start_time)
                all_ends.append(wo.end_time)

        rows.append(GanttRow(
            row_id=customer_name,
            row_name=customer_name,
            bars=bars,
        ))

    rows.sort(key=lambda r: r.row_name)

    time_start = min(all_starts) if all_starts else datetime.now()
    time_end = max(all_ends) if all_ends else datetime.now()

    return GanttData(rows=rows, time_start=time_start, time_end=time_end)
