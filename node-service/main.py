import asyncio
import os
import random
import socket

from fastapi import FastAPI, Request
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

app = FastAPI()

BASE_LATENCY_MS = float(os.getenv("BASE_LATENCY_MS", "50"))
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.0"))
NODE_ID = socket.gethostname()

_resource = Resource.create({"service.name": NODE_ID})
_provider = TracerProvider(resource=_resource)
_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://jaeger:4317", insecure=True))
)
trace.set_tracer_provider(_provider)
_tracer = trace.get_tracer(NODE_ID)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/handle")
async def handle(request: Request):
    ctx = extract(dict(request.headers))
    with _tracer.start_as_current_span("node.handle", context=ctx) as span:
        span.set_attribute("node.id", NODE_ID)
        span.set_attribute("base_latency_ms", BASE_LATENCY_MS)
        jitter = random.uniform(-5, 20)
        sleep_ms = max(1, BASE_LATENCY_MS + jitter)
        await asyncio.sleep(sleep_ms / 1000)
        if random.random() < ERROR_RATE:
            span.set_attribute("error", True)
            return {"status": "error", "latency_ms": round(sleep_ms, 2), "node_id": NODE_ID}
        return {"status": "ok", "latency_ms": round(sleep_ms, 2), "node_id": NODE_ID}
