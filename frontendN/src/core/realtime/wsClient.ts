import type { TrackingEvent } from "@/core/api/types";

type TrackingHandler = (event: TrackingEvent) => void;

export class TrackingSocketClient {
  private socket: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private reconnectAttempts = 0;
  private handlers = new Set<TrackingHandler>();

  connect(token: string) {
    if (this.socket || !token) return;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = "localhost:8000";
    const url = `${protocol}://${host}/ws/tracking?token=${token}`;

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as TrackingEvent;
        this.handlers.forEach((handler) => handler(event));
      } catch {
        // Ignore malformed messages.
      }
    };

    this.socket.onclose = () => {
      this.socket = null;
      this.scheduleReconnect(token);
    };

    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.socket?.close();
    this.socket = null;
  }

  onEvent(handler: TrackingHandler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  private scheduleReconnect(token: string) {
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 10000);
    this.reconnectAttempts += 1;

    this.reconnectTimer = window.setTimeout(() => {
      this.connect(token);
    }, delay);
  }
}
