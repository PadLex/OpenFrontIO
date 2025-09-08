import asyncio, ssl, json, websockets

from websockets import ServerConnection

CLIENT_URL = "http://localhost:9000"
TOKEN = "Pybot"
HANDSHAKE_TIMEOUT = 5

ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_ctx.load_cert_chain("localhost.pem", "localhost-key.pem")
print("WARNING: using self-signed certificate, for development only")

class Client:
    def __init__(self, orchestrator, ws, client_id):
        self.o = orchestrator
        self.ws = ws
        self.id = client_id
        self.connected = True

    async def listen(self):
        try:
            async for message in self.ws:            # ordered delivery per connection
                data = json.loads(message)
                intent = data.get("intent")
                if intent == "ping":
                    await self.on_ping(data)
                else:
                    print("Unknown intent:", intent)
        except websockets.ConnectionClosed:
            pass
        finally:
            # cleanup
            self.connected = False
            print("Client disconnected", self.id)

    async def on_ping(self, data):
        print("Ping from", self.id)
        await self.ws.send(json.dumps({"intent": "pong", "timestamp": data["timestamp"]}))

    async def on_turn(self, data):
        print("Turn from", data)

    async def send(self, data):
        # TODO: how do I wait in case connected is False?
        await self.ws.send(json.dumps(data))


class Orchestrator:
    def __init__(self):
        self.clients = {}
        self.unassigned = asyncio.Queue()

    async def handler(self, ws: ServerConnection):
        if ws.subprotocol != TOKEN:
            await ws.close(code=1008, reason="bad token")
            return

        # Handshake, expect clientId
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=HANDSHAKE_TIMEOUT)
            data = json.loads(raw)
            assert data["intent"] == "handshake"
            client_id = data["clientId"]
        except Exception as e:
            print("Handshake error:", e)
            await ws.close(code=1002, reason="handshake failed")
            return

        # Register or reconnect client
        if client_id not in self.clients:
            print(f"New client ID: {client_id}, qsize: {self.unassigned.qsize()}")
            self.clients[client_id] = Client(self, ws, client_id)
            await self.unassigned.put(self.clients[client_id])  # new client available, see spawn_client
        elif not self.clients[client_id].connected:
            print("Reconnecting client ID:", client_id)
            self.clients[client_id].ws = ws
            self.clients[client_id].connected = True
        else:
            print("Client ID already connected:", client_id)
            await ws.close(code=1008, reason="client ID already connected")
            return

        await self.clients[client_id].listen()  # keeps the connection alive

    async def spawn_client(self):
        client = await self.unassigned.get()
        return client


async def main():
    o = Orchestrator()
    server = await websockets.serve(
        o.handler, "localhost", 8765,
        origins=[CLIENT_URL], subprotocols=[TOKEN], ssl=ssl_ctx
    )

    # Example usage:
    client1_task = asyncio.create_task(o.spawn_client())
    print("Server started on wss://localhost:8765")
    client1 = await client1_task
    print("Spawned client:", client1.id)


    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
