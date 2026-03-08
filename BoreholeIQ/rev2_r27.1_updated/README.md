# BoreholeIQ v2

Converts borehole PDFs, images, and spreadsheets into AGS4, CSV, and DIGGS XML.

Runs offline. No cloud, no API keys, no data leaves the machine.

Prototype by Orven Fajardo.

---

## How It Works

1. Drop a borehole report PDF (scanned or digital)
2. The app extracts text via OCR or native text layer
3. A local AI model (Ollama) or pattern matcher parses the geotechnical data
4. Output: AGS4, OpenGround-ready CSVs, DIGGS XML, quality report

Works with borehole logs, CPT reports, lab certificates. Supports 25 languages including Indonesian, Vietnamese, Thai, Malay, and Filipino.

---

## Install

Copy the `rev2_r27` folder to a Windows machine. Right-click `deploy.bat`, Run as administrator. Takes ~25 minutes on a fresh machine. Installs everything from scratch: compilers, OCR engine, AI model, then builds the app.

If it fails, re-run. It skips completed steps.

Output: `C:\BoreholeIQ\src-tauri\target\release\borehole-iq.exe`

---

## What It Produces

Per borehole:

- `output.ags` — AGS4, self-validated
- `loca.csv`, `geol.csv`, `samp.csv`, `ispt.csv` — OpenGround-ready CSVs
- `openground_mapping.xml` — CSV import mapping for OpenGround
- `output.diggs.xml` — DIGGS 2.5.x for US market
- `manifest.json` — extraction summary with quality score
- `provenance.json` — audit trail

Per batch: `project.ags` (combined), `batch_summary.html`

---

## AI Models

The deploy auto-detects RAM and picks a model:

| RAM | Model | Notes |
|-----|-------|-------|
| < 8 GB | None | Pattern matching only |
| 8-11 GB | phi3:mini | Basic AI |
| 12-23 GB | phi3:medium | Default for most machines |
| 24-47 GB | llama3.1:8b | Better accuracy |
| 48+ GB | mistral-nemo:12b | Best extraction |

To use a different model:

```
ollama pull llama3.1:70b
```

Create `%LOCALAPPDATA%\BoreholeIQ\ai_config.json`:
```json
{"model": "llama3.1:70b", "timeout_secs": 600, "context_chars": 12000}
```

Restart the app.

AI runs on CPU. First file may take 2-5 minutes while the model loads. Subsequent files are faster. The app falls back to pattern matching if AI is slow or unavailable.

---

## Tips

- **First file is slow**: The AI model loads into RAM on first use. Let it finish — subsequent files are much faster.
- **Wrong language?**: Check the language dropdown. Indonesian reports need "Indonesian" not "English".
- **Low confidence warnings**: Pattern matching found data but depths may be approximate. AI mode gives better results.
- **Batch processing**: Add multiple files, click Process. Gets a combined `project.ags` and summary report.
- **Preview**: Click "DONE" on a completed file to see extracted layers.
- **CLI mode**: `boreholeiq.exe --batch input_dir --output output_dir --lang eng`
- **Dictionary**: The app learns from successful extractions. Files in `%LOCALAPPDATA%\BoreholeIQ\dictionary\`.

---

## Requirements

| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 64-bit | Windows 11 |
| RAM | 4 GB (no AI) | 16 GB |
| Disk | 10 GB | 50 GB |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Build fails at Step 4 | Check scaffold_files.json size matches. Delete `%LOCALAPPDATA%\BoreholeIQ\state\4-app.ok`, re-run. |
| AI times out | Normal on first file — model is loading. Wait or switch to REGEX mode. |
| AI never works | Create `ai_config.json` with model name from `ollama list`. |
| No layers extracted | Try different extraction mode (Auto vs Pattern). Check language setting. |
| SSL errors during deploy | Normal on corporate networks. Deploy handles this automatically. |

---

## What Changed from R26

- Batch AGS4 output, DIGGS XML, OpenGround mapping XML
- AGS4 self-validation, quality scoring, provenance audit
- Page classification, depth calibration, gap detection
- XLSX and AGS input support
- Drag-and-drop, output preview panel
- Language auto-detection and persistence
- SE-Asian keyword support
- AI warm-up and extended timeout for CPU inference
- Cleaned up UI

---

## Project Structure

```
deploy.bat                  ← Run as Administrator
deploy/
  ├── config.json           ← URLs, versions
  ├── utils.py              ← Shared utilities
  ├── 1_prereqs.py          ← MSVC, Node, Rust, WebView2
  ├── 2_libraries.py        ← Tesseract + 25 languages, Poppler
  ├── 3_ollama.py           ← AI engine (optional)
  └── 4_app.py              ← Build the app
scaffolds/
  └── scaffold_files.json   ← 40 source files (Rust + React)
```

Built with Tauri 2 + React + Rust. OCR via Tesseract 5. AI via Ollama.
