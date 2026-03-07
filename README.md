
# BoreholeIQ v2 R27

**Offline borehole data extraction for PDFs, images, and spreadsheets**

BoreholeIQ converts geotechnical source files into **AGS4**, **OpenGround-ready CSV**, and **DIGGS XML**.

It runs **fully offline** on Windows. No cloud services, no API keys, and no data leaves the machine.

> Prototype by Orven Fajardo

![BoreholeIQ main window](BoreholeIQ-Screenshots/R27_UI.png)

---

## Overview

BoreholeIQ is a Windows desktop prototype for extracting structured geotechnical data from borehole reports and related source files.

It supports both **digital PDFs** and **scanned documents**, combining native text extraction, OCR, deterministic parsing, and optional local AI to produce outputs suitable for downstream engineering workflows.

---

## Key Features

- Fully offline processing
- No cloud services or external API keys
- Converts PDFs, images, and spreadsheets into structured engineering outputs
- Supports AGS4, OpenGround-ready CSV, and DIGGS XML
- Works with both native-text and scanned PDFs
- Optional local AI parsing through Ollama
- Deterministic pattern-matching fallback
- Batch processing support
- Quality scoring and provenance tracking
- Support for 25 languages, including Indonesian, Vietnamese, Thai, Malay, and Filipino

---

## Supported Inputs

- Borehole log PDFs
- Scanned reports
- Images
- CPT reports
- Laboratory certificates
- Spreadsheets
- XLSX files
- AGS files

---

## Produced Outputs

### Per borehole

- `output.ags` — AGS4 output with self-validation
- `loca.csv` — OpenGround-ready location data
- `geol.csv` — OpenGround-ready geology data
- `samp.csv` — OpenGround-ready sample data
- `ispt.csv` — OpenGround-ready SPT data
- `openground_mapping.xml` — CSV import mapping for OpenGround
- `output.diggs.xml` — DIGGS 2.5.x output
- `manifest.json` — extraction summary with quality score
- `provenance.json` — audit trail

### Per batch

- `project.ags` — combined AGS4 output
- `batch_summary.html` — batch processing summary

---

## How It Works

1. Add a borehole PDF, image, or spreadsheet.
2. BoreholeIQ extracts text using either:
   - the native PDF text layer, or
   - OCR for scanned documents.
3. The extracted content is parsed using:
   - a local AI model through **Ollama**, or
   - deterministic pattern matching.
4. The application generates structured outputs and a quality report.

---

## Installation

Copy the `rev2_r27` folder to a Windows machine.

Then:

1. Right-click `deploy.bat`
2. Select **Run as administrator**

On a fresh machine, installation typically takes around **25 minutes**.

The deployment process installs required components from scratch, including:

- Build tools
- OCR runtime
- Local AI runtime
- Application dependencies

If deployment stops partway through, run `deploy.bat` again. Completed steps are skipped automatically.

### Output executable

```text
C:\BoreholeIQ\src-tauri\target\release\borehole-iq.exe
````

---

## AI Model Selection

During deployment, BoreholeIQ detects available RAM and selects a model automatically.

| RAM            | Model              | Notes                     |
| -------------- | ------------------ | ------------------------- |
| Less than 8 GB | None               | Pattern matching only     |
| 8–11 GB        | `phi3:mini`        | Basic AI mode             |
| 12–23 GB       | `phi3:medium`      | Default for most machines |
| 24–47 GB       | `llama3.1:8b`      | Higher accuracy           |
| 48+ GB         | `mistral-nemo:12b` | Best extraction quality   |

### Use a different model

Run:

```bash
ollama pull llama3.1:70b
```

Create:

```text
%LOCALAPPDATA%\BoreholeIQ\ai_config.json
```

With:

```json
{
  "model": "llama3.1:70b",
  "timeout_secs": 600,
  "context_chars": 12000
}
```

Then restart the application.

### Notes

* AI runs on **CPU**
* The first file may take **2 to 5 minutes** while the model loads
* Subsequent files are usually faster
* If AI is unavailable or too slow, the app falls back to pattern matching

---

## Usage Notes

### First file is slow

The AI model loads into RAM on first use. This is expected.

### Wrong language selected

Check the language dropdown. For example, Indonesian reports should use **Indonesian**, not **English**.

### Low confidence warnings

Pattern matching found data, but some depths may be approximate. AI mode usually improves extraction quality.

### Batch processing

Add multiple files and click **Process** to generate a combined `project.ags` and summary report.

### Preview

Click **DONE** on a completed file to preview extracted layers.

### CLI mode

```bash
boreholeiq.exe --batch input_dir --output output_dir --lang eng
```

### Dictionary learning

The application stores learned extraction data in:

```text
%LOCALAPPDATA%\BoreholeIQ\dictionary\
```

---

## System Requirements

| Requirement | Minimum                  | Recommended |
| ----------- | ------------------------ | ----------- |
| OS          | Windows 10 64-bit        | Windows 11  |
| RAM         | 4 GB (pattern mode only) | 16 GB       |
| Disk space  | 10 GB                    | 50 GB       |

---

## Troubleshooting

| Problem                  | Recommended action                                                                                                                 |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| Build fails at Step 4    | Check that `scaffold_files.json` is the expected size. Delete `%LOCALAPPDATA%\BoreholeIQ\state\4-app.ok` and run deployment again. |
| AI times out             | This is normal on the first file while the model loads. Wait or switch to **REGEX** mode.                                          |
| AI never starts          | Create `ai_config.json` using a valid model name from `ollama list`.                                                               |
| No layers extracted      | Try a different extraction mode (**Auto** vs **Pattern**) and verify the selected language.                                        |
| SSL errors during deploy | Common on some corporate networks. The deploy process is designed to handle this automatically.                                    |

---

## What’s New in R27

* Batch AGS4 output
* DIGGS XML export
* OpenGround mapping XML
* AGS4 self-validation
* Quality scoring
* Provenance audit output
* Page classification
* Depth calibration
* Gap detection
* XLSX and AGS input support
* Drag-and-drop support
* Output preview panel
* Language auto-detection and persistence
* Southeast Asian keyword support
* AI warm-up and extended CPU inference timeout
* Cleaner UI

---

## Technology Stack

* **Tauri 2**
* **React**
* **Rust**
* **Tesseract 5** for OCR
* **Ollama** for local AI inference
