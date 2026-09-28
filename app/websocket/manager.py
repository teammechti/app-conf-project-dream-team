from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, code: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[code].add(websocket)

    def disconnect(self, code: str, websocket: WebSocket) -> None:
        self.connections[code].discard(websocket)
        if not self.connections[code]:
            self.connections.pop(code, None)

    async def broadcast(self, code: str, event: str) -> None:
        dead: list[WebSocket] = []
        for socket in tuple(self.connections.get(code, set())):
            try:
                await socket.send_json({"event": event})
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(code, socket)


manager = ConnectionManager()
