from typing import List
from fastapi import APIRouter, HTTPException

from app.models import Order, OrderCreate, OrderUpdate, OrderStatus
from app.store import store

router = APIRouter(prefix="/orders", tags=["订单管理"])


@router.get("", response_model=List[Order])
def list_orders(status: OrderStatus | None = None):
    orders = store.list_orders()
    if status:
        orders = [o for o in orders if o.status == status]
    return orders


@router.get("/{order_no}", response_model=Order)
def get_order(order_no: str):
    order = store.get_order(order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@router.post("", response_model=Order)
def create_order(order_data: OrderCreate):
    if store.get_order(order_data.order_no):
        raise HTTPException(status_code=400, detail="订单号已存在")
    order = Order(**order_data.model_dump())
    store.add_order(order)
    return order


@router.put("/{order_no}", response_model=Order)
def update_order(order_no: str, update_data: OrderUpdate):
    updated = store.update_order(order_no, **update_data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="订单不存在")
    return updated


@router.delete("/{order_no}")
def delete_order(order_no: str):
    if not store.delete_order(order_no):
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"message": "删除成功"}


@router.post("/{order_no}/start")
def start_order(order_no: str):
    from datetime import datetime
    order = store.get_order(order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order.status = OrderStatus.IN_PROGRESS
    order.actual_start_time = datetime.now()
    return {"message": "工单已开工", "actual_start_time": order.actual_start_time}


@router.post("/{order_no}/complete")
def complete_order(order_no: str):
    from datetime import datetime
    order = store.get_order(order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order.status = OrderStatus.COMPLETED
    order.actual_end_time = datetime.now()
    return {"message": "工单已完工", "actual_end_time": order.actual_end_time}
