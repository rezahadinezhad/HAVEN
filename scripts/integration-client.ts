import { connectionLoop } from "../apps/web/src/lib/connection";
import { Messenger, fingerprintOf } from "../apps/web/src/lib/messenger";
import { api } from "../apps/web/src/lib/api";
import { encryptUpload, downloadDecrypt } from "../apps/web/src/lib/media";
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
import { contactLink, readContactLink } from "../apps/web/src/lib/contact-link";
import { generateUnlockPassphrase } from "../apps/web/src/lib/passphrase";
Object.assign(window, {
  havenIntegration: {
    Messenger,
    cryptoCall,
    openVault,
    saveVault,
    vaultDB,
    seal,
    stopVaultWorker,
    generateUnlockPassphrase,
    contactLink,
    readContactLink,
    connectionLoop,
    fingerprintOf,
    api,
    encryptUpload,
    downloadDecrypt,
    recoveryKit,
    unseal,
    loadVault,
  },
});
