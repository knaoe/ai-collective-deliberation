"""
MAGI API Server
================
FastAPI server exposing the MAGI Consensus Engine via REST and WebSocket.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from magi_engine.engine import MAGIEngine


# Global engine instance
engine: Optional[MAGIEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the MAGI engine on startup."""
    global engine
    engine = MAGIEngine()
    print("\n" + "=" * 60)
    print("  MAGI SYSTEM ONLINE")
    print("  MELCHIOR ... READY (科学者)")
    print("  BALTHASAR ... READY (母親)")
    print("  CASPER ..... READY (女)")
    print("=" * 60 + "\n")
    yield
    print("\nMAGI SYSTEM SHUTTING DOWN...")


app = FastAPI(
    title="MAGI Consensus Engine",
    description="Multi-Aspectual General Intelligence -- Three minds, one judgment.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DeliberationRequest(BaseModel):
    question: str


class DeliberationResponse(BaseModel):
    success: bool
    deliberation: dict
    cost: dict


# -------------------------------------------------------------------
# REST Endpoints
# -------------------------------------------------------------------

@app.post("/magi/deliberate", response_model=DeliberationResponse)
async def deliberate(request: DeliberationRequest):
    """Submit a question for MAGI deliberation."""
    if engine is None:
        return DeliberationResponse(
            success=False, deliberation={}, cost={}
        )

    # Run synchronous deliberation in a thread pool to not block
    loop = asyncio.get_event_loop()
    delib = await loop.run_in_executor(
        None, engine.deliberate, request.question
    )

    return DeliberationResponse(
        success=True,
        deliberation=delib.to_dict(),
        cost=delib.cost.to_dict() if delib.cost else {},
    )


@app.get("/magi/history")
async def get_history():
    """Get past deliberations."""
    if engine is None:
        return {"deliberations": [], "count": 0}

    return {
        "deliberations": [d.to_dict() for d in engine.history],
        "count": len(engine.history),
    }


@app.get("/magi/status")
async def get_status():
    """Get MAGI system status."""
    if engine is None:
        return {"status": "offline", "personas": []}

    from magi_engine.personas import ALL_PERSONAS

    return {
        "status": "online",
        "system": "MAGI Consensus Engine v1.0.0",
        "personas": [
            {
                "name": p.name,
                "title": p.title,
                "title_jp": p.title_jp,
                "color": p.color,
            }
            for p in ALL_PERSONAS
        ],
        "model": engine.deployment,
        "deliberations_completed": len(engine.history),
        "cost_summary": engine.cost_tracker.get_cumulative_summary(),
    }


# -------------------------------------------------------------------
# WebSocket Streaming
# -------------------------------------------------------------------

@app.websocket("/magi/deliberate/stream")
async def deliberate_stream(websocket: WebSocket):
    """Stream a MAGI deliberation in real-time via WebSocket."""
    await websocket.accept()

    try:
        # Wait for the question
        data = await websocket.receive_json()
        question = data.get("question", "")

        if not question:
            await websocket.send_json({
                "event": "error",
                "data": {"message": "No question provided"},
            })
            await websocket.close()
            return

        if engine is None:
            await websocket.send_json({
                "event": "error",
                "data": {"message": "MAGI engine not initialized"},
            })
            await websocket.close()
            return

        # Stream events
        async for event_type, event_data in engine.deliberate_async(question):
            await websocket.send_json({
                "event": event_type,
                "data": event_data,
            })

        await websocket.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "event": "error",
                "data": {"message": str(e)},
            })
            await websocket.close()
        except Exception:
            pass


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------

def main():
    """Run the MAGI API server."""
    import uvicorn
    uvicorn.run(
        "magi_engine.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
