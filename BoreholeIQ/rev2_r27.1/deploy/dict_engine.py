"""
BoreholeIQ v2 R27 - deploy/dict_engine.py
Advanced Dictionary Engine

Generates enhanced Rust source for models/userdict.rs with:
- Auto-learning from successful extractions
- Frequency-weighted term matching
- Dictionary-driven column header detection
- OCR confidence feedback (auto-add near-misses to ocr_fixes.json)
- Format templates for known report layouts
- Cross-file project defaults propagation
"""

DICT_EXTENSIONS_RS = r'''
// ── Auto-Learning ─────────────────────────────────────────────────────────
// Saves successful extraction patterns for future matching.

/// Record a successful term match for frequency tracking.
pub fn record_match(&self, term: &str) {
    let freq_path = self.folder.join("_frequency.json");
    let mut freq: std::collections::HashMap<String, u64> = match std::fs::read_to_string(&freq_path) {
        Ok(c) => serde_json::from_str(&c).unwrap_or_default(),
        Err(_) => std::collections::HashMap::new(),
    };
    let upper = term.to_uppercase();
    *freq.entry(upper).or_insert(0) += 1;
    let _ = std::fs::write(&freq_path, serde_json::to_string_pretty(&freq).unwrap_or_default());
}

/// Get frequency-sorted terms (most common first).
pub fn terms_by_frequency(&self) -> Vec<(String, String)> {
    let freq_path = self.folder.join("_frequency.json");
    let freq: std::collections::HashMap<String, u64> = match std::fs::read_to_string(&freq_path) {
        Ok(c) => serde_json::from_str(&c).unwrap_or_default(),
        Err(_) => std::collections::HashMap::new(),
    };
    let mut terms: Vec<_> = self.terms.iter()
        .map(|(k, v)| (k.clone(), v.clone(), freq.get(k).copied().unwrap_or(0)))
        .collect();
    terms.sort_by(|a, b| b.2.cmp(&a.2)); // Most frequent first
    terms.into_iter().map(|(k, v, _)| (k, v)).collect()
}

// ── OCR Feedback Loop ─────────────────────────────────────────────────────
// Auto-detects near-misses and suggests/adds OCR corrections.

/// Check if a word is a near-miss for any dictionary term (edit distance 1-2).
/// If so, auto-add to ocr_fixes.json for future correction.
pub fn check_ocr_near_miss(&self, word: &str) -> Option<String> {
    let upper = word.to_uppercase();
    if upper.len() < 4 { return None; } // Skip short words

    // Check all terms for edit distance
    for (term, _legend) in &self.terms {
        if term == &upper { return None; } // Exact match, not a near-miss
        if edit_distance(&upper, term) <= 2 && upper.len() >= 4 {
            // This is a near-miss - auto-add to OCR fixes
            self.auto_add_ocr_fix(&upper, term);
            return Some(term.clone());
        }
    }

    // Also check against hardcoded soil keywords
    let soil_terms = [
        "CLAY", "SAND", "SILT", "GRAVEL", "PEAT", "FILL", "TOPSOIL", "ROCK",
        "LEMPUNG", "PASIR", "LANAU", "KERIKIL", "GAMBUT", "TANAH",
        "MUDSTONE", "SANDSTONE", "LIMESTONE",
    ];
    for &soil in &soil_terms {
        if edit_distance(&upper, soil) <= 1 && upper != soil {
            self.auto_add_ocr_fix(&upper, soil);
            return Some(soil.to_string());
        }
    }
    None
}

fn auto_add_ocr_fix(&self, wrong: &str, correct: &str) {
    let fixes_path = self.folder.join("ocr_fixes.json");
    let mut fixes: std::collections::HashMap<String, String> = match std::fs::read_to_string(&fixes_path) {
        Ok(c) => {
            let stripped = strip_comments(&c);
            serde_json::from_str(&stripped).unwrap_or_default()
        }
        Err(_) => std::collections::HashMap::new(),
    };
    let key = wrong.to_uppercase();
    if !fixes.contains_key(&key) {
        fixes.insert(key.clone(), correct.to_string());
        // Write back with comment
        if let Ok(json) = serde_json::to_string_pretty(&fixes) {
            let _ = std::fs::write(&fixes_path, json);
            log::info!("Auto-added OCR fix: '{}' -> '{}'", key, correct);
        }
    }
}

/// Simple Levenshtein edit distance.
fn edit_distance(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let (m, n) = (a.len(), b.len());
    let mut dp = vec![vec![0usize; n + 1]; m + 1];
    for i in 0..=m { dp[i][0] = i; }
    for j in 0..=n { dp[0][j] = j; }
    for i in 1..=m {
        for j in 1..=n {
            let cost = if a[i-1] == b[j-1] { 0 } else { 1 };
            dp[i][j] = (dp[i-1][j] + 1).min(dp[i][j-1] + 1).min(dp[i-1][j-1] + cost);
        }
    }
    dp[m][n]
}

// ── Column Header Detection ───────────────────────────────────────────────
// Uses dictionary metadata_keys to identify table column headers.

/// Given a list of potential header strings, identify which standard field they map to.
pub fn identify_header(&self, text: &str) -> Option<String> {
    let upper = text.trim().to_uppercase();
    // Check user metadata keys first
    if let Some(standard) = self.metadata_keys.get(&upper) {
        return Some(standard.clone());
    }
    // Check partial matches (header might be "KEDALAMAN (m)" but key is "KEDALAMAN")
    for (key, standard) in &self.metadata_keys {
        if upper.contains(key.as_str()) {
            return Some(standard.clone());
        }
    }
    None
}

// ── Format Templates ──────────────────────────────────────────────────────
// Reusable column layouts for known report formats.

/// Load format templates from templates.json
pub fn load_templates(&self) -> Vec<FormatTemplate> {
    let path = self.folder.join("templates.json");
    match std::fs::read_to_string(&path) {
        Ok(c) => {
            let stripped = strip_comments(&c);
            serde_json::from_str(&stripped).unwrap_or_default()
        }
        Err(_) => Vec::new(),
    }
}

/// Save a discovered template for future use.
pub fn save_template(&self, template: &FormatTemplate) {
    let path = self.folder.join("templates.json");
    let mut templates = self.load_templates();
    // Don't duplicate
    if templates.iter().any(|t| t.name == template.name) { return; }
    templates.push(template.clone());
    if let Ok(json) = serde_json::to_string_pretty(&templates) {
        let _ = std::fs::write(&path, json);
        log::info!("Saved format template: {}", template.name);
    }
}

// ── Cross-File Defaults ───────────────────────────────────────────────────
// Propagates discovered project info across files in a batch.

/// Update defaults from a successfully extracted borehole (non-destructive).
pub fn propagate_defaults(&self, crs: Option<&str>, project: Option<&str>, company: Option<&str>) {
    let defaults_path = self.folder.join("defaults.json");
    let mut defaults: serde_json::Value = match std::fs::read_to_string(&defaults_path) {
        Ok(c) => {
            let stripped = strip_comments(&c);
            serde_json::from_str(&stripped).unwrap_or(serde_json::json!({}))
        }
        Err(_) => serde_json::json!({}),
    };
    let mut changed = false;
    if let Some(c) = crs {
        if defaults.get("crs").and_then(|v| v.as_str()).is_none() || defaults["crs"].is_null() {
            defaults["crs"] = serde_json::Value::String(c.to_string());
            changed = true;
        }
    }
    if let Some(p) = project {
        if defaults.get("project_name").and_then(|v| v.as_str()).is_none() || defaults["project_name"].is_null() {
            defaults["project_name"] = serde_json::Value::String(p.to_string());
            changed = true;
        }
    }
    if let Some(co) = company {
        if defaults.get("company").and_then(|v| v.as_str()).is_none() || defaults["company"].is_null() {
            defaults["company"] = serde_json::Value::String(co.to_string());
            changed = true;
        }
    }
    if changed {
        if let Ok(json) = serde_json::to_string_pretty(&defaults) {
            let _ = std::fs::write(&defaults_path, json);
            log::info!("Auto-propagated project defaults");
        }
    }
}
'''

TEMPLATE_STRUCT_RS = r'''
/// A reusable format template for a known borehole report layout.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FormatTemplate {
    /// Human-readable name (e.g., "PT Geoteknik Indonesia - Standard Log")
    pub name: String,
    /// Company or source that uses this format
    pub source: String,
    /// Column definitions: position (0-indexed from left) -> role
    pub columns: Vec<TemplateColumn>,
    /// Regex pattern that identifies this format (matched against first page text)
    pub identifier_pattern: Option<String>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TemplateColumn {
    /// Column position (0 = leftmost)
    pub position: usize,
    /// What this column contains
    pub role: String, // "depth", "description", "spt", "sample", "recovery", "rqd"
    /// Approximate x-coordinate center (in PDF points, for spatial matching)
    pub x_approx: Option<f64>,
}
'''

EXAMPLE_TEMPLATES_JSON = '''{
    // ── Format Templates ──
    // Each template describes a known report layout.
    // BoreholeIQ auto-detects which template matches and uses it
    // for column identification instead of guessing.

    // To add a new template:
    // 1. Open a borehole PDF from the drilling company
    // 2. Note the column order (left to right)
    // 3. Add an entry here with the column positions

    // Example templates are commented out - uncomment and edit to match your reports.

    // [
    //     {
    //         "name": "PT Geoteknik - Standard Borehole Log",
    //         "source": "PT Geoteknik Indonesia",
    //         "columns": [
    //             {"position": 0, "role": "depth", "x_approx": 50},
    //             {"position": 1, "role": "casing", "x_approx": 100},
    //             {"position": 2, "role": "symbol", "x_approx": 150},
    //             {"position": 3, "role": "description", "x_approx": 300},
    //             {"position": 4, "role": "spt", "x_approx": 450},
    //             {"position": 5, "role": "sample", "x_approx": 520}
    //         ],
    //         "identifier_pattern": "PT Geoteknik"
    //     }
    // ]
}
'''


def get_dict_extensions_rs():
    return DICT_EXTENSIONS_RS

def get_template_struct_rs():
    return TEMPLATE_STRUCT_RS

def get_example_templates_json():
    return EXAMPLE_TEMPLATES_JSON

if __name__ == "__main__":
    print(f"dict_extensions: {len(DICT_EXTENSIONS_RS)} chars")
    print(f"template_struct: {len(TEMPLATE_STRUCT_RS)} chars")
    print("These get merged into scaffold userdict.rs and added as templates.json")
