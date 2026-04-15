use chrono::{DateTime, NaiveDateTime, Utc};
use encoding_rs::WINDOWS_1252;
use log::{debug, warn};
use once_cell::sync::Lazy;
use pyo3::exceptions::{PyIOError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use rayon::prelude::*;
use regex::Regex;
use std::collections::HashSet;
use std::fs;
use std::io::{ErrorKind, Read};
use std::path::Path;
use std::process::Command;
use thiserror::Error;
use uuid::Uuid;
use zip::read::ZipArchive;

const PARSER_VERSION: &str = "2.0.0";
const MAX_TEXT_LEN: usize = 10_000;

static HEADER_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        r"(?xim)
        ^[\u{200E}\u{200F}\u{202A}\u{202B}\u{202C}\u{202D}\u{202E}\s]*
        (?:\[)?
        (?P<date>\d{1,2}/\d{1,2}/\d{2,4})
        [,\s]+
        (?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM|am|pm))?)
        (?:\])?
        [\s\-–—:]*
        (?P<sender>[^:\n\r]{1,200}?)\s*:\s*
    ",
    )
    .expect("valid header regex")
});

static SYSTEM_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        r"(?i)(end-to-end encrypted|message deleted|this message was deleted|joined using|left the group|created group|changed the subject|<?media omitted>?)",
    )
    .expect("valid system regex")
});

static EMOJI_REGEX: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"[\p{So}\p{Sk}\p{Cf}]").expect("valid emoji regex"));

static MULTISPACE_REGEX: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"[ \t]+").expect("valid space regex"));

#[derive(Debug, Error)]
enum ParserError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Zip error: {0}")]
    Zip(#[from] zip::result::ZipError),
    #[error("Unsupported archive type for parse_zip: {0}")]
    UnsupportedArchive(String),
    #[error("RAR extraction failed: {0}")]
    Rar(String),
}

impl From<ParserError> for PyErr {
    fn from(err: ParserError) -> Self {
        match err {
            ParserError::Io(e) => PyIOError::new_err(e.to_string()),
            ParserError::Zip(e) => PyValueError::new_err(e.to_string()),
            ParserError::UnsupportedArchive(e) => PyValueError::new_err(e),
            ParserError::Rar(e) => PyRuntimeError::new_err(e),
        }
    }
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct RawMessageChunkCreate {
    #[pyo3(get, set)]
    pub rawfile_id: String,
    #[pyo3(get, set)]
    pub message_start: Option<String>,
    #[pyo3(get, set)]
    pub sender: Option<String>,
    #[pyo3(get, set)]
    pub raw_text: String,
    #[pyo3(get, set)]
    pub cleaned_text: Option<String>,
    #[pyo3(get, set)]
    pub split_into: i32,
    #[pyo3(get, set)]
    pub status: String,
    #[pyo3(get, set)]
    pub user_id: Option<String>,
}

#[pymethods]
impl RawMessageChunkCreate {
    #[new]
    fn new(
        rawfile_id: Option<String>,
        message_start: Option<String>,
        sender: Option<String>,
        raw_text: String,
        cleaned_text: Option<String>,
        split_into: Option<i32>,
        status: Option<String>,
        user_id: Option<String>,
    ) -> Self {
        Self {
            rawfile_id: rawfile_id.unwrap_or_else(nil_uuid),
            message_start,
            sender,
            raw_text,
            cleaned_text,
            split_into: split_into.unwrap_or(0),
            status: status.unwrap_or_else(|| "NEW".to_string()),
            user_id,
        }
    }

    fn to_dict(&self) -> std::collections::HashMap<&'static str, Option<String>> {
        let mut out = std::collections::HashMap::new();
        out.insert("rawfile_id", Some(self.rawfile_id.clone()));
        out.insert("message_start", self.message_start.clone());
        out.insert("sender", self.sender.clone());
        out.insert("raw_text", Some(self.raw_text.clone()));
        out.insert("cleaned_text", self.cleaned_text.clone());
        out.insert("split_into", Some(self.split_into.to_string()));
        out.insert("status", Some(self.status.clone()));
        out.insert("user_id", self.user_id.clone());
        out
    }
}

#[pyfunction]
fn parse_text(content: &str) -> PyResult<Vec<RawMessageChunkCreate>> {
    init_logging();
    Ok(parse_content(content))
}

fn parse_bytes_impl(bytes: &[u8]) -> Vec<RawMessageChunkCreate> {
    let decoded = decode_text(bytes);
    parse_content(&decoded)
}

#[pyfunction]
fn parse_bytes(content: &[u8]) -> PyResult<Vec<RawMessageChunkCreate>> {
    init_logging();
    Ok(parse_bytes_impl(content))
}

#[pyfunction]
fn parse_file(file_path: &str) -> PyResult<Vec<RawMessageChunkCreate>> {
    init_logging();
    if !Path::new(file_path).exists() {
        return Err(ParserError::Io(std::io::Error::new(
            ErrorKind::NotFound,
            format!("input file not found: {file_path}"),
        ))
        .into());
    }
    let bytes = fs::read(file_path).map_err(ParserError::from)?;
    Ok(parse_bytes_impl(&bytes))
}

#[pyfunction]
fn parse_zip(zip_path: &str) -> PyResult<Vec<RawMessageChunkCreate>> {
    init_logging();
    let lower = zip_path.to_ascii_lowercase();

    if lower.ends_with(".zip") {
        let file = fs::File::open(zip_path).map_err(ParserError::from)?;
        let mut archive = ZipArchive::new(file).map_err(ParserError::from)?;
        let mut collected = Vec::new();

        for i in 0..archive.len() {
            let mut zf = archive.by_index(i).map_err(ParserError::from)?;
            if zf.is_dir() {
                continue;
            }

            let name = zf.name().to_ascii_lowercase();
            if !(name.ends_with(".txt") || name.ends_with(".log")) {
                continue;
            }

            let mut bytes = Vec::new();
            zf.read_to_end(&mut bytes).map_err(ParserError::from)?;
            collected.extend(parse_bytes_impl(&bytes));
        }
        return Ok(collected);
    }

    if lower.ends_with(".rar") {
        let output = match Command::new("unrar")
            .args(["p", "-inul", zip_path])
            .output()
        {
            Ok(output) => output,
            Err(err) if err.kind() == ErrorKind::NotFound => {
                return Err(ParserError::Rar(
                    "RAR support unavailable: `unrar` executable not found".to_string(),
                )
                .into());
            }
            Err(err) => return Err(ParserError::from(err).into()),
        };

        if !output.status.success() {
            return Err(
                ParserError::Rar(String::from_utf8_lossy(&output.stderr).to_string()).into(),
            );
        }

        return Ok(parse_bytes_impl(&output.stdout));
    }

    Err(ParserError::UnsupportedArchive(zip_path.to_string()).into())
}

#[pyfunction]
fn get_parser_version() -> String {
    PARSER_VERSION.to_string()
}

#[pymodule]
fn whatsapp_parser(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RawMessageChunkCreate>()?;
    m.add_function(wrap_pyfunction!(parse_text, m)?)?;
    m.add_function(wrap_pyfunction!(parse_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(parse_file, m)?)?;
    m.add_function(wrap_pyfunction!(parse_zip, m)?)?;
    m.add_function(wrap_pyfunction!(get_parser_version, m)?)?;
    Ok(())
}

fn init_logging() {
    dotenv::dotenv().ok();
    let _ = env_logger::builder().is_test(true).try_init();
}

fn nil_uuid() -> String {
    Uuid::nil().to_string()
}

#[derive(Debug, Clone)]
struct HeaderData {
    date: String,
    time: String,
    sender: String,
}

#[derive(Debug)]
struct BlockData {
    header: Option<HeaderData>,
    block: String,
}

#[derive(Debug)]
struct Interim {
    sender: Option<String>,
    message_start: Option<String>,
    raw_text: String,
    cleaned_text: String,
}

fn parse_content(text: &str) -> Vec<RawMessageChunkCreate> {
    let normalized = normalize_whitespace(text);
    let blocks = split_messages_whatsapp(&normalized);

    let mut interim: Vec<Interim> = blocks
        .par_iter()
        .map(|block| {
            let (sender, message_start) = if let Some(h) = &block.header {
                let dt = parse_datetime(&h.date, Some(&h.time));
                (Some(h.sender.trim().to_string()), Some(dt.to_rfc3339()))
            } else {
                (None, None)
            };

            let cleaned = clean_block(&block.block);

            Interim {
                sender,
                message_start,
                raw_text: truncate(&block.block, MAX_TEXT_LEN),
                cleaned_text: truncate(&cleaned, MAX_TEXT_LEN),
            }
        })
        .collect();

    interim.sort_by(|a, b| a.message_start.cmp(&b.message_start));

    let mut dedupe_seen: HashSet<String> = HashSet::new();
    let mut out = Vec::with_capacity(interim.len());

    for item in interim {
        if item.cleaned_text.is_empty() {
            out.push(RawMessageChunkCreate {
                rawfile_id: nil_uuid(),
                message_start: item.message_start,
                sender: item.sender,
                raw_text: item.raw_text,
                cleaned_text: Some(String::new()),
                split_into: 0,
                status: "IGNORED".to_string(),
                user_id: None,
            });
            continue;
        }

        let dedupe_key = local_dedupe_key(&item.cleaned_text);
        if dedupe_seen.contains(&dedupe_key) {
            out.push(RawMessageChunkCreate {
                rawfile_id: nil_uuid(),
                message_start: item.message_start,
                sender: item.sender,
                raw_text: item.raw_text,
                cleaned_text: Some(item.cleaned_text),
                split_into: 0,
                status: "DUPLICATE_LOCAL".to_string(),
                user_id: None,
            });
            continue;
        }

        dedupe_seen.insert(dedupe_key);
        out.push(RawMessageChunkCreate {
            rawfile_id: nil_uuid(),
            message_start: item.message_start,
            sender: item.sender,
            raw_text: item.raw_text,
            cleaned_text: Some(item.cleaned_text),
            split_into: 0,
            status: "NEW".to_string(),
            user_id: None,
        });
    }

    out
}

fn split_messages_whatsapp(text: &str) -> Vec<BlockData> {
    let matches: Vec<_> = HEADER_REGEX.find_iter(text).collect();
    if matches.is_empty() {
        return vec![BlockData {
            header: None,
            block: text.to_string(),
        }];
    }

    let mut blocks = Vec::with_capacity(matches.len());

    for (i, m) in matches.iter().enumerate() {
        let start = m.start();
        let end = matches.get(i + 1).map_or(text.len(), |n| n.start());
        let block = text[start..end].trim().to_string();

        let caps = HEADER_REGEX.captures(&block);
        let header = caps.map(|c| HeaderData {
            date: c
                .name("date")
                .map(|x| x.as_str().to_string())
                .unwrap_or_default(),
            time: c
                .name("time")
                .map(|x| x.as_str().to_string())
                .unwrap_or_default(),
            sender: c
                .name("sender")
                .map(|x| x.as_str().trim().to_string())
                .unwrap_or_default(),
        });

        blocks.push(BlockData { header, block });
    }

    blocks
}

fn clean_block(block: &str) -> String {
    if block.is_empty() {
        return String::new();
    }

    let mut s = strip_emojis(block);
    s = normalize_whitespace(&s);

    if let Some(m) = HEADER_REGEX.find(&s) {
        if m.start() == 0 {
            s = s[m.end()..].trim().to_string();
        }
    }

    let lines: Vec<&str> = s
        .lines()
        .filter(|line| !SYSTEM_REGEX.is_match(line.trim()))
        .collect();
    lines.join("\n").trim().to_string()
}

fn normalize_whitespace(s: &str) -> String {
    let mut out = s
        .replace('\u{00A0}', " ")
        .replace('\u{202F}', " ")
        .replace('\u{200B}', "")
        .replace('\u{200E}', "")
        .replace('\u{200F}', "");
    out = MULTISPACE_REGEX.replace_all(&out, " ").to_string();
    out
}

fn strip_emojis(s: &str) -> String {
    if s.is_empty() {
        return String::new();
    }
    EMOJI_REGEX.replace_all(s, " ").to_string()
}

fn parse_datetime(date_str: &str, time_str: Option<&str>) -> DateTime<Utc> {
    if date_str.trim().is_empty() {
        return Utc::now();
    }

    let date = normalize_whitespace(date_str);
    let time = normalize_whitespace(time_str.unwrap_or(""));
    let combined = format!("{} {}", date, time).trim().to_string();

    let fmts = [
        "%d/%m/%y %I:%M %p",
        "%d/%m/%y %H:%M",
        "%d/%m/%y %I:%M:%S %p",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%Y %H:%M:%S",
    ];

    for fmt in fmts {
        if let Ok(dt) = NaiveDateTime::parse_from_str(&combined, fmt) {
            return DateTime::<Utc>::from_naive_utc_and_offset(dt, Utc);
        }
    }

    warn!(
        "Unknown timestamp format '{}', defaulting to now()",
        combined
    );
    Utc::now()
}

fn local_dedupe_key(cleaned: &str) -> String {
    normalize_whitespace(cleaned).to_lowercase()
}

fn decode_text(bytes: &[u8]) -> String {
    match std::str::from_utf8(bytes) {
        Ok(s) => s.to_string(),
        Err(_) => {
            debug!("UTF-8 decode failed, trying windows-1252 fallback");
            let (cow, _, _) = WINDOWS_1252.decode(bytes);
            cow.to_string()
        }
    }
}

fn truncate(input: &str, max_len: usize) -> String {
    input.chars().take(max_len).collect::<String>()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_text_basic() {
        let content = "[01/01/24, 10:00 AM] Alice: Hello\n[01/01/24, 10:05 AM] Bob: Hi";
        let out = parse_content(content);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].status, "NEW");
        assert_eq!(out[0].sender.as_deref(), Some("Alice"));
    }

    #[test]
    fn test_system_message_ignored() {
        let content = "[01/01/24, 10:00 AM] Alice: Messages and calls are end-to-end encrypted.";
        let out = parse_content(content);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].status, "IGNORED");
    }

    #[test]
    fn test_duplicate_local() {
        let content = "[01/01/24, 10:00 AM] Alice: Hello\n[01/01/24, 10:01 AM] Bob: Hello";
        let out = parse_content(content);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].status, "NEW");
        assert_eq!(out[1].status, "DUPLICATE_LOCAL");
    }
}
