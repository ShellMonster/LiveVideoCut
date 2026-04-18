import { useEffect, useRef, useCallback, useState } from "react";
import { useTaskStore } from "@/stores/taskStore";

function resolveWebSocketBase(): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }

  return "ws://localhost:5537";
}

const WS_BASE = resolveWebSocketBase();

interface WSMessage {
  state: string;
  step?: string;
  message?: string;
}

export function useTaskProgress(taskId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [connected, setConnected] = useState(false);
  const { setStatus, setError, setCurrentState } = useTaskStore();

  const connect = useCallback(() => {
    if (!taskId) return;

    const ws = new WebSocket(`${WS_BASE}/ws/tasks/${taskId}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (event) => {
      const data: WSMessage = JSON.parse(event.data);
      setCurrentState(data.state);

      if (data.state === "COMPLETED") {
        setStatus("done");
      } else if (data.state === "ERROR") {
        setError(data.message || "处理失败");
      } else {
        setStatus("processing");
      }
    };

    ws.onclose = (event) => {
      setConnected(false);
      wsRef.current = null;

      if (event.code !== 4040 && event.code !== 1000) {
        reconnectRef.current = setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [taskId, setStatus, setError, setCurrentState]);

  useEffect(() => {
    connect();

    return () => {
      clearTimeout(reconnectRef.current);
      wsRef.current?.close(1000, "Component unmounted");
      wsRef.current = null;
    };
  }, [connect]);

  return { connected };
}
