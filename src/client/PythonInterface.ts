// PythonInterface.ts
import { getPersistentID } from "./Main";

const URL = "wss://localhost:8765";
const TOKEN = "Pybot"; // subprotocol
const HANDSHAKE_TIMEOUT_MS = 3_000;
const PING_INTERVAL_MS = 3_000;

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
    ws = socket;
    let settled = false;

    const genericLogger = (e: MessageEvent) => {
      try {
        const msg = JSON.parse((e.data as any).toString());
        console.log("python says:", msg);
      } catch {
        console.error("Invalid message from Python:", e.data);
      }
    };

    const onOpen = () => {
      console.log("WebSocket opened, sending handshake");
      socket.send(
        JSON.stringify({
          clientId: getPersistentID(),
          intent: "handshake",
        }),
      );
    };

    const onHandshakeMessage = (e: MessageEvent) => {
      try {
        const msg = JSON.parse((e.data as any).toString());
        console.log("Received message during handshake:", msg);
        if (msg.intent === "handshake" && msg.success) {
          console.log("Python interface initialized");
          settled = true;

          // Post-handshake listeners
          socket.addEventListener("message", genericLogger);
          socket.addEventListener("close", () => {
            console.warn("WebSocket closed. Will reconnect on next use.");
            ws = null;
            connectPromise = null;
          });

          resolve(socket);
        } else {
          // Not the handshake yet; still log it
          console.log("python says (pre-handshake):", msg);
        }
      } catch {
        console.error("Invalid message from Python:", e.data);
      }
    };

    const onError = (err: Event) => {
      console.error("WebSocket error:", err);
    };

    socket.addEventListener("open", onOpen);
    socket.addEventListener("message", onHandshakeMessage);
    socket.addEventListener("error", onError, { once: true });

    // Guard against a handshake that never arrives
    const timer = setTimeout(() => {
      if (!settled) {
        console.error("Handshake timeout");
      }
    }, HANDSHAKE_TIMEOUT_MS);
  });

  return connectPromise;
}

/** Public API: waits for handshake, then sends. */
export async function sendUpdate(data: any): Promise<void> {
  const socket = await initSocket();
  console.log("Sending to Python:", data);
  socket.send(JSON.stringify(data));
}

/** Keep-alive ping (only sends if/when connected). */
setInterval(async () => {
  sendUpdate({ intent: "ping", timestamp: Date.now() }).then(
    () => console.log("Pinged Python successfully"),
    (err) => console.warn("Ping to Python failed:", err),
  );
}, PING_INTERVAL_MS);
