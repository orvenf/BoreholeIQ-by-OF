"""
BoreholeIQ v2 R27 - deploy/1_prereqs.py
Install build-time prerequisites: MSVC, Node.js, Rust, WebView2, Tauri CLI.
"""
import os, shutil, subprocess, sys, time
from pathlib import Path

# Ensure imports work regardless of CWD (batch files run from project root)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils


def _node_version():
    """Return installed Node major version, or None."""
    for cmd in ["node", r"C:\Program Files\nodejs\node.exe"]:
        try:
            out = subprocess.check_output([cmd, "--version"],
                                          timeout=10, stderr=subprocess.DEVNULL).decode().strip().lstrip("v")
            return int(out.split(".")[0]), out
        except Exception:
            continue
    return None, None


def _rust_present():
    """Return True if rustup + cargo are both reachable."""
    return shutil.which("rustup") is not None and shutil.which("cargo") is not None


def main():
    utils.init_dirs()
    utils.banner("Step 1: Prerequisites (MSVC, Node, Rust, WebView2)")
    start = time.time()

    # ── 1/6 VC++ Redistributable ──
    utils.header("1/6  VC++ Redistributable")
    dest = utils.WORK_DIR / "vc_redist.x64.exe"
    utils.download(utils.CFG["urls"]["vc_redist"], dest)
    utils.run_installer(dest, ["/install", "/quiet", "/norestart"], "VC++ Redist", (0, 3010))

    # ── 2/6 MSVC Build Tools ──
    utils.header("2/6  MSVC Build Tools")
    bt = Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft Visual Studio" / "2022" / "BuildTools"
    if bt.exists():
        utils.skip("MSVC Build Tools already installed")
    else:
        utils.check_disk_space(6.0)
        dest = utils.WORK_DIR / "vs_buildtools.exe"
        utils.download(utils.CFG["urls"]["vs_buildtools"], dest)
        utils.run_installer(dest, ["--quiet", "--wait", "--norestart",
            "--add", "Microsoft.VisualStudio.Workload.VCTools",
            "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "--add", "Microsoft.VisualStudio.Component.Windows11SDK.22621",
            "--includeRecommended"], "MSVC Build Tools", (0, 3010))

    # ── 3/6 Node.js ──
    utils.header("3/6  Node.js")
    nv = utils.CFG["versions"]["node"]
    min_major = utils.CFG["versions"]["min_node_major"]
    node_major, node_full = _node_version()
    if node_major is not None and node_major >= min_major:
        utils.skip(f"Node.js v{node_full}")
    else:
        if node_major is not None:
            utils.info(f"Node.js v{node_full} too old (need >= {min_major}), upgrading...")
        url = utils.CFG["urls"]["node_msi"].replace("{node}", nv)
        dest = utils.WORK_DIR / f"node-v{nv}-x64.msi"
        utils.download(url, dest)
        utils.run_installer(Path("msiexec.exe"), ["/i", str(dest), "/quiet", "/norestart", "ADDLOCAL=ALL"],
                           f"Node.js v{nv}", (0,))
        utils.refresh_path()
        # Verify node is now reachable
        node_cmd = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
        utils.verify_exe(node_cmd, ["--version"], "Node.js")

    # ── 4/6 Rust ──
    utils.header("4/6  Rust Toolchain")
    if _rust_present():
        utils.skip("Rust toolchain present")
        try:
            rc = subprocess.check_output(["rustc", "--version"], timeout=10).decode()
            parts = rc.split()[1].split(".")
            if len(parts) >= 2 and int(parts[1]) < utils.CFG["versions"]["min_rust_minor"]:
                utils.info("Updating Rust...")
                utils.run(["rustup", "update", "stable"], check=False, timeout=600)
        except Exception:
            pass
    else:
        dest = utils.WORK_DIR / "rustup-init.exe"
        utils.download(utils.CFG["urls"]["rustup"], dest)
        utils.run_installer(dest, ["-y", "--default-toolchain", "stable",
            "--default-host", "x86_64-pc-windows-msvc"], "Rust", (0,))
        utils.add_to_path(str(Path.home() / ".cargo" / "bin"))
        utils.refresh_path()
        # Verify cargo is reachable
        cargo_cmd = shutil.which("cargo") or str(Path.home() / ".cargo" / "bin" / "cargo.exe")
        utils.verify_exe(cargo_cmd, ["--version"], "Cargo")

    # ── 5/6 WebView2 ──
    utils.header("5/6  WebView2 Runtime")
    webview2_found = False
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for kp in [r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                       r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"]:
                try:
                    k = winreg.OpenKey(hive, kp)
                    v = winreg.QueryValueEx(k, "pv")[0]; winreg.CloseKey(k)
                    if v:
                        utils.skip(f"WebView2 v{v}")
                        webview2_found = True
                        break
                except OSError:
                    continue
            if webview2_found:
                break
    except ImportError:
        pass
    if not webview2_found:
        dest = utils.WORK_DIR / "WebView2Setup.exe"
        utils.download(utils.CFG["urls"]["webview2"], dest)
        utils.run_installer(dest, ["/silent", "/install"], "WebView2", (0,))

    # ── 6/6 Tauri CLI ──
    utils.header("6/6  Tauri CLI")
    utils.refresh_path()
    tauri_ok = False
    try:
        subprocess.check_output([utils.find_npx(), "tauri", "--version"],
                                stderr=subprocess.STDOUT, timeout=15)
        utils.skip("Tauri CLI available via npx")
        tauri_ok = True
    except Exception:
        pass
    if not tauri_ok:
        try:
            utils.info("Installing @tauri-apps/cli via npm...")
            utils.run([utils.find_npm(), "install", "-g", "@tauri-apps/cli"], timeout=300)
            utils.ok("Tauri CLI installed")
        except Exception:
            utils.warn("npm install failed, trying cargo install...")
            tauri_ver = utils.CFG.get("versions", {}).get("tauri_cli", "2.1.0")
            utils.run(["cargo", "install", "tauri-cli", "--version", f"={tauri_ver}", "--locked"], timeout=3600)

    utils.phase_complete("Prerequisites", start)
    utils.ok("All prerequisites installed successfully")


if __name__ == "__main__":
    main()
