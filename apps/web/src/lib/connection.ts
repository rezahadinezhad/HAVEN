import { serverHint } from "./ws";
// WebSocket hints are optional. The authoritative source is authenticated HTTP delta synchronization.
export function connectionLoop(
  sync: () => Promise<void>,
  status: (online: boolean) => void,
  typingHint?: (cid: string) => void,
  presence?: {
    conversation: () => string | undefined;
    received: (cid: string) => void;
  },
) {
  let stopped = false,
    socket: WebSocket | undefined,
    retry: ReturnType<typeof setTimeout> | undefined,
    poll: ReturnType<typeof setTimeout> | undefined,
    heartbeat: ReturnType<typeof setInterval> | undefined,
    attempt = 0,
    running = false;
  const tick = async () => {
    if (stopped || running) return;
    running = true;
    try {
      await sync();
      status(true);
    } catch (e) {
      status(false);
      throw e;
    } finally {
      running = false;
    }
  };
  const periodic = async () => {
    try {
      await tick();
    } catch {}
    if (!stopped) poll = setTimeout(periodic, 5000 + Math.random() * 1000);
  };
  const announcePresence = () => {
    const cid = presence?.conversation();
    if (cid && !document.hidden && socket?.readyState === WebSocket.OPEN)
      socket.send(
        JSON.stringify({
          v: 1,
          kind: "ephemeral.presence",
          conversation_id: cid,
        }),
      );
  };
  const connect = () => {
    if (stopped) return;
    socket = new WebSocket(
      `${location.origin.replace("https:", "wss:")}/ws/v1`,
    );
    socket.onopen = () => {
      attempt = 0;
      socket?.send(JSON.stringify({ v: 1, kind: "resume" }));
      announcePresence();
      heartbeat = setInterval(() => {
        if (socket?.readyState === WebSocket.OPEN)
          socket.send(JSON.stringify({ v: 1, kind: "heartbeat" }));
        announcePresence();
      }, 20000);
    };
    socket.onmessage = (e) => {
      try {
        if (typeof e.data !== "string" || e.data.length > 2048) {
          socket?.close(1009);
          return;
        }
        const d = serverHint(JSON.parse(e.data));
        if (!d) {
          socket?.close(1008);
          return;
        }
        if (
          d.v === 1 &&
          d.kind === "ephemeral.typing" &&
          typeof d.conversation_id === "string"
        )
          typingHint?.(d.conversation_id);
        if (d.kind === "ephemeral.presence")
          presence?.received(d.conversation_id);
        if (d.v === 1 && d.kind === "sync.required")
          void tick().catch(() => {});
      } catch {}
    };
    socket.onerror = () => socket?.close();
    socket.onclose = () => {
      clearInterval(heartbeat);
      if (!stopped)
        retry = setTimeout(
          connect,
          Math.min(30000, 1000 * 2 ** Math.min(attempt++, 5)) *
            (0.75 + Math.random() / 2),
        );
    };
  };
  const online = () => void tick().catch(() => {});
  let lastTyping = 0;
  const typing = (e: Event) => {
    const cid = (e as CustomEvent<string>).detail;
    if (Date.now() - lastTyping < 3000 || socket?.readyState !== WebSocket.OPEN)
      return;
    lastTyping = Date.now();
    socket.send(
      JSON.stringify({ v: 1, kind: "ephemeral.typing", conversation_id: cid }),
    );
  };
  window.addEventListener("haven:typing", typing);
  window.addEventListener("online", online);
  document.addEventListener("visibilitychange", announcePresence);
  connect();
  void periodic();
  return () => {
    stopped = true;
    clearTimeout(retry);
    clearTimeout(poll);
    clearInterval(heartbeat);
    socket?.close();
    window.removeEventListener("online", online);
    window.removeEventListener("haven:typing", typing);
    document.removeEventListener("visibilitychange", announcePresence);
  };
}
