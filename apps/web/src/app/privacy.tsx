"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { components } from "@/lib/generated/schema";

export function ServerPrivacy({ t }: { t: (text: string) => string }) {
  const [policy, setPolicy] = useState<
    components["schemas"]["PrivacyPolicy"] | null
  >(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setError(false);
    void api<components["schemas"]["PrivacyPolicy"]>("privacy-policy")
      .then((value) => {
        if (active) setPolicy(value);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [attempt]);
  return (
    <section
      className="card server-privacy"
      aria-labelledby="server-privacy-title"
    >
      <h2 id="server-privacy-title">{t("What stays on the server")}</h2>
      <p>
        {t(
          "Messages and files are encrypted on your device. The server does not hold your message decryption keys.",
        )}
      </p>
      {error ? (
        <div role="status">
          <p>
            {t(
              "Retention policy unavailable. Reconnect to check the server settings.",
            )}
          </p>
          <button onClick={() => setAttempt((value) => value + 1)}>
            {t("Try again")}
          </button>
        </div>
      ) : !policy ? (
        <p role="status">{t("Loading retention policy…")}</p>
      ) : (
        <dl>
          <div>
            <dt>{t("Delivered messages")}</dt>
            <dd>
              {t(
                "Encrypted payloads are removed after every eligible active device syncs, with a {hours}-hour retry window.",
              ).replace(
                "{hours}",
                String(policy.delivered_ciphertext_grace_hours),
              )}
            </dd>
          </div>
          <div>
            <dt>{t("Offline recipients")}</dt>
            <dd>
              {t(
                "Undelivered encrypted messages stay available. Keep a recovery kit: the server cannot rebuild a lost vault.",
              )}
            </dd>
          </div>
          <div>
            <dt>{t("Files and voice notes")}</dt>
            <dd>
              {t(
                "Available for up to {days} days. View-once files are removed sooner after all openings finish.",
              ).replace("{days}", String(policy.attachment_days))}
            </dd>
          </div>
          <div>
            <dt>{t("Security records")}</dt>
            <dd>
              {t(
                "Security audit records expire after {days} days. Expired sessions and used invitations are cleaned automatically.",
              ).replace("{days}", String(policy.audit_days))}
            </dd>
          </div>
        </dl>
      )}
      <details>
        <summary>{t("Understand the remaining limits")}</summary>
        <p>
          {t(
            "Accounts, public device keys, conversation membership and signed delivery proofs remain visible to the server. This is not anonymous messaging.",
          )}
        </p>
        <p>
          {t(
            "The connection server can see your IP while you connect. Request logs are disabled in the supplied deployment; a compromised host can still observe traffic.",
          )}
        </p>
        <p>
          {t(
            "Deletion removes live database records, not copies in older backups, replicas or recipients’ devices. Cleanup runs periodically.",
          )}
        </p>
        <p>
          {t(
            "A compromised website can serve altered browser code that steals keys when you unlock. Independent security review is still pending.",
          )}
        </p>
      </details>
    </section>
  );
}
