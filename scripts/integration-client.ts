import { connectionLoop } from "../apps/web/src/lib/connection";
import { Messenger, fingerprintOf } from "../apps/web/src/lib/messenger";
import { api } from "../apps/web/src/lib/api";
import sodium from "../apps/web/node_modules/libsodium-wrappers-sumo";
import { paddedAttachmentSize, attachmentLayout } from "../apps/web/src/lib/attachment-format";
import { authenticatedEvent } from "../apps/web/src/lib/events";
import { encryptUpload, downloadDecrypt, prepareUpload, resumeUpload, discardUpload } from "../apps/web/src/lib/media";
import { cryptoCall } from "../apps/web/src/lib/crypto";
import {
  recoveryKit,
  unseal,
  loadVault,
  openVault,
  saveVault,
  vaultDB,
  seal,
  stopVaultWorker,
} from "../apps/web/src/lib/vault";
import { contactLink, readContactLink, lookupContact } from "../apps/web/src/lib/contact-link";
import { generateUnlockPassphrase } from "../apps/web/src/lib/passphrase";
async function shareDevice(deviceId: string) {
  const device = (await api<import("../apps/web/src/lib/api").Device[]>("devices")).find(d => d.id === deviceId);
  if (!device) throw new Error("Own device required");
  if (device.trust_state !== "approved") return device;
  return {...device, contact_token:(await api<{token:string}>("devices/contact-introduction", "POST", {})).token};
}
Object.assign(window, {
  havenIntegration: {
    Messenger,
    shareDevice,
    cryptoCall,
    openVault,
    saveVault,
    vaultDB,
    seal,
    stopVaultWorker,
    generateUnlockPassphrase,
    contactLink,
    lookupContact,
    readContactLink,
    connectionLoop,
    fingerprintOf,
    api,
    sodium,
    paddedAttachmentSize,
    attachmentLayout,
    authenticatedEvent,
    prepareUpload,
    resumeUpload,
    discardUpload,
    encryptUpload,
    downloadDecrypt,
    recoveryKit,
    unseal,
    loadVault,
  },
});
