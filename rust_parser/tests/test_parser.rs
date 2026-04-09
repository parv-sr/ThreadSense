use std::fs;
use std::path::PathBuf;

#[test]
fn parser_source_contains_public_apis() {
    let mut lib = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    lib.push("src/lib.rs");
    let content = fs::read_to_string(lib).expect("read src/lib.rs");

    assert!(content.contains("fn parse_text("));
    assert!(content.contains("fn parse_file("));
    assert!(content.contains("fn parse_zip("));
    assert!(content.contains("fn get_parser_version("));
}
