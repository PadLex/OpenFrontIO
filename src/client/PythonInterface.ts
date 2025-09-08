// PythonInterface.ts

import { getPersistentID } from "./Main";

const URL = "wss://localhost:8765";
const TOKEN = "Pybot"; // subprotocol
const PING_INTERVAL_MS = 10_000;

let ws: WebSocket | null = null;
let connectPromise: Promise<WebSocket> | null = null;

/**
 * Establishes a WS connection and resolves only after the Python side
 * acknowledges with { intent: "connect", success: true }.
 */
function initSocket(): Promise<WebSocket> {
  if (ws && ws.readyState === WebSocket.OPEN) return Promise.resolve(ws);
  if (connectPromise) return connectPromise;

  connectPromise = new Promise<WebSocket>((resolve, reject) => {
    const socket = new WebSocket(URL, TOKEN);

    const onOpen = () => {
      console.log("WebSocket opened, sending handshake");
      socket.send(
        JSON.stringify({
          intent: "handshake",
          clientId: getPersistentID(),
        }),
      );

      ws = socket;
      resolve(socket);
    };

    socket.addEventListener("open", onOpen);
    socket.addEventListener("error", (err) => {
      console.error("WebSocket error:", err);
      reject(err);
    });
  });

  return connectPromise;
}

/** Public API: waits for handshake, then sends. */
export async function sendToPyBot(data: any): Promise<void> {
  const socket = await initSocket();
  console.log("Sending to Python:", data);
  socket.send(JSON.stringify(data));
}

export async function subscribeToPyBot(
  callback: (data: any) => void,
): Promise<void> {
  console.log("Subscribing to Python messages");
  const socket = await initSocket();
  socket.addEventListener("message", (e: MessageEvent) => {
    try {
      const msg = JSON.parse((e.data as any).toString());
      callback(msg);
    } catch {
      console.error("Invalid message from Python:", e.data);
    }
  });
}

/** Keep-alive ping (only sends if/when connected). */
setInterval(async () => {
  sendToPyBot({ intent: "ping", timestamp: Date.now() }).then(
    () => console.log("Pinged Python successfully"),
    (err) => console.warn("Ping to Python failed:", err),
  );
}, PING_INTERVAL_MS);

// For debugging log all messages
subscribeToPyBot((data) => {
  console.log("python says:", data);
});
