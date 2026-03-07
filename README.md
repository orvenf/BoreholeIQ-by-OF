BoreholeIQ r27 v2

Converts borehole PDFs, images, and spreadsheets into AGS4, CSV, and DIGGS XML.
Runs offline. No cloud, no API keys, no data leaves the machine.
Prototype by Orven Fajardo.


How It Works


Drop a borehole report PDF (scanned or digital)
The app extracts text via OCR or native text layer
A local AI model (Ollama) or pattern matcher parses the geotechnical data
Output: AGS4, OpenGround-ready CSVs, DIGGS XML, quality report

Works with borehole logs, CPT reports, lab certificates. Supports 25 languages including Indonesian, Vietnamese, Thai, Malay, and Filipino.



![BoreholeIQ main window](BoreholeIQ-Screenshots/R27_UI.png)




Install
Copy the rev2_r27 folder to a Windows machine. Right-click deploy.bat, Run as administrator. Takes ~25 minutes on a fresh machine. Installs everything from scratch: compilers, OCR engine, AI model, then builds the app.
If it fails, re-run. It skips completed steps.
Output: C:\BoreholeIQ\src-tauri\target\release\borehole-iq.exe



What It Produces
Per borehole:


output.ags — AGS4, self-validated
loca.csv, geol.csv, samp.csv, ispt.csv — OpenGround-ready CSVs
openground_mapping.xml — CSV import mapping for OpenGround
output.diggs.xml — DIGGS 2.5.x for US market
manifest.json — extraction summary with quality score
provenance.json — audit trail



Per batch: project.ags (combined), batch_summary.html



AI Models
The deploy auto-detects RAM and picks a model:
RAMModelNotes< 8 GBNonePattern matching only8-11 GBphi3:miniBasic AI12-23 GBphi3:mediumDefault for most machines24-47 GBllama3.1:8bBetter accuracy48+ GBmistral-nemo:12bBest extraction
To use a different model:
ollama pull llama3.1:70b
Create %LOCALAPPDATA%\BoreholeIQ\ai_config.json:
json{"model": "llama3.1:70b", "timeout_secs": 600, "context_chars": 12000}
Restart the app.
AI runs on CPU. First file may take 2-5 minutes while the model loads. Subsequent files are faster. The app falls back to pattern matching if AI is slow or unavailable.



Tips



First file is slow: The AI model loads into RAM on first use. Let it finish — subsequent files are much faster.
Wrong language?: Check the language dropdown. Indonesian reports need "Indonesian" not "English".
Low confidence warnings: Pattern matching found data but depths may be approximate. AI mode gives better results.
Batch processing: Add multiple files, click Process. Gets a combined project.ags and summary report.
Preview: Click "DONE" on a completed file to see extracted layers.
CLI mode: boreholeiq.exe --batch input_dir --output output_dir --lang eng
Dictionary: The app learns from successful extractions. Files in %LOCALAPPDATA%\BoreholeIQ\dictionary\.



Requirements
MinimumRecommendedOSWindows 10 64-bitWindows 11RAM4 GB (no AI)16 GBDisk10 GB50 GB



Troubleshooting
ProblemFixBuild fails at Step 4Check scaffold_files.json size matches. Delete %LOCALAPPDATA%\BoreholeIQ\state\4-app.ok, re-run.AI times outNormal on first file — model is loading. Wait or switch to REGEX mode.AI never worksCreate ai_config.json with model name from ollama list.No layers extractedTry different extraction mode (Auto vs Pattern). Check language setting.SSL errors during deployNormal on corporate networks. Deploy handles this automatically.



What Changed from R26


Batch AGS4 output, DIGGS XML, OpenGround mapping XML
AGS4 self-validation, quality scoring, provenance audit
Page classification, depth calibration, gap detection
XLSX and AGS input support
Drag-and-drop, output preview panel
Language auto-detection and persistence
SE-Asian keyword support
AI warm-up and extended timeout for CPU inference
Cleaned up UI







Built with Tauri 2 + React + Rust. OCR via Tesseract 5. AI via Ollama.
