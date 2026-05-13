from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

requests_total = Counter(
    'mesh_requests_total',
    'Total requests routed through the mesh',
    ['source', 'destination', 'status']
)

request_latency = Histogram(
    'mesh_request_latency_seconds',
    'Request latency in seconds',
    ['destination'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
)

active_connections = Gauge(
    'mesh_active_connections',
    'Currently active connections per node',
    ['node']
)

node_health = Gauge(
    'mesh_node_health',
    '1 if node is healthy, 0 if down',
    ['node']
)

failover_total = Counter(
    'mesh_failover_total',
    'Total number of failover events',
    ['node']
)


def get_metrics():
    return generate_latest(), CONTENT_TYPE_LATEST