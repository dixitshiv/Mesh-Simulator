import random


class LoadBalancer:
    def __init__(self, algorithm="round_robin"):
        self.algorithm = algorithm
        self._rr_index = 0

    def pick(self, nodes):
        healthy = [n for n in nodes if n.healthy]
        if not healthy:
            return None

        if self.algorithm == "round_robin":
            node = healthy[self._rr_index % len(healthy)]
            self._rr_index += 1
            return node

        if self.algorithm == "least_connections":
            return min(healthy, key=lambda n: n.active_connections)

        if self.algorithm == "random":
            return random.choice(healthy)

        return healthy[0]