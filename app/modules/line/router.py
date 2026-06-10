from typing import List
from fastapi import APIRouter, HTTPException

from app.models import (
    ProductionLine, ProductionLineCreate, ProductionLineUpdate,
    MoldInfo, ShiftDefinition, HolidayUpdateRequest
)
from app.store import store

router = APIRouter(prefix="/lines", tags=["产线管理"])


@router.get("", response_model=List[ProductionLine])
def list_lines():
    return store.list_lines()


@router.get("/{line_id}", response_model=ProductionLine)
def get_line(line_id: str):
    line = store.get_line(line_id)
    if not line:
        raise HTTPException(status_code=404, detail="产线不存在")
    return line


@router.post("", response_model=ProductionLine)
def create_line(line_data: ProductionLineCreate):
    if store.get_line(line_data.line_id):
        raise HTTPException(status_code=400, detail="产线ID已存在")
    line = ProductionLine(**line_data.model_dump())
    store.add_line(line)
    return line


@router.put("/{line_id}", response_model=ProductionLine)
def update_line(line_id: str, update_data: ProductionLineUpdate):
    updated = store.update_line(line_id, **update_data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="产线不存在")
    return updated


@router.delete("/{line_id}")
def delete_line(line_id: str):
    if not store.delete_line(line_id):
        raise HTTPException(status_code=404, detail="产线不存在")
    return {"message": "删除成功"}


@router.get("/molds/all", response_model=List[MoldInfo])
def list_molds():
    return store.list_molds()


@router.post("/molds", response_model=MoldInfo)
def create_mold(mold_data: MoldInfo):
    if store.get_mold(mold_data.mold_code):
        raise HTTPException(status_code=400, detail="模具编号已存在")
    store.add_mold(mold_data)
    return mold_data


@router.get("/shifts/all", response_model=List[ShiftDefinition])
def list_shifts():
    return store.list_shifts()


@router.get("/holidays/all")
def list_holidays():
    return {"holidays": [d.isoformat() for d in store.get_holidays()]}


@router.post("/holidays")
def update_holidays(req: HolidayUpdateRequest):
    store.set_holidays(req.dates)
    return {"message": "节假日更新成功", "holidays": [d.isoformat() for d in store.get_holidays()]}
