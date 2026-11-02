//! Test-only native MLS client. Stdin/stdout are PRIVATE pipes, never evidence.
//! Provider snapshots are returned only to the local encrypted-checkpoint driver.
use haven_crypto_core::run;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{self, BufRead, Write};

fn main() {
    let mut states: HashMap<String, String> = HashMap::new();
    for line in io::stdin().lock().lines() {
        let answer = (|| -> Option<Value> {
            let input: Value = serde_json::from_str(&line.ok()?).ok()?;
            let client = input["client"].as_str()?;
            if client.len() > 80 {
                return None;
            }
            if input["op"] == "restore" {
                let state = input["state"].as_str()?.to_owned();
                // Parse/validate the private snapshot through the pinned adapter.
                let group = input["group_id"].as_str()?;
                let parsed: Value = serde_json::from_str(
                    &run(
                        &state,
                        &json!({"op":"inspect","group_id":group}).to_string(),
                    )
                    .ok()?,
                )
                .ok()?;
                states.insert(client.into(), parsed["state"].as_str()?.into());
                return Some(json!({"ok":true}));
            }
            let previous = states.get(client).map(String::as_str).unwrap_or("");
            let output: Value =
                serde_json::from_str(&run(previous, &input["command"].to_string()).ok()?).ok()?;
            states.insert(client.into(), output["state"].as_str()?.into());
            Some(json!({"ok":true,"result":output["result"],"state":output["state"]}))
        })()
        .unwrap_or_else(|| json!({"ok":false,"error":"CLIENT_CRYPTO_REJECTED"}));
        println!("{answer}");
        if io::stdout().flush().is_err() {
            break;
        }
    }
}
