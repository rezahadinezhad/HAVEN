"use client";

import { useEffect, useState } from "react";

export function DeviceUnlockRoute({
  hostname,
  t,
}: {
  hostname: string;
  t: (text: string) => string;
}) {
  const [address, setAddress] = useState("");
  useEffect(() => {
    if (
      !hostname ||
      hostname.length > 253 ||
      !hostname
        .split(".")
        .every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))
    )
      return;
    const url = new URL(location.origin);
    url.hostname = hostname;
    if (
      url.protocol === "https:" &&
      url.hostname === hostname &&
      url.origin !== location.origin &&
      !/^\d+(?:\.\d+){3}$/.test(hostname)
    )
      setAddress(url.origin + "/");
  }, [hostname]);
  if (!address) return null;
  return (
    <p className="device-unlock-route">
      <a href={address} target="_blank" rel="noopener noreferrer">
        {t("Open the device-unlock address")} ↗
      </a>
      <small>
        {t(
          "Sign in there, set up this browser, and approve it from an existing trusted browser. Your current history stays here.",
        )}
      </small>
    </p>
  );
}
