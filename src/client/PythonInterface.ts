// PythonInterface.ts

import { getPersistentID } from "./Main";

const URL = "wss://localhost:8765";
const TOKEN = "Pybot"; // subprotocol
const PING_INTERVAL_MS = 60_000;

let ws: WebSocket | null = null;
let connectPromise: Promise<WebSocket> | null = null;
const intentListeners: { [key: string]: (data: any) => void } = {};
const missedMessages: any[] = [];

/**
 * Establishes a WS connection and resolves only after the Python side
 * acknowledges with { intent: "connect", success: true }.
 */
export function initSocket(): Promise<WebSocket> {
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
    socket.addEventListener("message", (e: MessageEvent) => {
      try {
        const data = JSON.parse((e.data as any).toString());
        console.log("Received from Python:", data);
        if (data.intent in intentListeners) {
          intentListeners[data.intent](data);
        } else {
          console.warn("No listener for intent:", data.intent);
          missedMessages.push(data);
        }
      } catch {
        console.error("Invalid message from Python:", e.data);
      }
    });
  });

  return connectPromise;
}

/** Public API: waits for handshake, then sends. */
export async function sendToPyBot(data: any): Promise<void> {
  const socket = await initSocket();
  console.log("Sending to Python:", data);
  socket.send(
    JSON.stringify(data, (_key, v) =>
      typeof v === "bigint" ? v.toString() : v,
    ),
  );
}

export async function subscribeToPyBot(
  intent: string,
  callback: (data: any) => void,
): Promise<void> {
  console.log("Subscribing to intent:", intent);
  intentListeners[intent] = callback;
  // Process any missed messages for this intent
  for (let i = missedMessages.length - 1; i >= 0; i--) {
    if (missedMessages[i].intent === intent) {
      callback(missedMessages[i]);
      missedMessages.splice(i, 1);
    }
  }
}

/** Keep-alive ping (only sends if/when connected). */
setInterval(async () => {
  sendToPyBot({ intent: "ping", timestamp: Date.now() }).then(
    () => console.log("Pinged Python successfully"),
    (err) => console.warn("Ping to Python failed:", err),
  );
}, PING_INTERVAL_MS);
