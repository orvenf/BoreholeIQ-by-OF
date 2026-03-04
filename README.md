# BoreholeIQ v2  (Experimental)
**Turn borehole reports into AGS4, CSV, and XML – automatically.**  

No more typing or manual copying. Just point BoreholeIQ at your scanned PDFs or images, and it extracts all the geological layers, samples, and test data into standard formats.  


### Main Interface
![BoreholeIQ main window](screenshots/UI_Main.png)


---

## ✨ What it does – quick summary  

| Input | Output | Mode |
|-------|--------|------|
| PDF, PNG, JPG, TIF, BMP, WEBP | AGS4 (`.ags`), CSV, JSON | **Pattern matching** (fast, works offline, no AI) |


- **Your data stays on your machine** – nothing is ever sent to the cloud.  
- **AI is optional** – you can stick with pattern matching, or let the app use AI for trickier logs.  
- **The AI automatically adapts to your computer** – the more powerful your machine, the bigger (and smarter) the model it can run.

---

## 💻 System requirements – what you need  

| Component | Minimum | Recommended for AI |
|-----------|---------|---------------------|
| **OS** | Windows 10/11 (64‑bit only) | same |
| **RAM** | 8 GB | 16 GB or more |
| **VRAM (GPU)** | none (CPU works) | 6 GB+ for larger models |
| **Free disk space** | 20 GB (temporary for build) | 30 GB+ if you want multiple AI models |
| **Internet** | first run only (to download tools) | first AI model download |

> 👋 **New user?** The installer automatically grabs the latest stable versions of everything you need (Python, Node.js, Rust, Tesseract OCR, Poppler, and more). You don't need to install anything manually.

---

## 🧠 How AI scales with your hardware – complete model tiers  

BoreholeIQ uses **Ollama** to run large language models **entirely on your own machine**. The app looks at your system and automatically picks the best model tier for your hardware – but you can always override by setting an environment variable.

Here’s the full list of model tiers, with examples and what hardware you'll need:

| Tier | Model examples (size) | Hardware needed | Best for |
|------|------------------------|------------------|----------|
| **1** | *Pattern matching only* (no model) | any machine | Simple, clean logs (fastest) |
| **2** | `phi3:mini` (2.3 GB)<br>`tinyllama` (0.6 GB) | 8 GB RAM | Basic AI extraction, low‑power machines |
| **3** | `phi3:medium` (7.5 GB)<br>`llama3.2:3b` (2.0 GB)<br>`gemma2:2b` (1.6 GB) | 16 GB RAM | Good balance of speed and accuracy |
| **4** | `llama3.1:8b` (4.7 GB)<br>`mistral:7b` (4.1 GB)<br>`qwen2.5:7b` (4.1 GB) | 32 GB RAM, or 16 GB + 8 GB VRAM | High accuracy, good for complex logs |
| **5** | `deepseek-r1:7b` (4.7 GB)<br>`deepseek-r1:8b` (4.9 GB)<br>`deepseek-coder:6.7b` (3.8 GB)<br>`phi4:14b` (9.1 GB) | 32 GB RAM + 8 GB VRAM | Research‑grade extraction, advanced reasoning |
| **6** | `llama3:70b` (39 GB)<br>`deepseek-r1:67b` (38 GB)<br>`mixtral:8x7b` (26 GB) | 64 GB RAM + 12+ GB VRAM | Maximum accuracy, server‑class machines |
| **7** | `deepseek-r1:671b` (404 GB) | 1 TB+ RAM, multiple GPUs | Overkill for boreholes – but it *can* run! |

> 💡 **Note:** Tier 7 is listed for completeness – you almost certainly won’t need it. The app will never auto‑select anything larger than Tier 5 on typical hardware.

### Where’s DeepSeek? Is it bad for boreholes?  

**DeepSeek models are right there in Tier 5 and Tier 7!**  

We included **DeepSeek R1 (7b, 8b, 67b)** and **DeepSeek Coder** – they're excellent choices if your hardware can handle them. DeepSeek R1 is particularly good at following complex instructions and extracting structured data from messy logs. The smaller DeepSeek models (7b/8b) are tier 5 – they need a decent GPU or lots of RAM, but they often outperform other models of similar size.

So no, DeepSeek is **not bad for boreholes** – in fact, it's one of the top performers. We just don't auto‑select it unless your machine meets the tier 5 requirements, because smaller models like `phi3:mini` work well enough on modest hardware and are much faster.

### How automatic selection works  

The app checks your system and chooses the highest tier that your hardware can comfortably handle. It uses these rough rules:

- **Tier 2** if RAM < 16 GB  
- **Tier 3** if RAM ≥ 16 GB and no NVIDIA GPU  
- **Tier 4** if RAM ≥ 32 GB **or** (16 GB RAM + NVIDIA GPU with ≥ 8 GB VRAM)  
- **Tier 5** if RAM ≥ 64 GB and GPU with ≥ 12 GB VRAM  

You can override by setting the environment variable `BOREHOLEIQ_AI_TIER` to a number (1–7) before launching the app.

### Where are the models stored?  

All downloaded models are kept in:  
```
C:\Users\<your-username>\.ollama\models
```
You can delete models you don’t need from there to free up space. The app will re‑download them if required.

### Can I use other models not listed?  

Yes! If you’re comfortable with Ollama, you can pull any model manually (`ollama pull <model>`) and then set the tier manually. The app will try to use whatever model is configured in `ai_config.json` (located in `%LOCALAPPDATA%\BoreholeIQ\`). Just be aware that very small models might not extract well, and very large ones might be too slow.

---

## 🚀 One‑click setup  

```bash
git clone https://github.com/your-org/boreholeiq.git
cd boreholeiq
```

Then **right‑click** `deploy6.bat` and choose **“Run as administrator”**.  
(If you forget, the script will ask you.)

**Grab a coffee.** The script checks your system, downloads dependencies, and builds the app. It usually takes **15–30 minutes**, depending on your internet speed.  

---

## 🖱️ After setup – how to start the app  

The installer creates two ways to run BoreholeIQ:

### Option 1 – Run directly (no installation)  
Open File Explorer and go to:  
```
C:\BoreholeIQ\src-tauri\target\release\
```
Double‑click `BoreholeIQ.exe`. That's it.  

### Option 2 – Install it properly  
In the same folder, open the `bundle` folder, then `msi`, and double‑click the `.msi` file. This installs BoreholeIQ like a normal Windows program – you'll find it in your Start Menu later.  

> 💡 **Tip:** After the first run, right‑click `BoreholeIQ.exe` and choose **Pin to taskbar** for easy access.  

---

## 🖱️ Your first run  

1. Launch the app (using one of the methods above).  
2. Click **+ Files** and select your borehole reports.  
3. Pick an **output folder**.  
4. Click **PROCESS**.  

Watch the log panel on the right – it shows progress for each file. When finished, your outputs (`.ags`, `.csv`, `.json`) are waiting in the folder you chose.  

---

## 🧠 Using the AI mode (optional, fully offline)  

- Switch the mode in the header dropdown:  
  - **AUTO** – tries AI first, falls back to pattern matching if AI fails or is unavailable.  
  - **AI ONLY** – uses AI exclusively; if AI fails, the file errors.  
  - **REGEX** – pattern matching only (fastest, no AI).  

- The first time you use AI, BoreholeIQ downloads the appropriate model (this happens only once, and the model is saved locally).  
- After that, AI extraction runs **entirely on your machine – no internet required**.  

> **No cloud, no API keys, no subscription.** You own the models, and your data never leaves your PC.  

---

## 🔧 If something goes wrong  

| Issue | Try this |
|-------|----------|
| **Script fails during download** | Your antivirus might be blocking `winget` or direct downloads. Temporarily disable it and run `deploy6.bat` again. |
| **Error about long paths** | The script tries to enable long paths for you. If it fails, turn them on manually: open `gpedit.msc` → Computer Configuration → Administrative Templates → System → Filesystem → **Enable Win32 long paths**. |
| **Python not found after install** | A quick reboot usually fixes the PATH. Restart your PC and run `deploy6.bat` once more. |
| **“Access denied” or permission errors** | Make sure you ran `deploy6.bat` **as Administrator**. Right‑click and choose “Run as administrator”. |
| **Log location** | Full install log: `%TEMP%\BoreholeIQ-deploy.log` – check there for detailed errors. |
| **AI extraction not working** | Check that you selected **AUTO** or **AI ONLY** mode. The first model download can take a few minutes. If it still fails, try pulling the model manually by running `ollama pull <model-name>` in a command prompt. |

---

## 📦 Installing on an air‑gapped machine (no internet)  

Need to install on a PC without internet?  

1. First, run `deploy6.bat` **once** on a machine that *is* connected.  
2. After it finishes, copy the folder `C:\BoreholeIQ\offline-cache` to a USB drive.  
3. On the offline machine, paste that folder back to `C:\BoreholeIQ\offline-cache`.  
4. Run `deploy6.bat` – it will use the cached files and skip downloads.  

> **AI models** are stored in `C:\Users\<you>\.ollama`. If you want AI on the offline machine, copy that folder too.  

---

## 📄 License  

BoreholeIQ v2 is an experimental software – to help geotechnical professionals.    

---

**Built with:** Tauri, React, Rust, Tesseract OCR, Poppler, Ollama, and a lot of ☕.  
**Questions?** Open an issue or contact orvenbfajardo@gmail.com
