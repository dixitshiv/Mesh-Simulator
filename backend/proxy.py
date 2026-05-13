from backend.mesh import Mesh, SERVICES
from backend.tracer import Trace


class Proxy:
    def __init__(self, mesh):
        self.mesh = mesh

    async def handle(self, source, destination, mode):
        if source not in SERVICES:
            return {"error": f"unknown source service: {source}"}
        if destination not in SERVICES:
            return {"error": f"unknown destination service: {destination}"}
        if source == destination:
            return {"error": "source and destination cannot be the same"}

        trace = Trace()

        if mode == "l4":
            target, err = await self.mesh.route_request(source, destination, "l4", trace)
        else:
            auth_target, auth_err = await self.mesh.route_request(source, "auth", "l7", trace)
            if auth_err:
                return {
                    "trace": trace.to_dict(),
                    "error": f"auth failed: {auth_err}",
                    "mode": mode,
                }
            target, err = await self.mesh.route_request(source, destination, "l7", trace)

        return {
            "trace": trace.to_dict(),
            "destination_node": target.to_dict() if target else None,
            "error": err,
            "mode": mode,
        }
