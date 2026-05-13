import asyncio
import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel

import backend.mesh as mesh_module
from backend.mesh import Mesh, SERVICES
from backend.proxy import Proxy
from backend.metrics import get_metrics
from backend.otel import init_otel


@asynccontextmanager
async def lifespan(app: FastAPI):
    mesh_module._client = httpx.AsyncClient()
    init_otel("mesh-router")
    yield
    await mesh_module._client.aclose()


app = FastAPI(lifespan=lifespan)
mesh = Mesh()
proxy = Proxy(mesh)


class RequestPayload(BaseModel):
    source: str
    destination: str
    mode: str = "l4"


class HealthPayload(BaseModel):
    node_id: str
    healthy: bool


class AlgorithmPayload(BaseModel):
    service: str
    algorithm: str


@app.get("/api/services")
def get_services():
    return {"services": SERVICES}


@app.get("/api/nodes")
def get_nodes():
    return {"nodes": mesh.get_all_nodes()}


@app.post("/api/request")
async def send_request(payload: RequestPayload):
    result = await proxy.handle(payload.source, payload.destination, payload.mode)
    return result


@app.post("/api/node/health")
def set_health(payload: HealthPayload):
    ok = mesh.set_node_health(payload.node_id, payload.healthy)
    if not ok:
        return {"error": "node not found"}
    return {"node_id": payload.node_id, "healthy": payload.healthy}


@app.post("/api/algorithm")
def set_algorithm(payload: AlgorithmPayload):
    mesh.set_algorithm(payload.service, payload.algorithm)
    return {"service": payload.service, "algorithm": payload.algorithm}


@app.get("/metrics")
def metrics():
    data, content_type = get_metrics()
    return Response(content=data, media_type=content_type)


@app.websocket("/ws/metrics")
async def metrics_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            nodes = mesh.get_all_nodes()
            payload = json.dumps({"nodes": nodes})
            await websocket.send_text(payload)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


app.mount("/static", StaticFiles(directory="frontend"), name="frontend")


@app.get("/")
def serve_index():
    return FileResponse("frontend/index.html")
