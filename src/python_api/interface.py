import asyncio, ssl, json, websockets
import signal
import sys
from enum import Enum
from typing import Any, Literal, TypedDict, Callable, List, Sequence, Collection
import numpy as np
from numpy.typing import NDArray

from websockets import ServerConnection
from playwright.async_api import async_playwright

CLIENT_URL = "http://localhost:9000"
TOKEN = "Pybot"
TIMEOUT = 3

ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_ctx.load_cert_chain("localhost.pem", "localhost-key.pem")
print("WARNING: using self-signed certificate, for development only")

NULL_PLAYER_ID = 0


class Player(TypedDict):
    id: int
    x: int
    y: int
    type: Literal["human", "nation", "bot"]
    troops: int
    gold: int
    tiles: int
    is_traitor: bool

    # TODO Diplomacy
    # relationship: Literal["team", "ally", "they_propose", "we_propose", "enemy"]
    # alliance_timer: float

    # TODO Structures
    # cities: int
    # ports: int
    # factories: int
    # defence_posts: int
    # missile_silos: int
    # sam_launchers: int
    # warships: int

class State(TypedDict):
    game_started: bool
    is_spawn_phase: bool
    turn: int
    my_id: str

    players: List[Player]

    # Map info
    width: int
    height: int
    skip: int  # distance between sampled tiles
    traversal_cost: NDArray[np.int_]  # 2D array
    is_land: NDArray[np.bool_]  # 2D array
    ownership: NDArray[np.int_]  # 2D array

    # TODO: Entities info

class BaseAction(TypedDict):
    action: str
    x: int
    y: int

class Spawn(BaseAction):
    action: Literal["spawn"]

class Attack(BaseAction):
    action: Literal["attack"]
    ratio: float

class BoatAttack(BaseAction):
    action: Literal["boat_attack"]
    ratio: float

class Build(BaseAction):
    action: Literal["build"]
    structure: Literal["city", "port", "factory", "defence_post", "missile_silo", "sam_launcher"]

class Place(BaseAction):
    action: Literal["place"]
    structure: Literal["warship", "atomic_bomb", "hydrogen_bomb", "mirv"]

Action = Spawn | Attack | BoatAttack | Build | Place

class ClientSessionAsync:
    def __init__(self, orchestrator, ws, client_id, skip=4):
        self._o = orchestrator
        self._ws = ws
        self._id = client_id
        self._connection_promise = None
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self.initial_state = None
        self.skip = skip

    async def _listen(self):
        try:
            async for message in self._ws:
                data = json.loads(message)

                if "cid" in data:
                    self._pending[data["cid"]].set_result(data)
                    del self._pending[data["cid"]]
                    continue

                intent = data.get("intent")
                if intent == "ping":
                    await self._on_ping(data)
                else:
                    print("Unknown intent:", intent)
        except websockets.ConnectionClosed:
            print("Client disconnected", self._id)
            self._connection_promise = asyncio.get_event_loop().create_future()

    async def _on_ping(self, data):
        print("Ping from", self._id)
        await self._ws.send(json.dumps({"intent": "pong", "timestamp": data["timestamp"]}))

    async def _send(self, data):
        if self._connection_promise:
            await self._connection_promise

        try:
            # Expect a response with the same cid
            fut = asyncio.get_event_loop().create_future()
            cid = str(id(fut))
            self._pending[cid] = fut
            await self._ws.send(json.dumps({**data, "cid": cid}))
            response = await asyncio.wait_for(fut, timeout=TIMEOUT)
            del response["cid"]
            return response
        except (asyncio.TimeoutError, websockets.ConnectionClosed) as e:
            print("Error sending to", self._id, ":", e)
            print("Closing connection to", self._id)
            await self._ws.close(code=1002, reason="timeout")

            self._connection_promise = asyncio.get_event_loop().create_future()
            await self._connection_promise
            return await self._send(data)  # retry

    async def createLobby(self):
        print("Creating lobby")
        response = await self._send({"intent": "createLobby"})
        return response["lobbyId"]

    async def joinLobby(self, lobbyId):
        print("Joining lobby", lobbyId)
        await self._send({"intent": "joinLobby", "lobbyId": lobbyId})

    async def startGame(self):
        await self._send({"intent": "startGame"})

    async def _saveStaticState(self):
        self.initial_state = await self._send({"intent": "getStaticState", "skip": self.skip})

    async def getState(self) -> State:
        if self.initial_state is None:
            await self._saveStaticState()

        response = await self._send({"intent": "getState"})
        return {**self.initial_state, **response}

    async def act(self, action: Action):
        if self.initial_state is None:
            await self._saveStaticState()

        print("Acting:", action)
        response = await self._send({"intent": "act", **action})
        return response["success"]


class SessionManagerAsync:
    def __init__(self):
        self._clients = {}
        self._unassigned = asyncio.Queue()

    async def serve(self, host="localhost", port=8765):
        return await websockets.serve(
            self._handler, host, port,
            max_size=None,
            origins=[CLIENT_URL], subprotocols=[TOKEN], ssl=ssl_ctx
        )

    async def _handler(self, ws: ServerConnection):
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
        if client_id not in self._clients:
            print(f"New client ID: {client_id}, qsize: {self._unassigned.qsize()}")
            self._clients[client_id] = ClientSessionAsync(self, ws, client_id)
            await self._unassigned.put(self._clients[client_id])  # new client available, see spawn_client
        elif self._clients[client_id]._connection_promise:
            print("Reconnecting client ID:", client_id)
            self._clients[client_id]._ws = ws
            self._clients[client_id]._connection_promise.set_result(True)
            self._clients[client_id]._connection_promise = None
        else:
            print("Client ID already connected:", client_id)
            await ws.close(code=1008, reason="client ID already connected")
            return

        await self._clients[client_id]._listen()  # keeps the connection alive

    async def expect_client(self):
        # print("Waiting for client to connect...")
        return await self._unassigned.get()


class SynchronousAPI:
    def __init__(self, turn_length=0.1):
        self._min_turn_time = turn_length
        self._on_state_callbacks = []
        self._client_modes = []
        self._playwright = None

    def register_agent(self, on_state: Callable[[State], Collection[Action]], mode: Literal["headless", "window", "debug"] = "headless"):
        assert mode in ("headless", "window", "debug"), "mode must be 'headless', 'window' or 'debug'"
        self._on_state_callbacks.append(on_state)
        self._client_modes.append(mode)

    async def _game_loop(self):
        # Todo parallelize every client loop
        session = SessionManagerAsync()
        server = await session.serve()

        assert len(self._on_state_callbacks) >= 2, "At least two agents must be registered"

        clients = []
        for mode in self._client_modes:
            if mode == "debug":
                print("Connect your client in the browser at", CLIENT_URL)
            else:
                await self.start_browser(headless=(mode == "headless"))
            clients.append(await asyncio.create_task(session.expect_client()))

        lobby_id = await clients[0].createLobby()
        print("Created lobby:", lobby_id)
        for client in clients[1:]:
            await client.joinLobby(lobby_id)

        await clients[0].startGame()
        print("Game started")

        while True:
            start_time = asyncio.get_event_loop().time()
            print("New turn")

            for client, callback in zip(clients, self._on_state_callbacks):
                print("Getting state for client", client._id)
                state = await client.getState()
                print("State received, calling bot")
                actions = callback(state)
                outcome = [await client.act(action) for action in actions]

            end_time = asyncio.get_event_loop().time()
            await asyncio.sleep(max(.0, self._min_turn_time - (end_time - start_time)))

    async def start_browser(self, headless=True):
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        browser = await self._playwright.chromium.launch(headless=headless)
        page = await browser.new_page()

        await page.goto(CLIENT_URL)

    def play(self):
        asyncio.run(self._game_loop())
