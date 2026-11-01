//! Synthetic, native-only comparison. No keys, state, identities or plaintext are printed.
use base64::{engine::general_purpose::STANDARD as B64, Engine};
use haven_crypto_core::run;
use serde_json::{json, Value};
use std::time::Instant;

fn call(state: &mut String, command: Value) -> Value {
    let out: Value = serde_json::from_str(&run(state, &command.to_string()).unwrap()).unwrap();
    *state = out["state"].as_str().unwrap().into();
    out["result"].clone()
}

fn main() {
    let (mut a, mut b) = (String::new(), String::new());
    call(&mut a, json!({"op":"init","identity":"benchmark-a"}));
    call(&mut b, json!({"op":"init","identity":"benchmark-b"}));
    let package = call(&mut b, json!({"op":"package"}));
    call(
        &mut a,
        json!({"op":"create","group_id":"metadata-benchmark"}),
    );
    let add = call(
        &mut a,
        json!({"op":"add","group_id":"metadata-benchmark","key_package":package["key_package"]}),
    );
    call(
        &mut b,
        json!({"op":"join","group_id":"metadata-benchmark","welcome":add["welcome"]}),
    );
    let mut rows = Vec::new();
    for size in [1, 16, 64, 128, 255, 256, 1024, 4096, 131072] {
        let text = "x".repeat(size);
        let (mut send, mut receive, mut lengths) = (Vec::new(), Vec::new(), Vec::new());
        for _ in 0..40 {
            let start = Instant::now();
            let encrypted = call(
                &mut a,
                json!({"op":"encrypt","group_id":"metadata-benchmark","plaintext":text}),
            );
            send.push(start.elapsed().as_micros());
            lengths.push(
                B64.decode(encrypted["ciphertext"].as_str().unwrap())
                    .unwrap()
                    .len(),
            );
            let start = Instant::now();
            let decrypted = call(
                &mut b,
                json!({"op":"process","group_id":"metadata-benchmark","ciphertext":encrypted["ciphertext"]}),
            );
            receive.push(start.elapsed().as_micros());
            assert_eq!(decrypted["plaintext"], text);
        }
        send.sort();
        receive.sort();
        lengths.sort();
        rows.push(json!({"plaintext_bytes":size,"samples":40,"send_median_us":send[20],"send_p95_us":send[37],"receive_median_us":receive[20],"receive_p95_us":receive[37],"wire_min_bytes":lengths[0],"wire_max_bytes":lengths[39]}));
    }
    println!(
        "{}",
        json!({"scope":"native adapter including snapshot serialization; excludes network, database, browser and battery", "rows":rows})
    );
}
