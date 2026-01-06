"""Live monitor websocket and state endpoints."""

from fastapi import APIRouter, WebSocket
from apps.backend.src.common.websocket import ConnectionManager
from apps.backend.src.api.schemas import live as schemas
from apps.backend.src.usecases import live_toggle, live_state

router = APIRouter(prefix="/live", tags=["live"])
manager = ConnectionManager()


@router.websocket("/ws/monitor")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"echo: {data}")
    except Exception:
        manager.disconnect(websocket)


@router.post("/toggle", response_model=schemas.LiveState)
async def toggle(payload: schemas.LiveState):
    return schemas.LiveState(**live_toggle.execute(payload.enabled))


@router.get("/state", response_model=schemas.LiveState)
async def state():
    return schemas.LiveState(**live_state.execute())
