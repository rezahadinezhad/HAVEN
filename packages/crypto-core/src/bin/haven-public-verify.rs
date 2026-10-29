use std::io::{self, Read};
fn main() {
    let mut input = String::new();
    let read = io::stdin().take(200001).read_to_string(&mut input);
    match read
        .ok()
        .and_then(|_| haven_crypto_core::validate_public(&input).ok())
    {
        Some(result) => println!("{result}"),
        None => {
            eprintln!("PUBLIC_CRYPTO_REJECTED");
            std::process::exit(1);
        }
    }
}
