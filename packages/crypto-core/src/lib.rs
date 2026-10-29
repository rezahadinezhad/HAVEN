//! Local RFC 9420 adapter. Serialized state is SECRET and must only live in an encrypted client vault.
use ::tls_codec::{Deserialize, Serialize};
use base64::{engine::general_purpose::STANDARD as B64, Engine};
use openmls::prelude::*;
use openmls_basic_credential::SignatureKeyPair;
use openmls_memory_storage::MemoryStorage;
use openmls_rust_crypto::RustCrypto;
use openmls_traits::{signatures::Signer, OpenMlsProvider};
use serde::{Deserialize as SerdeDeserialize, Serialize as SerdeSerialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use wasm_bindgen::prelude::*;

const SUITE: Ciphersuite = Ciphersuite::MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519;
const MAX_INPUT: usize = 16 * 1024 * 1024;
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
#[derive(Default)]
struct Provider {
    crypto: RustCrypto,
    store: MemoryStorage,
}
impl OpenMlsProvider for Provider {
    type CryptoProvider = RustCrypto;
    type RandProvider = RustCrypto;
    type StorageProvider = MemoryStorage;
    fn crypto(&self) -> &RustCrypto {
        &self.crypto
    }
    fn rand(&self) -> &RustCrypto {
        &self.crypto
    }
    fn storage(&self) -> &MemoryStorage {
        &self.store
    }
}
#[derive(SerdeSerialize, SerdeDeserialize)]
struct Snapshot {
    v: u8,
    identity: String,
    signer: SignatureKeyPair,
    store: Vec<(Vec<u8>, Vec<u8>)>,
}
fn str_field<'a>(v: &'a Value, k: &str) -> Result<&'a str> {
    v[k].as_str().ok_or_else(|| "invalid input".into())
}
fn bytes(v: &Value, k: &str) -> Result<Vec<u8>> {
    Ok(B64.decode(str_field(v, k)?)?)
}
fn wire(m: &MlsMessageOut) -> Result<String> {
    Ok(B64.encode(m.tls_serialize_detached()?))
}
fn roster(g: &MlsGroup) -> Value {
    json!(g
        .members()
        .map(|m| json!({"index":m.index.u32(),
        "identity": String::from_utf8_lossy(m.credential.serialized_content()),
        "public_key": B64.encode(m.signature_key)}))
        .collect::<Vec<_>>())
}
pub fn run(state: &str, command: &str) -> Result<String> {
    if state.len() > MAX_INPUT || command.len() > MAX_INPUT {
        return Err("input limit".into());
    }
    let c: Value = serde_json::from_str(command)?;
    let op = str_field(&c, "op")?;
    let provider = Provider::default();
    let (identity, signer) = if op == "init" {
        let identity = str_field(&c, "identity")?.to_string();
        if identity.len() > 200 || identity.is_empty() {
            return Err("identity limit".into());
        }
        let signer = SignatureKeyPair::new(SUITE.signature_algorithm())?;
        signer.store(provider.storage())?;
        (identity, signer)
    } else {
        let snap: Snapshot = serde_json::from_str(state)?;
        if snap.v != 1 {
            return Err("state version".into());
        }
        *provider
            .store
            .values
            .write()
            .map_err(|_| "storage locked")? = snap.store.into_iter().collect();
        (snap.identity, snap.signer)
    };
    let credential = CredentialWithKey {
        credential: BasicCredential::new(identity.as_bytes().to_vec()).into(),
        signature_key: signer.public().into(),
    };
    let mut result = json!({"identity": identity, "public_key":B64.encode(signer.public())});
    if op == "sign" {
        let payload = bytes(&c, "payload")?;
        if payload.len() > 65536 {
            return Err("signature payload limit".into());
        }
        result["signature"] =
            json!(B64.encode(signer.sign(&payload).map_err(|_| "signing failed")?));
    } else if op == "package" {
        let kp = KeyPackage::builder().build(SUITE, &provider, &signer, credential)?;
        result["key_package"] = json!(B64.encode(kp.key_package().tls_serialize_detached()?));
    } else if op == "create" {
        let id = str_field(&c, "group_id")?;
        let config = MlsGroupCreateConfig::builder()
            .ciphersuite(SUITE)
            .use_ratchet_tree_extension(true)
            .build();
        let group = MlsGroup::new_with_group_id(
            &provider,
            &signer,
            &config,
            GroupId::from_slice(id.as_bytes()),
            credential,
        )?;
        result["state_hash"] = json!(format!(
            "{:x}",
            Sha256::digest(group.epoch_authenticator().as_slice())
        ));
        result["members"] = roster(&group);
        result["epoch"] = json!(group.epoch().as_u64());
    } else if op == "join" {
        let welcome = match MlsMessageIn::tls_deserialize_exact(bytes(&c, "welcome")?)?.extract() {
            MlsMessageBodyIn::Welcome(w) => w,
            _ => return Err("expected welcome".into()),
        };
        let config = MlsGroupJoinConfig::builder()
            .use_ratchet_tree_extension(true)
            .build();
        let group = StagedWelcome::new_from_welcome(&provider, &config, welcome, None)?
            .into_group(&provider)?;
        if group.group_id().as_slice() != str_field(&c, "group_id")?.as_bytes() {
            return Err("group mismatch".into());
        }
        result["state_hash"] = json!(format!(
            "{:x}",
            Sha256::digest(group.epoch_authenticator().as_slice())
        ));
        result["members"] = roster(&group);
        result["epoch"] = json!(group.epoch().as_u64());
    } else if !matches!(op, "init" | "package" | "sign") {
        let id = GroupId::from_slice(str_field(&c, "group_id")?.as_bytes());
        let mut group = MlsGroup::load(provider.storage(), &id)?.ok_or("unknown group")?;
        match op {
            "add" => {
                let kp = KeyPackageIn::tls_deserialize_exact(bytes(&c, "key_package")?)?
                    .validate(provider.crypto(), ProtocolVersion::Mls10)?;
                let (commit, welcome, _) = group.add_members(&provider, &signer, &[kp])?;
                result["commit"] = json!(wire(&commit)?);
                result["welcome"] = json!(wire(&welcome)?);
                group.merge_pending_commit(&provider)?;
            }
            "remove" => {
                let index = c["index"]
                    .as_u64()
                    .filter(|x| *x <= u32::MAX as u64)
                    .ok_or("invalid index")?;
                let (commit, _, _) = group.remove_members(
                    &provider,
                    &signer,
                    &[LeafNodeIndex::new(index as u32)],
                )?;
                result["commit"] = json!(wire(&commit)?);
                group.merge_pending_commit(&provider)?;
            }
            "update" => {
                let bundle =
                    group.self_update(&provider, &signer, LeafNodeParameters::default())?;
                result["commit"] = json!(wire(bundle.commit())?);
                group.merge_pending_commit(&provider)?;
            }
            "encrypt" => {
                let plaintext = str_field(&c, "plaintext")?;
                if plaintext.len() > 131072 {
                    return Err("message limit".into());
                }
                result["ciphertext"] = json!(wire(&group.create_message(
                    &provider,
                    &signer,
                    plaintext.as_bytes()
                )?)?);
            }
            "process" => {
                let m = MlsMessageIn::tls_deserialize_exact(bytes(&c, "ciphertext")?)?
                    .try_into_protocol_message()?;
                let processed = group.process_message(&provider, m)?;
                result["sender"] = json!(String::from_utf8_lossy(
                    processed.credential().serialized_content()
                ));
                match processed.into_content() {
                    ProcessedMessageContent::ApplicationMessage(app) => {
                        result["plaintext"] = json!(String::from_utf8(app.into_bytes())?);
                        result["kind"] = json!("application");
                    }
                    ProcessedMessageContent::StagedCommitMessage(commit) => {
                        group.merge_staged_commit(&provider, *commit)?;
                        result["kind"] = json!("commit");
                    }
                    _ => return Err("unsolicited proposal or own message".into()),
                }
            }
            "inspect" => {}
            _ => return Err("unknown operation".into()),
        }
        result["state_hash"] = json!(format!(
            "{:x}",
            Sha256::digest(group.epoch_authenticator().as_slice())
        ));
        result["members"] = roster(&group);
        result["epoch"] = json!(group.epoch().as_u64());
        result["active"] = json!(group.is_active());
    }
    // Bound storage before it is serialized, including authenticated but malformed states.
    let store: Vec<_> = provider
        .store
        .values
        .read()
        .map_err(|_| "storage locked")?
        .iter()
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    let snapshot = Snapshot {
        v: 1,
        identity,
        signer,
        store,
    };
    let state = serde_json::to_string(&snapshot)?;
    if state.len() > MAX_INPUT {
        return Err("state limit".into());
    }
    Ok(json!({"state":state,"result":result}).to_string())
}
/// Public-only validation. Private snapshots are never accepted by this entry point.
pub fn validate_public(command: &str) -> Result<String> {
    if command.len() > 200000 {
        return Err("input limit".into());
    }
    let c: Value = serde_json::from_str(command)?;
    let op = str_field(&c, "op")?;
    let payload = match op {
        "package" => "package",
        "wire" => "ciphertext",
        _ => return Err("operation".into()),
    };
    let object = c.as_object().ok_or("object required")?;
    if object.len() != 2 || object.keys().any(|key| key != "op" && key != payload) {
        return Err("unknown public validation fields".into());
    }
    let provider = Provider::default();
    let result = match op {
        "package" => {
            let kp = KeyPackageIn::tls_deserialize_exact(bytes(&c, "package")?)?
                .validate(provider.crypto(), ProtocolVersion::Mls10)?;
            if kp.ciphersuite() != SUITE {
                return Err("suite".into());
            }
            json!({"identity": String::from_utf8(kp.leaf_node().credential().serialized_content().to_vec())?,
                "public_key": B64.encode(kp.leaf_node().signature_key().as_slice())})
        }
        "wire" => {
            let m = MlsMessageIn::tls_deserialize_exact(bytes(&c, "ciphertext")?)?
                .try_into_protocol_message()?;
            json!({"group_id": String::from_utf8(m.group_id().as_slice().to_vec())?, "epoch": m.epoch().as_u64()})
        }
        _ => return Err("operation".into()),
    };
    Ok(result.to_string())
}
#[wasm_bindgen]
pub fn execute(state: &str, command: &str) -> std::result::Result<String, JsValue> {
    // Never expose private state or diagnostic structures in exceptions.
    run(state, command).map_err(|_| JsValue::from_str("CRYPTO_REJECTED"))
}
#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(64))]
        #[test]
        fn arbitrary_public_frames_are_bounded_and_never_panic(bytes in prop::collection::vec(any::<u8>(), 0..2048)) {
            for (op, field) in [("wire", "ciphertext"), ("package", "package")] {
                let mut command = json!({"op":op});
                command[field] = Value::String(B64.encode(&bytes));
                let parsed = std::panic::catch_unwind(|| validate_public(&command.to_string()));
                prop_assert!(parsed.is_ok());
                command["state"] = Value::String("private snapshots forbidden".into());
                prop_assert!(validate_public(&command.to_string()).is_err());
            }
        }
        #[test]
        fn unicode_serialization_preserves_authenticated_plaintext(text in prop::collection::vec(any::<char>(), 0..1024)) {
            fn call(state: &mut String, command:Value) -> Value {
                let out:Value=serde_json::from_str(&run(state,&command.to_string()).unwrap()).unwrap();
                *state=out["state"].as_str().unwrap().to_string();out["result"].clone()
            }
            let text:String=text.into_iter().collect();
            let (mut a,mut b)=(String::new(),String::new());
            call(&mut a,json!({"op":"init","identity":"property-a"}));
            call(&mut b,json!({"op":"init","identity":"property-b"}));
            let kp=call(&mut b,json!({"op":"package"}));
            call(&mut a,json!({"op":"create","group_id":"property"}));
            let add=call(&mut a,json!({"op":"add","group_id":"property","key_package":kp["key_package"]}));
            call(&mut b,json!({"op":"join","group_id":"property","welcome":add["welcome"]}));
            let encrypted=call(&mut a,json!({"op":"encrypt","group_id":"property","plaintext":text}));
            let decrypted=call(&mut b,json!({"op":"process","group_id":"property","ciphertext":encrypted["ciphertext"]}));
            prop_assert_eq!(decrypted["plaintext"].as_str(),Some(text.as_str()));
            let replay=run(&b,&json!({"op":"process","group_id":"property","ciphertext":encrypted["ciphertext"]}).to_string());
            prop_assert!(replay.is_err());
        }
    }

    #[test]
    fn native_to_wasm_golden_fixture() {
        fn call(s: &mut String, c: Value) -> Value {
            let x: Value = serde_json::from_str(&run(s, &c.to_string()).unwrap()).unwrap();
            *s = x["state"].as_str().unwrap().into();
            x["result"].clone()
        }
        let mut a = String::new();
        let mut b = String::new();
        call(&mut a, json!({"op":"init","identity":"native-alice"}));
        call(&mut b, json!({"op":"init","identity":"wasm-bob"}));
        let kp = call(&mut b, json!({"op":"package"}));
        call(
            &mut a,
            json!({"op":"create","group_id":"native-wasm-golden"}),
        );
        let add = call(
            &mut a,
            json!({"op":"add","group_id":"native-wasm-golden","key_package":kp["key_package"]}),
        );
        call(
            &mut b,
            json!({"op":"join","group_id":"native-wasm-golden","welcome":add["welcome"]}),
        );
        let message = call(
            &mut a,
            json!({"op":"encrypt","group_id":"native-wasm-golden","plaintext":"Native → WASM: سلام 🗝"}),
        );
        if let Ok(path) = std::env::var("HAVEN_GOLDEN_FILE") {
            use std::io::Write;
            use std::os::unix::fs::OpenOptionsExt;
            let mut file = std::fs::OpenOptions::new()
                .create(true)
                .truncate(true)
                .write(true)
                .mode(0o600)
                .open(path)
                .unwrap();
            write!(
                file,
                "{}",
                json!({"state":b,"ciphertext":message["ciphertext"]})
            )
            .unwrap();
        }
        assert_eq!(
            call(
                &mut b,
                json!({"op":"process","group_id":"native-wasm-golden","ciphertext":message["ciphertext"]})
            )["plaintext"],
            "Native → WASM: سلام 🗝"
        );
    }

    #[test]
    fn native_roundtrip() {
        fn call(s: &mut String, c: Value) -> Value {
            let x: Value = serde_json::from_str(&run(s, &c.to_string()).unwrap()).unwrap();
            *s = x["state"].as_str().unwrap().into();
            x["result"].clone()
        }
        let mut a = String::new();
        let mut b = String::new();
        call(&mut a, json!({"op":"init","identity":"alice"}));
        call(&mut b, json!({"op":"init","identity":"bob"}));
        let kp = call(&mut b, json!({"op":"package"}));
        call(&mut a, json!({"op":"create","group_id":"test"}));
        let add = call(
            &mut a,
            json!({"op":"add","group_id":"test","key_package":kp["key_package"]}),
        );
        call(
            &mut b,
            json!({"op":"join","group_id":"test","welcome":add["welcome"]}),
        );
        let enc = call(
            &mut a,
            json!({"op":"encrypt","group_id":"test","plaintext":"سلام"}),
        );
        let out = call(
            &mut b,
            json!({"op":"process","group_id":"test","ciphertext":enc["ciphertext"]}),
        );
        assert_eq!(out["plaintext"], "سلام");
        assert!(run(
            &b,
            &json!({"op":"process","group_id":"test","ciphertext":enc["ciphertext"]}).to_string()
        )
        .is_err());
    }
}
