"""
BoreholeIQ v2 R27 - deploy/utils.py
Shared Utilities for all deploy scripts.

Download with retry + SSL fallback, state tracking, logging, subprocess, PATH.
"""
import hashlib, json, logging, os, shutil, subprocess, sys, time, urllib.request, zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Load config ──────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _SCRIPT_DIR / "config.json"
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    CFG = json.load(_f)

APP_DIR = Path(os.environ.get("BOREHOLEIQ_ROOT", CFG["app_dir"]))
SRC_TAURI = APP_DIR / "src-tauri"
SRC_FRONT = APP_DIR / "src"
WORK_DIR = Path(os.environ.get("TEMP", r"C:\Temp")) / "BoreholeIQ-Install"
CACHE_DIR = APP_DIR / "offline-cache"
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "BoreholeIQ" / "state"
REPORT_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "BoreholeIQ"
INSTALL_LOG = Path(os.environ.get("TEMP", r"C:\Temp")) / "BoreholeIQ-Install.log"
TESS_INST = Path(CFG["paths"]["tesseract"])
POPPL_INST = Path(CFG["paths"]["poppler"])

# ── Logging with rotation ────────────────────────────────────────
_LOG_FMT = "%(asctime)s [%(levelname)-5s] %(message)s"

def _safe_stream():
    """Return a stdout stream that won't crash on Unicode.
    Windows cp1252 can't encode Ollama's progress bar chars (█░)."""
    import io
    try:
        return io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        return sys.stdout

def setup_logging(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(_safe_stream())
    ch.setFormatter(logging.Formatter(_LOG_FMT, "%H:%M:%S"))
    logger.addHandler(ch)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    _rotate_logs(INSTALL_LOG, keep=3)
    fh = logging.FileHandler(str(INSTALL_LOG), encoding="utf-8", errors="replace")
    fh.setFormatter(logging.Formatter(_LOG_FMT, "%H:%M:%S"))
    logger.addHandler(fh)
    return logger

def _rotate_logs(log_path: Path, keep=3):
    """Rotate log files: .log -> .log.1 -> .log.2 -> .log.3 (delete oldest)."""
    try:
        for i in range(keep, 0, -1):
            old = Path(f"{log_path}.{i}")
            older = Path(f"{log_path}.{i+1}")
            if i == keep and old.exists():
                old.unlink()
            elif old.exists():
                old.rename(older)
        if log_path.exists() and log_path.stat().st_size > 0:
            log_path.rename(Path(f"{log_path}.1"))
    except Exception:
        pass

log = setup_logging("boreholeiq")

def banner(text): print(f"\n{'=' * 64}\n  {text}\n  Started: {datetime.now():%Y-%m-%d %H:%M:%S}\n{'=' * 64}")
def header(text): print(f"\n{'-' * 64}\n  [{datetime.now():%H:%M:%S}] {text}\n{'-' * 64}")
def ok(msg): log.info(f"[OK]   {msg}")
def fail(msg): log.error(f"[FAIL] {msg}")
def warn(msg): log.warning(f"[WARN] {msg}")
def info(msg): log.info(f"[...] {msg}")
def skip(msg): log.info(f"[SKIP] {msg}")

# ── Disk check ───────────────────────────────────────────────────
def check_disk_space(required_gb, path=None):
    """Check disk space on the drive containing `path` (default: APP_DIR)."""
    target = str(path or APP_DIR)
    try:
        _, _, free = shutil.disk_usage(target)
        free_gb = free / (1024**3)
        if free_gb < required_gb:
            raise RuntimeError(f"Insufficient disk: {free_gb:.1f} GB free, need {required_gb:.1f} GB on {target}")
    except OSError:
        warn(f"Could not check disk space on {target}")

# ── SSL context for downloads ────────────────────────────────────
_ssl_fallback_ctx = None  # Cached after first successful creation

def _get_ssl_context():
    """Create an SSL context that works on corporate/VM Windows machines.
    Returns an unverified context when the Windows cert store is missing certs."""
    global _ssl_fallback_ctx
    if _ssl_fallback_ctx is not None:
        return _ssl_fallback_ctx
    import ssl
    # Attempt 1: standard verified context
    try:
        ctx = ssl.create_default_context()
        # Quick test — if this context can't verify anything, we'll find out
        # during the actual download and fall through to attempt 2
        _ssl_fallback_ctx = ctx
        return ctx
    except Exception:
        pass
    # Attempt 2: build context and load system certs explicitly
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.set_default_verify_paths()
        _ssl_fallback_ctx = ctx
        return ctx
    except Exception:
        pass
    # Attempt 3: unverified (the only thing that works on fresh VMs)
    warn("SSL certificates unavailable - using unverified HTTPS (VM/corporate environment)")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    _ssl_fallback_ctx = ctx
    return ctx

# ── Download with SSL fallback ───────────────────────────────────
def download(url, dest: Path, max_retries=3) -> Path:
    name = dest.name
    cached = CACHE_DIR / name
    if cached.exists():
        info(f"Cache hit: {name}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(cached), str(dest))
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)

    ssl_failed_once = False
    for attempt in range(1, max_retries + 1):
        try:
            info(f"Download {attempt}/{max_retries}: {name}")
            if ssl_failed_once:
                # Skip urllib.request.urlretrieve — go straight to fallback
                _download_with_fallback_ssl(url, dest)
            else:
                try:
                    urllib.request.urlretrieve(url, str(dest))
                except Exception as e:
                    if "CERTIFICATE_VERIFY_FAILED" in str(e) or "SSL" in str(e):
                        ssl_failed_once = True
                        info("SSL cert issue detected, switching to fallback for all remaining attempts...")
                        # Force unverified context for this and all future downloads
                        import ssl as _ssl
                        _ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
                        _ctx.check_hostname = False
                        _ctx.verify_mode = _ssl.CERT_NONE
                        global _ssl_fallback_ctx
                        _ssl_fallback_ctx = _ctx
                        _download_with_fallback_ssl(url, dest)
                    else:
                        raise
            if not dest.exists() or dest.stat().st_size < 1024:
                raise RuntimeError("Downloaded file too small or missing")
            ok(f"Downloaded: {name}")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(dest), str(cached))
            return dest
        except Exception as e:
            fail(f"Attempt {attempt} failed: {e}")
            dest.unlink(missing_ok=True)
            if attempt < max_retries:
                wait = min(2 ** attempt, 30)
                info(f"Retrying in {wait}s...")
                time.sleep(wait)
    raise RuntimeError(f"FATAL: Failed to download {name} after {max_retries} attempts")


def _download_with_fallback_ssl(url, dest: Path):
    """Download using the cached SSL fallback context."""
    ctx = _get_ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": "BoreholeIQ/2.0"})
    with urllib.request.urlopen(req, context=ctx) as resp, open(str(dest), "wb") as fout:
        shutil.copyfileobj(resp, fout)

# ── Subprocess ───────────────────────────────────────────────────
def run(cmd, cwd=None, check=True, env=None, timeout=1800):
    info(f"Running: {' '.join(str(c) for c in cmd)}")
    merged = {**os.environ, **(env or {})}
    result = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                           env=merged, capture_output=True, timeout=timeout, check=False,
                           text=True, errors="replace")
    # Stream output
    if result.stdout:
        for line in result.stdout.strip().splitlines()[-20:]:
            log.debug(line)
    if check and result.returncode != 0:
        stderr_lines = (result.stderr or "").strip().splitlines()
        # Show last 60 lines of stderr to capture ALL Rust compiler errors
        stderr_tail = stderr_lines[-60:] if len(stderr_lines) > 60 else stderr_lines
        for line in stderr_tail:
            log.error(f"  | {line}")
        stderr_msg = "\n".join(stderr_tail) if stderr_tail else "(no stderr)"
        raise RuntimeError(
            f"Command failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"  stderr: {stderr_msg}"
        )
    return result

def run_installer(exe, args, name, acceptable_codes=(0,)):
    info(f"Installing: {name}...")
    result = subprocess.run([str(exe)] + [str(a) for a in args],
                           capture_output=True, timeout=3600, check=False)
    # Always accept: 0=success, 3010=reboot needed, 1638=already installed, 1641=reboot initiated
    all_ok = set(acceptable_codes) | {0, 3010, 1638, 1641}
    if result.returncode not in all_ok:
        stderr = result.stderr.decode(errors="replace")[-500:] if result.stderr else ""
        raise RuntimeError(f"Installer failed: {name} (exit {result.returncode})\n  {stderr}")
    if result.returncode == 3010 or result.returncode == 1641:
        warn(f"{name}: REBOOT REQUIRED (exit {result.returncode})")
    elif result.returncode == 1638:
        skip(f"{name} already installed (exit 1638)")
    else:
        ok(f"{name} installed (exit {result.returncode})")

# ── Post-install verification ────────────────────────────────────
def verify_exe(exe_path, version_args=None, name=None):
    """Verify an executable exists and optionally runs a version check."""
    p = Path(exe_path)
    label = name or p.name
    if not p.exists():
        raise RuntimeError(f"Verification FAILED: {label} not found at {p}")
    if version_args:
        try:
            out = subprocess.check_output(
                [str(p)] + version_args, stderr=subprocess.STDOUT, timeout=15
            ).decode(errors="replace").strip()
            ok(f"Verified {label}: {out[:80]}")
            return out
        except Exception as e:
            warn(f"Verification: {label} exists but version check failed: {e}")
    else:
        ok(f"Verified {label} exists at {p}")
    return None

# ── State tracking with verification ─────────────────────────────
def set_step_complete(step_name):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / f"{step_name}.done").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))

def is_step_complete(step_name):
    return (STATE_DIR / f"{step_name}.done").exists()

# ── ZIP extraction ───────────────────────────────────────────────
def extract_zip_safe(zip_path, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(zip_path), "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"Corrupted zip member: {bad}")
        # Path traversal protection
        for member in zf.namelist():
            target = (dest / member).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise RuntimeError(f"Zip path traversal detected: {member}")
        zf.extractall(str(dest))
    ok(f"Extracted: {zip_path.name}")

# ── PATH management ──────────────────────────────────────────────
def add_to_path(directory):
    if directory not in os.environ.get("PATH", ""):
        os.environ["PATH"] = directory + ";" + os.environ.get("PATH", "")
        info(f"PATH += {directory} (session)")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command",
            f"[Environment]::SetEnvironmentVariable('Path', "
            f"[Environment]::GetEnvironmentVariable('Path','Machine') + ';{directory}', 'Machine')"],
            capture_output=True, timeout=15)
        # Broadcast WM_SETTINGCHANGE so Explorer picks up the new PATH
        _broadcast_env_change()
    except Exception as e:
        warn(f"Could not persist PATH: {e}")

def _broadcast_env_change():
    """Broadcast WM_SETTINGCHANGE to notify other processes of env changes."""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command",
            "Add-Type -Namespace Win32 -Name NativeMethods -MemberDefinition '"
            "[DllImport(\"user32.dll\", SetLastError = true, CharSet = CharSet.Auto)]"
            "public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, "
            "UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);';"
            "$result = [UIntPtr]::Zero;"
            "[Win32.NativeMethods]::SendMessageTimeout([IntPtr]0xffff, 0x1A, "
            "[UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$result)"
            ], capture_output=True, timeout=15)
    except Exception:
        pass

def refresh_path():
    try:
        import winreg
        m = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
        mp = winreg.QueryValueEx(m, "Path")[0]; winreg.CloseKey(m)
        u = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        up = winreg.QueryValueEx(u, "Path")[0]; winreg.CloseKey(u)
        os.environ["PATH"] = mp + ";" + up
    except Exception:
        pass
    for p in [r"C:\Program Files\nodejs", str(Path.home() / ".cargo" / "bin"),
              str(TESS_INST), str(POPPL_INST / "bin")]:
        if p and Path(p).exists() and p not in os.environ.get("PATH", ""):
            os.environ["PATH"] = p + ";" + os.environ["PATH"]
    # Verify critical tools are findable after refresh
    for tool in ["node", "cargo", "npm"]:
        found = shutil.which(tool)
        if found:
            log.debug(f"PATH check: {tool} -> {found}")

# ── npm/npx discovery ────────────────────────────────────────────
def find_npm():
    found = shutil.which("npm")
    if found: return found
    for c in [r"C:\Program Files\nodejs\npm.cmd"]:
        if Path(c).exists(): return c
    raise RuntimeError("npm not found")

def find_npx():
    found = shutil.which("npx")
    if found: return found
    npm = find_npm()
    npx = str(Path(npm).parent / "npx.cmd")
    if Path(npx).exists(): return npx
    raise RuntimeError("npx not found")

# ── Init dirs ────────────────────────────────────────────────────
def init_dirs():
    for d in [WORK_DIR, CACHE_DIR, REPORT_DIR, STATE_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def phase_complete(name, start):
    elapsed = time.time() - start
    if elapsed < 60: ok(f"{name} complete ({elapsed:.1f}s)")
    else: ok(f"{name} complete ({int(elapsed//60)}m {int(elapsed%60)}s)")
