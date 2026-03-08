"""
BoreholeIQ v2 R27 - deploy/3_ollama.py
Headless Ollama sidecar: install, strip auto-start, kill tray, pull model.

COMPLETELY INDEPENDENT — any failure here does NOT block the app build.
Every operation is wrapped in try/except so the script always exits 0
unless the user explicitly needs to know something failed.
"""
import json, os, socket, subprocess, sys, time, urllib.request
from pathlib import Path

# Ensure imports work regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils


def main():
    utils.init_dirs()
    utils.banner("Step 3: Ollama AI Engine (Headless Sidecar)")
    start = time.time()

    # ── Detect hardware and pick tier ─────────────────────────────
    tier, model, pull_gb = _detect_tier()
    if tier <= 1:
        utils.info("Tier 1 machine (< 8GB RAM) — skipping Ollama (regex-only mode)")
        utils.phase_complete("Ollama (skipped)", start)
        return

    utils.info(f"Detected tier {tier}: model={model}, pull_size={pull_gb:.1f} GB")

    # ── Find or install Ollama ────────────────────────────────────
    utils.header("1/4  Ollama Installation")
    ollama_exe = _find_ollama()
    if ollama_exe is None:
        try:
            utils.info("Downloading Ollama...")
            installer = utils.WORK_DIR / "OllamaSetup.exe"
            utils.download(utils.CFG["urls"]["ollama"], installer)
            utils.run_installer(installer, ["/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"],
                                "Ollama", (0,))
            # Installer may spawn tray app — wait for it to settle
            time.sleep(3)
            ollama_exe = _find_ollama()
        except Exception as e:
            utils.warn(f"Ollama install failed: {e}")
            utils.warn("AI features disabled — app works fine with regex mode.")
            utils.phase_complete("Ollama (install failed)", start)
            return
    else:
        utils.skip("Ollama already installed")

    if ollama_exe is None:
        utils.warn("Ollama executable not found after install. AI features disabled.")
        utils.phase_complete("Ollama (not found)", start)
        return

    utils.ok(f"Ollama binary: {ollama_exe}")

    # ── Kill tray + strip auto-start ──────────────────────────────
    utils.header("2/4  Disable Auto-Start & Kill Tray")
    if _ollama_healthy():
        utils.skip("Ollama headless server already running and healthy")
    else:
        _kill_tray()
        # Extra wait after kill to avoid port/binary lock race
        time.sleep(2)
    _strip_autostart()

    # ── Start headless server ─────────────────────────────────────
    utils.header("3/4  Start Headless Server")
    if not _start_headless(str(ollama_exe)):
        utils.warn("Could not start Ollama server. Model pull skipped.")
        utils.warn("Run manually later: ollama serve & ollama pull " + (model or "phi3:mini"))
        utils.phase_complete("Ollama (server failed)", start)
        return

    # ── Pull model ────────────────────────────────────────────────
    utils.header("4/4  Pull AI Model")
    if model is None:
        utils.info("No model configured for this tier")
        utils.phase_complete("Ollama", start)
        return

    # Check disk space before pull
    try:
        _, _, free = __import__("shutil").disk_usage(str(ollama_exe.parent))
        free_gb = free / (1024**3)
        if free_gb < pull_gb + 1.0:  # Need model size + 1GB headroom
            utils.warn(f"Insufficient disk for model: {free_gb:.1f} GB free, need {pull_gb + 1:.1f} GB")
            utils.warn(f"Run manually later: ollama pull {model}")
            utils.phase_complete("Ollama (disk)", start)
            return
        utils.info(f"Disk OK: {free_gb:.1f} GB free (need {pull_gb:.1f} GB)")
    except Exception:
        pass  # Can't check — proceed anyway

    # Check if model already pulled
    if _model_exists(str(ollama_exe), model):
        utils.skip(f"Model already available: {model}")
        utils.phase_complete("Ollama", start)
        return

    _pull_model(str(ollama_exe), model)
    utils.phase_complete("Ollama", start)


def _detect_tier():
    """Detect hardware tier. Returns (tier, model, pull_size_gb).
    Uses hw_profile.json if it exists, otherwise auto-detects from RAM."""
    hw_path = utils.REPORT_DIR / "hw_profile.json"

    # Try existing profile first
    try:
        hw = json.loads(hw_path.read_text(encoding="utf-8"))
        tier = hw.get("selected_tier", 2)
        model = hw.get("model")
        pull_gb = hw.get("pull_size_gb", 2.3)
        return tier, model, pull_gb
    except Exception:
        pass

    # No profile — auto-detect from RAM
    ram_gb = _get_ram_gb()
    utils.info(f"No hw_profile.json found. Detected RAM: {ram_gb:.1f} GB")

    if ram_gb < 8:
        tier, model, pull_gb = 1, None, 0
    elif ram_gb < 12:
        tier, model, pull_gb = 2, "phi3:mini", 2.3
    elif ram_gb < 24:
        tier, model, pull_gb = 3, "phi3:medium", 7.5
    elif ram_gb < 48:
        tier, model, pull_gb = 4, "llama3.1:8b", 4.7
    else:
        tier, model, pull_gb = 5, "mistral-nemo:12b", 7.1

    # Save auto-detected profile
    profile = {"selected_tier": tier, "model": model, "pull_size_gb": pull_gb,
               "ram_gb": round(ram_gb, 1), "auto_detected": True}
    try:
        hw_path.parent.mkdir(parents=True, exist_ok=True)
        hw_path.write_text(json.dumps(profile, indent=2))
        utils.ok(f"Saved hw_profile.json (tier {tier})")
    except Exception:
        pass

    return tier, model, pull_gb


def _get_ram_gb():
    """Get total physical RAM in GB."""
    try:
        import ctypes
        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = MEMSTAT(dwLength=ctypes.sizeof(MEMSTAT))
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return ms.ullTotalPhys / (1024**3)
    except Exception:
        return 0.0  # Cannot detect RAM — force tier 1 (regex-only, safest)


def _find_ollama():
    """Find ollama.exe in known locations."""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(r"C:\Program Files\Ollama\ollama.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Ollama" / "ollama.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    try:
        out = subprocess.check_output(["where", "ollama"], stderr=subprocess.STDOUT, timeout=10)
        line = out.decode().strip().splitlines()[0].strip()
        if line and Path(line).exists():
            return Path(line)
    except Exception:
        pass
    return None


def _kill_tray():
    """Kill Ollama tray app and any running server processes."""
    for proc in ["ollama app.exe", "Ollama.exe"]:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/IM", proc],
                          capture_output=True, timeout=10)
        except Exception:
            pass
    # Wait for port release
    for _ in range(15):
        time.sleep(0.5)
        if not _port_open():
            return
    utils.warn("Port 11434 still in use after killing tray")


def _strip_autostart():
    """Remove Ollama from Windows auto-start locations."""
    try:
        import winreg
        for hive, name in [(winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")]:
            try:
                key = winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Run",
                                     0, winreg.KEY_ALL_ACCESS)
                try:
                    winreg.DeleteValue(key, "Ollama")
                    utils.info(f"Removed auto-start from {name}")
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
            except Exception:
                pass
    except ImportError:
        pass
    try:
        startup = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        for n in ["Ollama.lnk", "ollama.lnk"]:
            s = startup / n
            if s.exists():
                s.unlink()
                utils.info(f"Removed shortcut: {n}")
    except Exception:
        pass


def _start_headless(exe_path):
    """Start Ollama in headless mode. Returns True if server is responding."""
    if _ollama_healthy():
        utils.ok("Ollama already running and healthy on :11434")
        return True
    if _port_open():
        # Something on the port but not healthy — kill and restart
        utils.info("Port 11434 in use but not healthy, restarting...")
        _kill_tray()
        time.sleep(2)
    try:
        subprocess.Popen([exe_path, "serve"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=0x08000000)
        for i in range(30):  # 15 seconds max
            time.sleep(0.5)
            if _ollama_healthy():
                utils.ok(f"Ollama server ready (took {(i+1)*500}ms)")
                return True
        # Fallback: check port even if /api/tags doesn't respond
        if _port_open():
            utils.warn("Ollama port open but /api/tags not responding — proceeding anyway")
            return True
        utils.warn("Ollama started but not responding after 15s")
        return False
    except Exception as e:
        utils.warn(f"Could not start server: {e}")
        return False


def _model_exists(exe_path, model):
    """Check if a model is already pulled."""
    try:
        result = subprocess.run([exe_path, "list"], capture_output=True, text=True,
                               timeout=15, creationflags=0x08000000)
        if result.returncode == 0 and model.split(":")[0] in result.stdout:
            return True
    except Exception:
        pass
    return False


def _pull_model(exe_path, model):
    """Pull a model WITHOUT buffering stdout (prevents memory exhaustion).
    Uses Popen + line-by-line reading instead of subprocess.run."""
    import re as _re
    _ansi_re = _re.compile(r'\x1b\[[0-9;]*[A-Za-z]|\x1b\[\?[0-9;]*[A-Za-z]')

    utils.info(f"Pulling {model} (this may take several minutes)...")
    try:
        proc = subprocess.Popen(
            [exe_path, "pull", model],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=0x08000000
        )
        last_log = time.time()
        while True:
            raw = proc.stdout.readline()
            if not raw and proc.poll() is not None:
                break
            # Decode with replacement to handle any encoding, strip ANSI escapes
            line = raw.decode("utf-8", errors="replace").strip()
            line = _ansi_re.sub("", line)
            # Replace Unicode block chars that crash cp1252 logging
            line = line.encode("ascii", errors="replace").decode("ascii")
            if line:
                now = time.time()
                if now - last_log > 30 or "success" in line.lower():
                    utils.info(f"  pull: {line[:120]}")
                    last_log = now

        rc = proc.wait(timeout=30)
        if rc == 0:
            utils.ok(f"Model ready: {model}")
        else:
            utils.warn(f"Pull exited with code {rc}")
            utils.warn(f"Run manually later: ollama pull {model}")
    except subprocess.TimeoutExpired:
        proc.kill()
        utils.warn(f"Pull timed out. Run manually: ollama pull {model}")
    except Exception as e:
        utils.warn(f"Pull failed: {e}")
        utils.warn(f"Run manually later: ollama pull {model}")


def _port_open():
    try:
        s = socket.create_connection(("127.0.0.1", 11434), timeout=1)
        s.close()
        return True
    except (socket.error, OSError):
        return False


def _ollama_healthy():
    """Check if Ollama is running AND responding correctly."""
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # True fail-forward: NEVER let an unhandled exception crash the deploy
        utils.warn(f"Ollama setup failed with unexpected error: {e}")
        utils.warn("AI features disabled — app works fine with regex extraction.")
        utils.warn("Re-run 3-ollama.bat independently to retry.")
        sys.exit(0)  # Exit 0 so deploy.bat doesn't think the whole deploy failed
