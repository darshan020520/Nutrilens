import { useEffect, useMemo } from "react";
import { getAccessToken } from "@/core/auth/sessionStore";
import { useNotificationStore } from "@/core/realtime/notificationStore";
import { TrackingSocketClient } from "@/core/realtime/wsClient";

export function useTrackingSocket(enabled = true) {
  const push = useNotificationStore((state) => state.push);
  const client = useMemo(() => new TrackingSocketClient(), []);

  useEffect(() => {
    if (!enabled) return;

    const token = getAccessToken();
    if (!token) return;

    const unsubscribe = client.onEvent((event) => {
      if (!event?.event_type) return;
      push(event);
    });

    client.connect(token);

    return () => {
      unsubscribe();
      client.disconnect();
    };
  }, [client, enabled, push]);
}
