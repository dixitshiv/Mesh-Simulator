import time
import uuid


class Span:
    def __init__(self, service, node):
        self.service = service
        self.node = node
        self.start = time.time()
        self.end = None
        self.status = None

    def finish(self, status="ok"):
        self.end = time.time()
        self.status = status

    def to_dict(self):
        duration_ms = round((self.end - self.start) * 1000, 2) if self.end else None
        return {
            "service": self.service,
            "node": self.node,
            "duration_ms": duration_ms,
            "status": self.status
        }


class Trace:
    def __init__(self):
        self.trace_id = str(uuid.uuid4())[:8]
        self.spans = []
        self.start = time.time()

    def add_span(self, service, node):
        span = Span(service, node)
        self.spans.append(span)
        return span

    def to_dict(self):
        total_ms = round((time.time() - self.start) * 1000, 2)
        return {
            "trace_id": self.trace_id,
            "total_ms": total_ms,
            "spans": [s.to_dict() for s in self.spans]
        }