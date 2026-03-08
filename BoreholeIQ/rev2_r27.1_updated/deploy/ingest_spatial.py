"""
BoreholeIQ v2 R27 - deploy/ingest_spatial.py
Spatial PDF Extraction Engine

Extracts word-level bounding boxes from PDFs using pdftotext -bbox-layout,
clusters x-coordinates into columns, and associates depths with descriptions
by y-coordinate proximity. Solves the Indonesian multi-column table problem.

This module generates Rust source code for pipeline/spatial.rs that gets
scaffolded into the Tauri backend.
"""

SPATIAL_RS = r'''use std::path::Path;
use std::process::Command;
use std::collections::BTreeMap;
use regex::Regex;
use once_cell::sync::Lazy;

/// A word with its bounding box from pdftotext -bbox output.
#[derive(Debug, Clone)]
pub struct BboxWord {
    pub text: String,
    pub x1: f64,
    pub y1: f64,
    pub x2: f64,
    pub y2: f64,
    pub page: usize,
}

/// A detected column in a table.
#[derive(Debug, Clone)]
pub struct TableColumn {
    pub x_center: f64,
    pub x_min: f64,
    pub x_max: f64,
    pub header: Option<String>,
    pub role: ColumnRole,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ColumnRole {
    Depth,
    Description,
    Spt,
    Sample,
    Recovery,
    Unknown,
}

/// A row extracted from spatial table analysis.
#[derive(Debug, Clone)]
pub struct SpatialRow {
    pub y_center: f64,
    pub depth_top: Option<f64>,
    pub depth_base: Option<f64>,
    pub description: Option<String>,
    pub spt_n: Option<u32>,
    pub sample_type: Option<String>,
    pub confidence: f64,
}

static PDFTOTEXT_DIR: &str = r"C:\Tools\poppler\bin";

fn pdftotext_exe() -> String {
    if let Ok(p) = std::env::var("BOREHOLEIQ_PDFTOTEXT") { return p; }
    let fallback = format!(r"{}\pdftotext.exe", PDFTOTEXT_DIR);
    if Path::new(&fallback).exists() { return fallback; }
    "pdftotext".to_string()
}

/// Extract word bounding boxes from a PDF using pdftotext -bbox-layout.
/// Returns XML-like output that we parse into BboxWord structs.
pub fn extract_bbox(pdf_path: &Path) -> Result<Vec<BboxWord>, String> {
    let exe = pdftotext_exe();
    let output = Command::new(&exe)
        .args(["-bbox-layout", "-enc", "UTF-8"])
        .arg(pdf_path)
        .arg("-") // stdout
        .output()
        .map_err(|e| format!("pdftotext -bbox failed: {} (path: {})", e, exe))?;

    if !output.status.success() {
        return Err(format!("pdftotext -bbox exited with error"));
    }

    let text = String::from_utf8_lossy(&output.stdout);
    parse_bbox_xml(&text)
}

/// Parse pdftotext -bbox-layout HTML/XML output into word structs.
fn parse_bbox_xml(html: &str) -> Result<Vec<BboxWord>, String> {
    static RE_WORD: Lazy<Regex> = Lazy::new(|| {
        Regex::new(r#"<word xMin="([^"]+)" yMin="([^"]+)" xMax="([^"]+)" yMax="([^"]+)">([^<]+)</word>"#).unwrap()
    });
    static RE_PAGE: Lazy<Regex> = Lazy::new(|| {
        Regex::new(r#"<page width="[^"]+" height="[^"]+">"#).unwrap()
    });

    let mut words = Vec::new();
    let mut page_num = 0usize;

    for line in html.lines() {
        if RE_PAGE.is_match(line) {
            page_num += 1;
        }
        for caps in RE_WORD.captures_iter(line) {
            let x1: f64 = caps[1].parse().unwrap_or(0.0);
            let y1: f64 = caps[2].parse().unwrap_or(0.0);
            let x2: f64 = caps[3].parse().unwrap_or(0.0);
            let y2: f64 = caps[4].parse().unwrap_or(0.0);
            let text = caps[5].trim().to_string();
            if !text.is_empty() {
                words.push(BboxWord { text, x1, y1, x2, y2, page: page_num });
            }
        }
    }
    Ok(words)
}

/// Cluster words into columns by x-coordinate proximity.
/// Uses a simple histogram approach: bin x-centers, find peaks.
pub fn detect_columns(words: &[BboxWord], tolerance: f64) -> Vec<TableColumn> {
    if words.is_empty() { return vec![]; }

    // Collect x-centers
    let mut x_centers: Vec<f64> = words.iter().map(|w| (w.x1 + w.x2) / 2.0).collect();
    x_centers.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    // Cluster x-centers within tolerance
    let mut clusters: Vec<Vec<f64>> = Vec::new();
    for &x in &x_centers {
        if let Some(last) = clusters.last_mut() {
            let mean: f64 = last.iter().sum::<f64>() / last.len() as f64;
            if (x - mean).abs() < tolerance {
                last.push(x);
                continue;
            }
        }
        clusters.push(vec![x]);
    }

    // Only keep clusters with enough words (at least 3 words = likely a column)
    let mut columns: Vec<TableColumn> = clusters.iter()
        .filter(|c| c.len() >= 3)
        .map(|c| {
            let mean = c.iter().sum::<f64>() / c.len() as f64;
            let min = c.iter().cloned().fold(f64::MAX, f64::min);
            let max = c.iter().cloned().fold(f64::MIN, f64::max);
            TableColumn {
                x_center: mean, x_min: min, x_max: max,
                header: None, role: ColumnRole::Unknown,
            }
        })
        .collect();

    columns.sort_by(|a, b| a.x_center.partial_cmp(&b.x_center).unwrap_or(std::cmp::Ordering::Equal));

    // Try to identify column roles from header words
    identify_column_roles(&mut columns, words);

    columns
}

/// Identify column roles by checking header-row words against known labels.
fn identify_column_roles(columns: &mut [TableColumn], words: &[BboxWord]) {
    // Header words are typically in the top 15% of the page
    let min_y = words.iter().map(|w| w.y1).fold(f64::MAX, f64::min);
    let max_y = words.iter().map(|w| w.y2).fold(f64::MIN, f64::max);
    let header_threshold = min_y + (max_y - min_y) * 0.15;

    let header_words: Vec<&BboxWord> = words.iter()
        .filter(|w| w.y1 < header_threshold)
        .collect();

    let depth_keywords = ["DEPTH", "KEDALAMAN", "TOP", "BASE", "METER", "DEEP"];
    let desc_keywords = ["DESCRIPTION", "DESKRIPSI", "SOIL", "TANAH", "GEOLOGI", "JENIS"];
    let spt_keywords = ["SPT", "N-VALUE", "BLOW", "PUKULAN"];
    let sample_keywords = ["SAMPLE", "SAMPEL", "UDS", "CONTOH"];

    for col in columns.iter_mut() {
        // Find header words that fall within this column's x-range
        let col_headers: Vec<String> = header_words.iter()
            .filter(|w| {
                let wx = (w.x1 + w.x2) / 2.0;
                wx >= col.x_min - 20.0 && wx <= col.x_max + 20.0
            })
            .map(|w| w.text.to_uppercase())
            .collect();

        let joined = col_headers.join(" ");
        col.header = if joined.is_empty() { None } else { Some(joined.clone()) };

        if depth_keywords.iter().any(|k| joined.contains(k)) {
            col.role = ColumnRole::Depth;
        } else if desc_keywords.iter().any(|k| joined.contains(k)) {
            col.role = ColumnRole::Description;
        } else if spt_keywords.iter().any(|k| joined.contains(k)) {
            col.role = ColumnRole::Spt;
        } else if sample_keywords.iter().any(|k| joined.contains(k)) {
            col.role = ColumnRole::Sample;
        }
    }

    // Heuristic fallback: if no headers found, first numeric column is Depth,
    // widest text column is Description
    let has_depth = columns.iter().any(|c| c.role == ColumnRole::Depth);
    if !has_depth && columns.len() >= 2 {
        // First column with mostly numbers = depth
        // Widest column = description
        if let Some(first) = columns.first_mut() {
            first.role = ColumnRole::Depth;
        }
        if let Some(widest) = columns.iter_mut().max_by(|a, b|
            (a.x_max - a.x_min).partial_cmp(&(b.x_max - b.x_min)).unwrap_or(std::cmp::Ordering::Equal)
        ) {
            if widest.role == ColumnRole::Unknown {
                widest.role = ColumnRole::Description;
            }
        }
    }
}

/// Extract rows by grouping words at similar y-coordinates and reading
/// values from identified columns.
pub fn extract_spatial_rows(words: &[BboxWord], columns: &[TableColumn]) -> Vec<SpatialRow> {
    if columns.is_empty() || words.is_empty() { return vec![]; }

    // Skip header region (top 15%)
    let min_y = words.iter().map(|w| w.y1).fold(f64::MAX, f64::min);
    let max_y = words.iter().map(|w| w.y2).fold(f64::MIN, f64::max);
    let header_threshold = min_y + (max_y - min_y) * 0.15;

    let data_words: Vec<&BboxWord> = words.iter()
        .filter(|w| w.y1 >= header_threshold)
        .collect();

    // Group words by y-coordinate (within 5pt tolerance = same row)
    let mut y_groups: BTreeMap<i64, Vec<&BboxWord>> = BTreeMap::new();
    for w in &data_words {
        let y_key = ((w.y1 + w.y2) / 2.0 * 2.0).round() as i64; // 0.5pt bins
        y_groups.entry(y_key).or_default().push(w);
    }

    // Merge adjacent y-groups (within 8pt = same logical row)
    let mut merged_rows: Vec<Vec<&BboxWord>> = Vec::new();
    let mut current_row: Vec<&BboxWord> = Vec::new();
    let mut last_y: Option<i64> = None;

    for (y_key, group_words) in &y_groups {
        if let Some(prev_y) = last_y {
            if (y_key - prev_y).abs() > 16 { // 8pt gap = new row
                if !current_row.is_empty() {
                    merged_rows.push(std::mem::take(&mut current_row));
                }
            }
        }
        current_row.extend(group_words.iter());
        last_y = Some(*y_key);
    }
    if !current_row.is_empty() {
        merged_rows.push(current_row);
    }

    // For each row, extract values from each column
    let mut rows = Vec::new();
    for row_words in &merged_rows {
        let y_center = row_words.iter().map(|w| (w.y1 + w.y2) / 2.0).sum::<f64>()
            / row_words.len() as f64;

        let mut depth_top = None;
        let mut depth_base = None;
        let mut description = None;
        let mut spt_n = None;
        let mut sample_type = None;

        for col in columns {
            // Words in this row that fall within this column
            let col_words: Vec<&&BboxWord> = row_words.iter()
                .filter(|w| {
                    let wx = (w.x1 + w.x2) / 2.0;
                    wx >= col.x_min - 10.0 && wx <= col.x_max + 10.0
                })
                .collect();

            let text: String = col_words.iter().map(|w| w.text.as_str()).collect::<Vec<_>>().join(" ");
            if text.trim().is_empty() { continue; }

            match col.role {
                ColumnRole::Depth => {
                    // Try to parse depth value(s)
                    let nums: Vec<f64> = text.split_whitespace()
                        .filter_map(|s| s.replace(',', ".").parse::<f64>().ok())
                        .filter(|&n| n >= 0.0 && n < 200.0)
                        .collect();
                    if nums.len() >= 2 {
                        depth_top = Some(nums[0]);
                        depth_base = Some(nums[1]);
                    } else if nums.len() == 1 {
                        depth_top = Some(nums[0]);
                    }
                }
                ColumnRole::Description => {
                    description = Some(text.trim().to_string());
                }
                ColumnRole::Spt => {
                    if let Some(n) = text.split_whitespace()
                        .filter_map(|s| s.parse::<u32>().ok())
                        .filter(|&n| n <= 400)
                        .last()
                    {
                        spt_n = Some(n);
                    }
                }
                ColumnRole::Sample => {
                    let upper = text.to_uppercase();
                    if upper.contains("UDS") || upper.contains('U') {
                        sample_type = Some("U".to_string());
                    } else if upper.contains('D') {
                        sample_type = Some("D".to_string());
                    }
                }
                _ => {}
            }
        }

        // Only keep rows that have at least a depth or description
        if depth_top.is_some() || description.is_some() {
            rows.push(SpatialRow {
                y_center, depth_top, depth_base, description,
                spt_n, sample_type,
                confidence: if depth_top.is_some() && description.is_some() { 0.90 } else { 0.60 },
            });
        }
    }

    rows
}

/// High-level: try spatial extraction on a PDF. Returns geology layers if successful.
/// Falls back to None if the PDF doesn't have usable bbox data.
pub fn try_spatial_extraction(pdf_path: &Path) -> Option<Vec<SpatialRow>> {
    let words = extract_bbox(pdf_path).ok()?;
    if words.len() < 20 { return None; } // Too few words for table detection

    let columns = detect_columns(&words, 30.0); // 30pt tolerance
    if columns.len() < 2 { return None; } // Need at least depth + description

    let has_depth = columns.iter().any(|c| c.role == ColumnRole::Depth);
    let has_desc = columns.iter().any(|c| c.role == ColumnRole::Description);
    if !has_depth || !has_desc { return None; }

    let rows = extract_spatial_rows(&words, &columns);
    if rows.is_empty() { return None; }

    log::info!("Spatial extraction: {} columns, {} rows detected", columns.len(), rows.len());
    for col in &columns {
        log::info!("  Column: x={:.0} role={:?} header={:?}", col.x_center, col.role, col.header);
    }

    Some(rows)
}
'''

# This will be integrated into scaffold_files.json as:
# "SRC_TAURI/src\\pipeline\\spatial.rs": <content above>

def get_spatial_rs():
    """Return the Rust source for spatial.rs"""
    return SPATIAL_RS

if __name__ == "__main__":
    print(f"spatial.rs: {len(SPATIAL_RS)} chars")
    print("Add to scaffold_files.json as SRC_TAURI/src\\\\pipeline\\\\spatial.rs")
