from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import PORT
from app.modules.order.router import router as order_router
from app.modules.line.router import router as line_router
from app.modules.schedule.router import router as schedule_router
from app.modules.gantt.router import router as gantt_router
from app.modules.replan.router import router as replan_router
from app.modules.stats.router import router as stats_router

app = FastAPI(
    title="生产排产系统",
    description="基于 FastAPI + OR-Tools 的智能生产排产系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(order_router)
app.include_router(line_router)
app.include_router(schedule_router)
app.include_router(gantt_router)
app.include_router(replan_router)
app.include_router(stats_router)


@app.get("/")
def root():
    return {
        "name": "生产排产系统",
        "version": "1.0.0",
        "port": PORT,
        "modules": ["order", "line", "schedule", "gantt", "replan", "stats"],
    }


@app.get("/health")
def health():
    return {"status": "ok"}
