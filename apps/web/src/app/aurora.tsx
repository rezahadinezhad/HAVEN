"use client";

import { useEffect, useState } from "react";

// Compositor-driven CSS only: no canvas loop, network traffic or message content.
export function AuroraBackdrop({
  active,
  motion,
}: {
  active: boolean;
  motion: boolean;
}) {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    update();
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return (
    <div
      className="aurora-backdrop"
      aria-hidden="true"
      data-animated={motion && visible}
      data-active={active}
    >
      <div className="aurora-field aurora-field-blue" />
      <div className="aurora-field aurora-field-teal" />
      <div className="aurora-field aurora-field-rose" />
      <div className="aurora-shade" />
    </div>
  );
}

export function TypingIndicator({ label }: { label: string }) {
  return (
    <div
      className="peer-hint typing-indicator"
      role="status"
      aria-live="polite"
    >
      <span className="typing-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span>{label}</span>
    </div>
  );
}
