"""
BoreholeIQ v2 R27 - deploy/4_app.py
Scaffold source files, install deps, build frontend + backend, verify.

Reads scaffold files from ../scaffolds/ directory (plain JSON, no Base64).
"""
import json, os, subprocess, sys, time
from pathlib import Path

# Ensure imports work regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils

SCRIPT_DIR = Path(__file__).resolve().parent
SCAFFOLDS_DIR = SCRIPT_DIR.parent / "scaffolds"

def main():
    utils.init_dirs()
    utils.banner("Step 4: Build Application")
    start = time.time()
    utils.refresh_path()

    # ── 1/6 Scaffold ──
    utils.header("1/6  Scaffold Source Files")
    scaffold_json = SCAFFOLDS_DIR / "scaffold_files.json"
    if not scaffold_json.exists():
        raise RuntimeError(f"scaffold_files.json not found at {scaffold_json}")
    # Verify scaffold integrity before building
    scaffold_size = scaffold_json.stat().st_size
    utils.info(f"Scaffold file: {scaffold_size:,} bytes")
    if scaffold_size < 260000:
        utils.warn(f"Scaffold file seems too small ({scaffold_size} bytes). Expected ~270,000+. You may have an old version.")
    files = json.loads(scaffold_json.read_text(encoding="utf-8"))
    # Quick sanity checks on critical fixes
    _xlsx = files.get("SRC_TAURI/src\\pipeline\\xlsx.rs", "")
    _cargo = files.get("SRC_TAURI/Cargo.toml", "")
    _settings = files.get("SRC_TAURI/src\\commands\\settings.rs", "")
    _spatial = files.get("SRC_TAURI/src\\pipeline\\spatial.rs", "")
    issues = []
    if "quality_score" not in _xlsx: issues.append("xlsx.rs missing quality_score field")
    if '"clock"' not in _cargo: issues.append("Cargo.toml missing chrono clock feature")
    if "#[tauri::command]\npub fn get_saved_language" not in _settings: issues.append("settings.rs missing #[tauri::command] on language functions")
    if "let conf = if depth_top" not in _spatial: issues.append("spatial.rs missing E0382 borrow fix")
    if issues:
        for iss in issues:
            utils.fail(f"SCAFFOLD ERROR: {iss}")
        raise RuntimeError(f"Scaffold has {len(issues)} known issues. Download the latest scaffold_files.json (should be ~270,625 bytes).")
    else:
        utils.ok(f"Scaffold integrity verified: {len(files)} files, all critical fixes present")
    utils.info(f"Scaffolding {len(files)} files into {utils.APP_DIR}")
    utils.APP_DIR.mkdir(parents=True, exist_ok=True)
    utils.SRC_FRONT.mkdir(parents=True, exist_ok=True)
    utils.SRC_TAURI.mkdir(parents=True, exist_ok=True)
    for key, content in sorted(files.items()):
        target = _resolve_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    utils.ok(f"Scaffolded {len(files)} files")
    _generate_icons(utils.SRC_TAURI / "icons")

    # ── 2/6 npm install ──
    utils.header("2/6  npm Install")
    npm = utils.find_npm()
    lock = utils.APP_DIR / "package-lock.json"
    if lock.exists():
        utils.run([npm, "ci"], cwd=utils.APP_DIR, timeout=600)
    else:
        utils.run([npm, "install"], cwd=utils.APP_DIR, timeout=600)
    utils.ok("npm dependencies installed")

    # ── 3/6 Fonts ──
    utils.header("3/6  JetBrains Mono Font")
    fonts_dir = utils.APP_DIR / "public" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    if list(fonts_dir.glob("*.woff2")):
        utils.skip("Fonts already present")
    else:
        fv = utils.CFG["versions"]["font"]
        url = utils.CFG["urls"]["font_zip"].replace("{font}", fv)
        zip_dest = utils.WORK_DIR / f"JetBrainsMono-{fv}.zip"
        utils.download(url, zip_dest)
        extract = utils.WORK_DIR / "jbmono"
        utils.extract_zip_safe(zip_dest, extract)
        import shutil
        for woff2 in extract.rglob("*.woff2"):
            shutil.copy2(str(woff2), str(fonts_dir / woff2.name))
        utils.ok("Fonts installed")

    # ── 4/6 Frontend build ──
    utils.header("4/6  Frontend Build (TypeScript + Vite)")
    npx = utils.find_npx()
    result = utils.run([npx, "tsc", "--noEmit"], cwd=utils.APP_DIR, check=False)
    if result.returncode != 0:
        raise RuntimeError("TypeScript errors detected")
    utils.ok("TypeScript: zero errors")
    utils.run([npx, "vite", "build"], cwd=utils.APP_DIR)
    dist_index = utils.APP_DIR / "dist" / "index.html"
    if not dist_index.exists():
        raise RuntimeError("dist/index.html missing after Vite build")
    utils.ok(f"Frontend built ({dist_index.stat().st_size} bytes)")

    # ── 5/6 Backend build ──
    utils.header("5/6  Backend Build (Tauri release)")
    utils.check_disk_space(4.0)
    # Find tauri command
    tauri_cmd = None
    try:
        subprocess.check_output([npx, "tauri", "--version"], stderr=subprocess.STDOUT, timeout=15)
        tauri_cmd = [npx, "tauri"]
    except Exception:
        try:
            subprocess.check_output(["cargo", "tauri", "--version"], stderr=subprocess.STDOUT, timeout=15)
            tauri_cmd = ["cargo", "tauri"]
        except Exception:
            pass
    if tauri_cmd is None:
        raise RuntimeError("Tauri CLI not found")
    env = os.environ.copy()
    # Auto-tune build parallelism based on available RAM
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
        avail_gb = ms.ullAvailPhys / (1024**3)
        jobs = max(1, min(2, int(avail_gb / 2)))
        utils.info(f"Available RAM: {avail_gb:.1f} GB -> CARGO_BUILD_JOBS={jobs}")
    except Exception:
        jobs = 2
    env["CARGO_BUILD_JOBS"] = str(jobs)
    utils.info(f"Building with: {' '.join(tauri_cmd)} build")
    utils.run(tauri_cmd + ["build"], cwd=utils.APP_DIR, timeout=3600, env=env)
    utils.ok("Tauri release build complete")

    # ── 6/6 Verify ──
    utils.header("6/6  Verification")
    release_dir = utils.SRC_TAURI / "target" / "release"
    exes = list(release_dir.glob("*.exe")) if release_dir.exists() else []
    if exes:
        for e in exes:
            utils.ok(f"Binary: {e.name} ({e.stat().st_size // 1024} KB)")
    else:
        utils.warn("No .exe found in target/release")
    msis = list((release_dir / "bundle").rglob("*.msi")) if (release_dir / "bundle").exists() else []
    for m in msis:
        utils.ok(f"MSI: {m.name} ({m.stat().st_size // (1024*1024)} MB)")
    # Check attribution
    for js in (utils.APP_DIR / "dist" / "assets").rglob("*.js"):
        if "Orven Fajardo" in js.read_text(encoding="utf-8", errors="replace"):
            utils.ok("UI attribution footer verified in build")
            break

    utils.phase_complete("Application Build", start)

def _resolve_path(key):
    if key.startswith("APP_DIR/"): return utils.APP_DIR / key[8:].replace("\\", os.sep)
    elif key.startswith("SRC_FRONT/"): return utils.SRC_FRONT / key[10:].replace("\\", os.sep)
    elif key.startswith("SRC_TAURI/"): return utils.SRC_TAURI / key[10:].replace("\\", os.sep)
    else: return utils.APP_DIR / key.replace("\\", os.sep)

def _generate_icons(icons_dir):
    import struct, zlib
    icons_dir.mkdir(parents=True, exist_ok=True)
    if (icons_dir / "icon.png").exists(): return
    w, h = 32, 32
    raw = b''.join(b'\x00' + (b'\x1a\x3a\x5c\xff' if (x<2 or x>=30 or y<2 or y>=30)
                   else b'\x2e\x75\xb6\xff') for y in range(h) for x in range(w))
    # Fix: generate row by row properly
    rows = []
    for y in range(h):
        row = b'\x00'
        for x in range(w):
            if x < 2 or x >= 30 or y < 2 or y >= 30:
                row += b'\x1a\x3a\x5c\xff'
            else:
                row += b'\x2e\x75\xb6\xff'
        rows.append(row)
    raw = b''.join(rows)
    def chunk(ct, cd): c = ct + cd; return struct.pack('>I', len(cd)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    png = sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    (icons_dir / "icon.png").write_bytes(png)
    ico_hdr = struct.pack('<HHH', 0, 1, 1)
    ico_ent = struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(png), 22)
    (icons_dir / "icon.ico").write_bytes(ico_hdr + ico_ent + png)

if __name__ == "__main__":
    main()
