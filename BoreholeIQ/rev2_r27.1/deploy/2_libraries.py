"""
BoreholeIQ v2 R27 - deploy/2_libraries.py
Install runtime libraries: Tesseract OCR + 25 language packs, Poppler PDF tools.
"""
import shutil, sys, time
from pathlib import Path

# Ensure imports work regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils

def main():
    utils.init_dirs()
    utils.banner("Step 2: Libraries (Tesseract, Poppler)")
    start = time.time()

    # ── 1/3 Tesseract OCR ──
    utils.header("1/3  Tesseract OCR")
    tess_exe = utils.TESS_INST / "tesseract.exe"
    tv = utils.CFG["versions"]["tesseract"]
    if tess_exe.exists():
        utils.skip("Tesseract already installed")
    else:
        url = utils.CFG["urls"]["tesseract"].replace("{tesseract}", tv)
        dest = utils.WORK_DIR / f"tesseract-ocr-w64-setup-{tv}.exe"
        utils.download(url, dest)
        utils.run_installer(dest, ["/S", f"/D={utils.TESS_INST}"], "Tesseract OCR", (0,))
        # Verify tesseract actually works
        utils.verify_exe(utils.TESS_INST / "tesseract.exe", ["--version"], "Tesseract OCR")
    utils.add_to_path(str(utils.TESS_INST))

    # ── 2/3 Language packs ──
    utils.header("2/3  Tesseract Language Packs")
    tessdata = utils.TESS_INST / "tessdata"
    tessdata.mkdir(parents=True, exist_ok=True)
    langs = utils.CFG["tesseract_languages"]
    failures = []
    for lang in langs:
        lf = tessdata / f"{lang}.traineddata"
        if lf.exists():
            utils.skip(f"{lang}.traineddata")
            continue
        url = f"{utils.CFG['urls']['tessdata_base']}/{lang}.traineddata"
        try:
            utils.download(url, lf, max_retries=3)
        except Exception as e:
            failures.append(lang)
            utils.warn(f"Failed: {lang} - {e}")
    if failures:
        utils.warn(f"{len(failures)} packs failed: {', '.join(failures)}. Re-run to retry.")
    else:
        utils.ok(f"All {len(langs)} language packs installed")

    # ── 3/3 Poppler ──
    utils.header("3/3  Poppler PDF Tools")
    ppm = utils.POPPL_INST / "bin" / "pdftoppm.exe"
    if ppm.exists():
        utils.skip("Poppler already installed")
    else:
        pv = utils.CFG["versions"]["poppler"]
        url = utils.CFG["urls"]["poppler"].replace("{poppler}", pv)
        zip_dest = utils.WORK_DIR / f"Release-{pv}.zip"
        utils.download(url, zip_dest)
        extract = utils.WORK_DIR / "poppler-extract"
        utils.extract_zip_safe(zip_dest, extract)
        utils.POPPL_INST.mkdir(parents=True, exist_ok=True)
        (utils.POPPL_INST / "bin").mkdir(parents=True, exist_ok=True)
        # Recursively find pdftoppm.exe — handles upstream ZIP layout changes
        found_bin = None
        for item in extract.rglob("pdftoppm.exe"):
            found_bin = item.parent
            break
        if found_bin is None:
            raise RuntimeError("pdftoppm.exe not found in Poppler archive")
        shutil.copytree(str(found_bin.parent), str(utils.POPPL_INST), dirs_exist_ok=True)
        # Verify Poppler works
        utils.verify_exe(utils.POPPL_INST / "bin" / "pdftoppm.exe", name="Poppler pdftoppm")
        utils.ok("Poppler installed")
    utils.add_to_path(str(utils.POPPL_INST / "bin"))

    # ── Write manifest ──
    import json
    manifest = {
        "tesseract": str(utils.TESS_INST),
        "poppler": str(utils.POPPL_INST),
        "languages": [l for l in langs if (tessdata / f"{l}.traineddata").exists()],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (utils.REPORT_DIR / "libraries-manifest.json").write_text(json.dumps(manifest, indent=2))

    utils.phase_complete("Libraries", start)

if __name__ == "__main__":
    main()
