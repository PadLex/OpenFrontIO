import asyncio, ssl, json, websockets
import signal
import sys
from typing import Any

from websockets import ServerConnection
from playwright.async_api import async_playwright

CLIENT_URL = "http://localhost:9000"
TOKEN = "Pybot"
TIMEOUT = 60

ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_ctx.load_cert_chain("localhost.pem", "localhost-key.pem")
print("WARNING: using self-signed certificate, for development only")

class Client:
    def __init__(self, orchestrator, ws, client_id):
        self.o = orchestrator
        self.ws = ws
        self.id = client_id
        self.connected = True
        self.pending: dict[str, asyncio.Future[Any]] = {}

    async def listen(self):
        try:
            async for message in self.ws:
                data = json.loads(message)

                if "cid" in data:
                    self.pending[data["cid"]].set_result(data)
                    del self.pending[data["cid"]]
                    continue

                intent = data.get("intent")
                if intent == "ping":
                    await self.on_ping(data)
                else:
                    print("Unknown intent:", intent)
        except websockets.ConnectionClosed:
            print("Client disconnected", self.id)
            self.connected = False


    async def on_ping(self, data):
        print("Ping from", self.id)
        await self.ws.send(json.dumps({"intent": "pong", "timestamp": data["timestamp"]}))

    async def on_turn(self, data):
        print("Turn from", data)

    async def send(self, data):
        # TODO: how do I wait in case connected is False?
        fut = asyncio.get_event_loop().create_future()
        cid = str(id(fut))
        self.pending[cid] = fut
        await self.ws.send(json.dumps({**data, "cid": cid}))
        return await asyncio.wait_for(fut, timeout=TIMEOUT)

    async def createLobby(self):
        print("Creating lobby")
        response = await self.send({"intent": "createLobby"})
        return response["lobbyId"]

    async def joinLobby(self, lobbyId):
        print("Joining lobby", lobbyId)
        assert await self.send({"intent": "joinLobby", "lobbyId": lobbyId})



class Orchestrator:
    def __init__(self):
        self.clients = {}
        self.unassigned = asyncio.Queue()
        self.playwright = None

    async def handler(self, ws: ServerConnection):
        if ws.subprotocol != TOKEN:
            await ws.close(code=1008, reason="bad token")
            return

        # Handshake, expect clientId
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=TIMEOUT)
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

    async def spawn_client(self, headless=True):
        if self.playwright is None:
            self.playwright = await async_playwright().start()

        browser = await self.playwright.chromium.launch(headless=headless)
        page = await browser.new_page()

        await page.goto(CLIENT_URL)

        print("Waiting for client to connect...")
        client = await self.unassigned.get()

        return client


async def main():
    o = Orchestrator()
    server = await websockets.serve(
        o.handler, "localhost", 8765,
        origins=[CLIENT_URL], subprotocols=[TOKEN], ssl=ssl_ctx
    )

    # Example usage:
    print("Server started on wss://localhost:8765")
    client1 = await asyncio.create_task(o.spawn_client(headless=False))
    print("Spawned client:", client1.id)

    client2 = await asyncio.create_task(o.spawn_client(headless=False))
    print("Spawned client:", client2.id)


    lobby_id = await client1.createLobby()
    print("Created lobby:", lobby_id)

    await client2.joinLobby(lobby_id)
    print("Client 2 joined lobby")

    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
