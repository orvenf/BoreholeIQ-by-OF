# BoreholeIQ v2 — Build R27

Prototype by Orven Fajardo

Converts borehole PDFs, images, and spreadsheets into AGS4, CSV, and DIGGS XML. Runs offline on Windows. No cloud, no API keys, no data leaves the machine.

---

## What Changed from R26

R26 was the first working build. R27 adds:

- OpenGround-aligned CSV headers (LOCA, GEOL, SAMP, ISPT groups) — zero-config import
- Auto-generated `openground_mapping.xml` for OpenGround's CSV import wizard
- Batch AGS4 output (`project.ags` with all boreholes in one file)
- DIGGS XML output for US market (ASCE standard)
- AGS4 self-validation before writing (checks structure, field counts, cross-references)
- Provenance audit trail (`provenance.json` per borehole)
- Quality score (0-100) per borehole with completeness report
- Page classification — filters out cover pages and narrative sections before extraction
- Depth calibration validation — warns if extracted depth doesn't match header total depth
- Gap detection — flags missing geology between consecutive layers
- Graceful degradation — always produces output even on partial extraction
- Water level extraction to AGS WSTB group
- XLSX input support via calamine (direct parsing, no OCR needed)
- AGS input for round-trip editing (load existing AGS, fix, re-export)
- Language auto-detection via whatlang (re-runs OCR if language mismatch detected)
- OCR language persistence (remembers your selection between sessions)
- Output preview panel — click a completed file to see extracted layers
- Drag-and-drop file loading (Tauri native)
- SE-Asian keyword support: Indonesian, Vietnamese, Thai, Malay, Filipino borehole terms
- Metadata extraction: project name, client, contractor, location, water level from headers
- Output templates for custom CSV column names
- CLI batch mode: `boreholeiq.exe --batch input/ --output output/`
- Dictionary auto-learning capped at 10,000 entries
- Bulletproof deployment: handles Windows Store Python aliases, SSL fallback, Unicode in console

---

## Install (Fresh Machine)

Copy the `rev2_r27` folder to the machine. Right-click `deploy.bat`, Run as administrator. Walk away. Takes about 25 minutes on a fresh Windows 10/11 machine.

What gets installed: VC++ Redist, MSVC Build Tools, Node 20, Rust, Tesseract 5 + 25 languages, Poppler, Ollama + AI model, then builds the app from source.

If it fails partway through, re-run `deploy.bat`. It skips completed steps automatically.

The output is an MSI installer at `C:\BoreholeIQ\src-tauri\target\release\bundle\msi\` and an executable at `C:\BoreholeIQ\src-tauri\target\release\borehole-iq.exe`.

---

## Folder Structure

```
deploy.bat              ← right-click, Run as Administrator
deploy/
  ├── config.json       ← versions, URLs, paths
  ├── utils.py          ← shared utilities
  ├── 1_prereqs.py      ← MSVC, Node, Rust, WebView2, Tauri CLI
  ├── 2_libraries.py    ← Tesseract OCR + 25 languages, Poppler
  ├── 3_ollama.py       ← AI sidecar (optional, fail-forward)
  ├── 4_app.py          ← scaffold source + build
  ├── ingest_spatial.py ← spatial PDF extraction (Rust source)
  └── dict_engine.py    ← dictionary engine (Rust source)
scaffolds/
  └── scaffold_files.json ← 40 source files
```

---

## Supported Formats

**Input:** PDF (scanned or born-digital), PNG, JPG, TIFF, BMP, WEBP, XLSX, XLS, AGS

**Output per borehole:**

| File | What |
|------|------|
| output.ags | AGS4, self-validated |
| loca.csv | Location (OpenGround headers) |
| geol.csv | Geology layers |
| samp.csv | Samples |
| ispt.csv | SPT results |
| output.diggs.xml | DIGGS 2.5.x XML |
| openground_mapping.xml | Pre-configured CSV mapping for OpenGround |
| manifest.json | Extraction summary + quality score |
| provenance.json | Audit trail |

**Batch output:** `project.ags` (combined multi-hole), `batch_summary.html` (visual report)

---

## AI Model Tiers

The deploy script auto-detects RAM and picks the best model:

| Tier | RAM | Model | Pull Size | What You Get |
|------|-----|-------|-----------|-------------|
| 1 | < 8 GB | None | 0 | Regex + spatial extraction only |
| 2 | 8-11 GB | phi3:mini | 2.3 GB | Basic AI-assisted extraction |
| 3 | 12-23 GB | phi3:medium | 7.5 GB | Good extraction quality |
| 4 | 24-47 GB | llama3.1:8b | 4.7 GB | Better instruction following |
| 5 | 48+ GB | mistral-nemo:12b | 7.1 GB | Strongest extraction |

### Using a Different Model

If you have a powerful machine and want something bigger:

1. Pull the model: `ollama pull llama3.1:70b`
2. Create or edit `%LOCALAPPDATA%\BoreholeIQ\ai_config.json`:
```json
{"model": "llama3.1:70b", "timeout_secs": 120, "context_chars": 12000}
```
3. Restart the app.

Models that work well for geotechnical extraction:

| Model | Download | RAM Needed | Notes |
|-------|----------|-----------|-------|
| deepseek-r1:70b | 40 GB | 48+ GB | Best reasoning, slowest |
| llama3.1:70b | 40 GB | 48+ GB | Excellent general extraction |
| mistral-nemo:12b | 7 GB | 16+ GB | Good balance of speed and quality |
| llama3.1:8b | 4.7 GB | 12+ GB | Fast, good enough for clean PDFs |
| phi3:medium | 7.5 GB | 12+ GB | Default for 16 GB machines |
| phi3:mini | 2.3 GB | 8+ GB | Minimum viable AI |

Increase `timeout_secs` for bigger models (they take longer). Increase `context_chars` if the model supports larger context windows — more of the borehole text gets sent in one shot.

---

## Tips

**First run on a new machine:** The build takes 25 minutes because it compiles from source. After that, you have an MSI you can distribute. Users install the MSI in 30 seconds.

**VM testing:** Take a snapshot after a successful build. Revert to that snapshot for testing — don't rebuild every time.

**If Ollama AI shows 404:** Create `%LOCALAPPDATA%\BoreholeIQ\ai_config.json` with the exact model name from `ollama list`. Restart the app.

**If extraction quality is poor:** Check the OCR language setting (top bar). Indonesian borehole logs need "Indonesian" not "English". The app now remembers your selection.

**If layers are missing:** The extraction log shows gap warnings. These usually mean the PDF layout is complex. Try "Auto" mode which uses spatial table extraction as a fallback.

**Low confidence warnings (50%):** These come from the keyword fallback extractor. It found soil terms but couldn't match them to specific depth ranges. The data is there but depths may be approximate.

**Dictionary learning:** The app auto-learns from successful extractions. The more files you process, the better it gets at recognizing your contractors' report formats. Dictionary files are in `%LOCALAPPDATA%\BoreholeIQ\dictionary\`.

**Output preview:** After processing, click the green "DONE" label on any file to see the extracted layers in a table.

**Batch processing:** Drag or add multiple files, click Process. The app generates `batch_summary.html` and a combined `project.ags` for one-shot OpenGround import.

**Custom CSV columns:** If your OpenGround deployment uses non-standard column names, create an output template in `%LOCALAPPDATA%\BoreholeIQ\dictionary\output_templates.json`.

**CLI mode:** For scripting: `boreholeiq.exe --batch input_dir --output output_dir --lang eng`

---

## System Requirements

| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 64-bit | Windows 11 |
| RAM | 4 GB (no AI) | 16 GB |
| Disk | 10 GB free | 50 GB free |
| CPU | Any x64 | 4+ cores |

---

## Known Limitations

- Ollama AI requires the correct model name in `ai_config.json` if auto-detection doesn't match
- XLSX parsing works for tabular borehole data with recognizable column headers — not arbitrary spreadsheet layouts
- CPT trace digitization (graphical curves) is not supported — only tabular CPT data
- Handwritten borehole logs (pre-1980) have significantly lower extraction accuracy
- The app builds from source — first deployment requires MSVC Build Tools, Rust, and Node.js

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `exit 9009` during deploy | Windows Store Python alias. The latest deploy.bat handles this automatically. |
| `powershell not recognized` | Fixed in R27 — deploy.bat uses full path. |
| Rust build fails | Check `scaffold_files.json` size matches what was provided. Delete `%LOCALAPPDATA%\BoreholeIQ\state\4-app.ok` and re-run. |
| SSL certificate errors | Normal on corporate networks. The deploy auto-falls back to unverified HTTPS. |
| Ollama 404 error | Create `ai_config.json` with the model name from `ollama list`. |
| No layers extracted | Check OCR language setting. Try a different extraction mode (Auto vs Pattern). |
| App won't start after reboot | Tesseract and Poppler need to be in PATH. Re-run deploy.bat (it re-adds them). |

---

## Files on Disk

| Location | What |
|----------|------|
| `C:\BoreholeIQ\` | App source and build output |
| `%LOCALAPPDATA%\BoreholeIQ\dictionary\` | User dictionary, terms, OCR fixes, templates |
| `%LOCALAPPDATA%\BoreholeIQ\hw_profile.json` | Detected hardware tier and AI model |
| `%LOCALAPPDATA%\BoreholeIQ\ai_config.json` | AI model override (create manually if needed) |
| `%LOCALAPPDATA%\BoreholeIQ\state\` | Deploy step completion markers |
| `%TEMP%\BoreholeIQ-deploy.log` | Deploy log |

---

Prototype by Orven Fajardo
