import httpx
from opentelemetry import trace
from opentelemetry.propagate import inject

from backend.balancer import LoadBalancer
from backend.metrics import (
    requests_total,
    request_latency,
    active_connections,
    node_health,
    failover_total,
)

SERVICES = ["rides", "payments", "maps", "auth", "notifications"]

# Shared async HTTP client; assigned in main.py lifespan before first request
_client: httpx.AsyncClient = None


class Node:
    def __init__(self, node_id, service, base_latency_ms):
        self.node_id = node_id
        self.service = service
        self.healthy = True
        self.active_connections = 0
        self.base_latency_ms = base_latency_ms

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "service": self.service,
            "healthy": self.healthy,
            "active_connections": self.active_connections,
            "base_latency_ms": self.base_latency_ms,
        }


# Fixed per-node base latencies (ms) — deterministic so README docs are accurate
_BASE_LATENCIES = {
    "rides-1": 42,   "rides-2": 87,   "rides-3": 130,
    "payments-1": 28, "payments-2": 95, "payments-3": 61,
    "maps-1": 110,   "maps-2": 19,    "maps-3": 75,
    "auth-1": 55,    "auth-2": 140,   "auth-3": 33,
    "notifications-1": 88, "notifications-2": 22, "notifications-3": 103,
}


class Mesh:
    def __init__(self):
        self.nodes = {}
        self.balancers = {}
        self._init_nodes()

    def _init_nodes(self):
        for service in SERVICES:
            for i in range(1, 4):
                node_id = f"{service}-{i}"
                latency_ms = _BASE_LATENCIES[node_id]
                node = Node(node_id, service, latency_ms)
                self.nodes[node_id] = node
                node_health.labels(node=node_id).set(1)
                active_connections.labels(node=node_id).set(0)
            self.balancers[service] = LoadBalancer("round_robin")

    def set_algorithm(self, service, algorithm):
        if service in self.balancers:
            self.balancers[service] = LoadBalancer(algorithm)

    def set_node_health(self, node_id, healthy):
        if node_id not in self.nodes:
            return False
        node = self.nodes[node_id]
        node.healthy = healthy
        node_health.labels(node=node_id).set(1 if healthy else 0)
        if not healthy:
            # Increments only on explicit operator health-toggle, not on HTTP errors.
            # Transient failures are tracked via mesh_requests_total{status="error"}.
            failover_total.labels(node=node_id).inc()
        return True

    async def route_request(self, source_service, destination_service, proxy_mode, tracer):
        span = tracer.add_span(destination_service, "proxy")
        service_nodes = [n for n in self.nodes.values() if n.service == destination_service]
        balancer = self.balancers.get(destination_service)
        target = balancer.pick(service_nodes) if balancer else None

        if not target:
            span.finish("no_healthy_nodes")
            requests_total.labels(
                source=source_service, destination=destination_service, status="error"
            ).inc()
            return None, "no healthy nodes available"

        target.active_connections += 1
        active_connections.labels(node=target.node_id).set(target.active_connections)

        otel_tracer = trace.get_tracer("mesh.router")
        with otel_tracer.start_as_current_span(f"route.{destination_service}") as otel_span:
            otel_span.set_attribute("node.id", target.node_id)
            otel_span.set_attribute("lb.algorithm", balancer.algorithm)
            otel_span.set_attribute("proxy.mode", proxy_mode)
            headers = {}
            inject(headers)  # injects W3C traceparent; no-op until OTel is initialized in lifespan
            try:
                resp = await _client.post(
                    f"http://{target.node_id}:8080/handle", headers=headers, timeout=5.0
                )
                data = resp.json()
                latency_s = data.get("latency_ms", 50) / 1000.0
                status = data.get("status", "ok")
            except Exception as e:
                target.active_connections -= 1
                active_connections.labels(node=target.node_id).set(target.active_connections)
                span.finish("error")
                requests_total.labels(
                    source=source_service, destination=destination_service, status="error"
                ).inc()
                return target, f"node unreachable: {e}"

        target.active_connections -= 1
        active_connections.labels(node=target.node_id).set(target.active_connections)
        request_latency.labels(destination=destination_service).observe(latency_s)
        requests_total.labels(
            source=source_service, destination=destination_service, status=status
        ).inc()
        span.finish(status)

        if status == "error":
            return target, "simulated request failure"
        return target, None

    def get_all_nodes(self):
        return [n.to_dict() for n in self.nodes.values()]
