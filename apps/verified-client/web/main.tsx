import React from "react";
import { createRoot } from "react-dom/client";
import Haven from "../../web/src/app/ui";
import { configureClientDelivery } from "../../web/src/lib/client-delivery";
import "../../web/src/app/style.css";
import "../../web/src/app/chat.css";
import "./fonts.css";
async function start() {
  if (
    !isSecureContext ||
    location.protocol !== "https:" ||
    window.top !== window.self
  )
    throw new Error("Trusted HTTPS required");
  const response = await fetch("/client-config.json", {
    cache: "no-store",
    credentials: "omit",
  });
  if (!response.ok)
    throw new Error("Independent client configuration unavailable");
  configureClientDelivery(await response.json());
  createRoot(document.getElementById("root")!).render(<Haven />);
}
void start().catch(() => {
  document.body.textContent =
    "HAVEN could not start its verified client. Check the trusted launcher and local HTTPS connection.";
});
