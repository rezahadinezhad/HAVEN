# User onboarding — prepared evaluation only

Current release is BLOCKED for real emergency onboarding. The following workflow is exercised locally; physical phones, trusted public IP hosting and independent review are still required.

1. Obtain the exact HTTPS IP URL and, for private PKI, the public root fingerprint through an independent trusted channel. Verify before installing. Never bypass a certificate warning. A bookmark is enough; no PWA install or foreign login is required.
2. Open **Start a chat** (or the **+** in Conversations). Choose **Generate a secure passphrase**, then reveal or copy it and save it privately. Check **I’ve saved my passphrase somewhere private** before continuing. **Generate another** creates a different value and resets that confirmation. You can also choose **Use my own passphrase**, enter at least 20 characters, and confirm it. This browser saves your keys locally; if a vault already exists, the guide asks you to unlock it instead. The unlock passphrase must differ from your account password. A first browser proves possession of its own keys; an additional browser needs approval from an existing trusted device.
3. Choose **Invite a friend** to create a private, one-use signup link valid for 24 hours. Approved members may issue three invitations per UTC day, with at most three pending. The administrator can disable member issuance or pause all invitations. The guide explains the restriction and lets you revoke your own pending invitations. An administrator can also issue an invitation through Operator console. Inviting does not grant an admin role.
4. Send the full link privately. A new friend chooses their username/password, then sets up their browser. For someone who already has an account, choose **Share my friend link** instead. If your friend sends you their link, choose **I have a friend link** and paste it. There is no public user directory or username lookup. The invitation token and public friend card live in the URL fragment and are removed from the address bar after loading; a live token grants one signup, so do not publish it.
5. Compare the **entire security code** with your friend in person or through another trusted channel. Each person finds their own code under **Start a chat → My security code**. A link/QR alone does not verify its sender. Name your friend, explicitly confirm the comparison, then choose **Verify and continue**. HAVEN creates the direct chat automatically. The other person opens the incoming conversation and compares/confirms your code before reading or replying. An unexpected changed identity is blocked in this guide; stop and investigate in People & trust. Advanced device/group creation remains available separately.

**This preview is local:** `https://127.0.0.1:8445/` works on this computer only. A friend on another computer cannot use your loopback URL. Two browser profiles on this computer can evaluate the flow. Real remote use needs a reachable raw-IP HTTPS server and independently verified certificate trust on both devices, plus the outstanding release qualifications. Never bypass TLS warnings or expose the local integration service as production.

6. For another browser/device on the same account, sign in, create a distinct device vault, compare its fingerprint on the existing device, approve enrollment, then complete enrollment on the new browser. An owner/moderator explicitly adds it to each group. Devices on a separately trusted standby origin must be prepared the same way before an outage.
7. Download an encrypted recovery kit and store its separate random key elsewhere. The original account recovery authority must be backed up before losing every device. A later device without that authority exports history only. Recovery requires a separate browser profile, the kit and its key; it revokes old identities and contacts must verify/re-add the fresh identity. Existing unlocked approved devices can import saved history locally without replacing their live keys.
8. Queued means stored locally, server_accepted means durably accepted, recipient_synced means a recipient device synchronized. It never means a human read it. Read receipts are optional encrypted events; typing exposes activity metadata and is opt-in.
9. Download/open attachments only when you trust their sender/content. Files can be malicious despite encryption. Voice permission is requested explicitly; unsupported browser states must be treated as unavailable. No server can inspect/transcode/decrypt private media.
10. During disconnection, cached unlocked history and encrypted pending sends stay on this browser while storage persists. Retry uses trusted HTTPS only. No route means no remote delivery. Keep a printed independently verified endpoint/CA incident card; an invalid TLS page cannot reliably diagnose itself from JavaScript.

Edit/delete are authenticated events, not guaranteed erasure of recipients' copies. Explicit plaintext local export is sensitive. Lock/logout/timeout clears active worker state as far as browser execution permits, but browser GC is not guaranteed secure erasure. A compromised origin, device or extension can disclose plaintext and keys.

If authentication expires or connectivity prevents logout, the interface still locks locally and permits signing in again. It clearly reports unconfirmed server revocation; do not assume remote sessions were revoked during an outage. Existing encrypted vault/outbox data remains preserved.

Presence is off by default. If enabled, a visible selected conversation sends an ephemeral online hint; it expires after 50 seconds and is not proof that a person read anything. Typing is a separate five-second hint; read receipts are separately opt-in. Default group icons are bundled glyphs; group titles travel as encrypted events. Custom group photographs are not supported in this release.

A backup address has separate browser keys and storage. Before an outage, sign in there, approve the new device from a trusted device, verify fingerprints, and have it added to each group. Check messaging there while the primary is available. The operator must have configured the verified preparation bridge. Merely bookmarking the backup cannot recover lost keys. Never copy an old live ratchet snapshot to make the switch.

The optional generator is available only for a new local vault. Generated secrets stay in browser memory until setup encrypts the vault; they are not sent to the server or stored in plaintext browser storage. Clipboard copying is explicit, and clipboard history/sync or another app may retain what you copy. If copying is denied, choose Show passphrase and record it privately. A new generated value cannot recover an existing vault. Your account password and recovery-kit key have separate roles. See ADR 0008 for the security boundaries.

## Easier vault unlock

On the current **IP address**, save the vault passphrase as a **separate** password-manager item. The unlock form supplies autofill hints; whether your manager asks for fingerprint, face or device PIN depends on that browser/device. HAVEN does not store an unencrypted automatic-unlock token. A refresh or browser restart locks the vault again, and the account session may separately require login.

If your operator has also prepared an exact, trusted HTTPS **hostname** and your browser supports WebAuthn PRF, unlock once with the vault passphrase and open **Settings → Unlock with this device → Set up device unlock**. Your device will require verification. After a refresh, choose **Unlock with this device**; your saved passphrase still works as fallback. You can remove this shortcut in Settings. A PIN may be used instead of biometrics, and some passkeys synchronize through the OS/provider. No physical Face ID/Touch ID qualification has occurred.

An IP URL cannot offer this browser passkey option. Changing to a hostname creates a separate browser origin with no automatic key/history migration. Keep the original approved IP browser open, enroll the hostname as a **new device**, compare its fingerprint and approve it from the old browser; have each group explicitly add the new device. Preserve the recovery kit. Do not clear the old browser just to enable convenience. The local `localhost` QA origin in the runbook is only for isolated tests on the same computer, not a URL to send to friends. See ADR 0009.

## Inside a conversation

Use **All chats** or **Unread** to find a conversation. Search works on the
messages saved in this browser; the search button in a thread opens its search
field. A security-code comparison must still finish before messaging is enabled.

Write a message and use the arrow to send. On a computer, **Enter** sends and
**Shift + Enter** adds a line. Phone keyboards keep Return as a newline. These
controls and delivery indicators are explained under **Connection & help**.

Use the reply arrow on a message to reply. **Message actions** opens copy,
reaction, edit and delete controls. Edits load the current text. **Cancel edit**
restores your ordinary draft. Deleting sends a deletion event; another person may
already have retained a copy. Clipboard history can retain copied text.

Open the paperclip menu and choose **Photos & videos** for your gallery,
**Audio** for music/audio files, or **File** for documents and other files. Your
browser/OS supplies the picker, so its gallery choices can differ by device.

The confirmation box shows the actual local photo, video controls, or audio player
before sending. Check the preview, filename and viewing mode, then choose **Send
attachment**. No file is uploaded until confirmation. **Remove attachment**
cancels before upload. Unsupported types have a clear preview-unavailable message;
documents/HTML/SVG are not embedded. The cap remains 25 MiB.
**Open photo**/**Open video** decrypt ordinary media on this device; Escape or the
close button dismisses the preview. To send a view-once photo/video, first choose
its file, then enable **View once** inside that attachment’s confirmation box.
Read the capture/opening notice and choose **Send attachment**. This option appears
only for supported photos/videos. Every new or replacement selection starts in
ordinary mode; sending or removing it clears its mode. View-once is not protection
against screenshots or external cameras.

The microphone starts a voice note. Stop to send it, or choose **Discard recording**
to cancel; leaving the conversation also discards an active recording. Voice notes
are ordinary audio, separate from the photo/video view-once setting.

New messages do not move you away from older messages you are reading. Use the
down-arrow/new-messages button to return to the latest. On a phone, use the back
arrow in the chat header to return to conversations and the main navigation.

If **This browser needs approval** appears, follow its three steps in an existing
approved browser, then return and use **Check approval**. The long code identifies
the new browser; it is not a password. Expand **I can’t access the approved browser**
for recovery limits. Creating another vault does not approve or recover this one.

## Sign-in and automatic lock protection

After the session-security upgrade, sign in once with your existing account password. Keep your current browser data: your encrypted vault and approved identity remain. Use your existing vault passphrase or previously configured device unlock. Up to five unfinished browser sign-ins can be kept; a newer unfinished sign-in replaces the oldest, without using that limit to evict approved browser sessions.

HAVEN locks when you leave the page, restore it from browser history, or return/input after five minutes of inactivity, including a suspended tab. A confirmed expired/revoked server sign-in also locks your private space and asks you to sign in again. A temporary connection failure keeps offline vault access available; it cannot tell you immediately that a remote session was revoked. Saving your passphrase and recovery kit is still required.
