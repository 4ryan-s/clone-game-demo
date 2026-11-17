#!/usr/bin/env python3
"""Set this demo up on a new laptop. Python 3.11+ is enough to start; the models are downloaded, not stored in git.

    python setup.py                  everything (API, Qwen3-TTS, CosyVoice 2, clone-check model, React quiz build)
    python setup.py --only api,qwen  just some parts: api, qwen, cosyvoice, spectra, frontend
    python setup.py --cpu            no NVIDIA GPU (a Mac, for example): CPU/Apple builds of PyTorch, much slower
    python setup.py --check          show what is installed and what is missing, change nothing
    python setup.py --dry-run        print the commands instead of running them

Needs about 20 GB of disk and an internet connection for the downloads.
The clone-check model (Spectra-AASIST3, 1.2 GB, Apache-2.0) is downloaded from Hugging Face (lab260/Spectra-AASIST3)
and checked against its published SHA-256. To use a copy you already have, pass `--spectra-from <file>` or set SPECTRA_URL.
Sarvam needs the SARVAM_API_KEY environment variable; this script never asks for or stores it.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402  (paths and model names live there; local_config.py may override them)

COSYVOICE_COMMIT = "074ca6d"
COSYVOICE_REPO_URL = "https://github.com/FunAudioLLM/CosyVoice.git"
COSYVOICE_HF_ID = "FunAudioLLM/CosyVoice2-0.5B"
SPECTRA_URL = "https://huggingface.co/lab260/Spectra-AASIST3/resolve/main/spectra-aasist3.onnx"   # Apache-2.0, public
SPECTRA_SHA256 = "5f05c29a01ad80c702b32654db87c2aa6e467c11c67b6d47f2fac873f846cae9"
ARGS = None


def say(msg):
    print(f"\n== {msg}", flush=True)


def run(cmd, **kw):
    cmd = [str(c) for c in cmd]
    print("   $ " + " ".join(cmd), flush=True)
    if not ARGS.dry_run:
        subprocess.run(cmd, check=True, **kw)


def venv_python(name):
    return Path(config.venv_python(name))


def find_python(version):
    """A Python interpreter of the given major.minor, as a command list, or None."""
    candidates = [["py", f"-{version}"], [f"python{version}"], ["python"]] if os.name == "nt" else [[f"python{version}"], ["python3"], ["python"]]
    for c in candidates:
        try:
            out = subprocess.run(c + ["-c", "import sys;print('%d.%d' % sys.version_info[:2])"], capture_output=True, text=True, timeout=20)
            if out.returncode == 0 and out.stdout.strip() == version:
                return c
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def make_venv(path, version=None):
    if (path / ("Scripts" if os.name == "nt" else "bin")).exists():
        print(f"   environment exists: {path}")
        return
    py = find_python(version) if version else [sys.executable]
    if not py:
        sys.exit(f"Python {version} is needed for this engine and was not found. Install it (python.org, or `pyenv install {version}`) and run again.")
    run(py + ["-m", "venv", path])


def pip(py, *args):
    run([py, "-m", "pip", "install", "--disable-pip-version-check", *args])


def torch_install(py, version, tv, cuda_tag):
    """PyTorch from the CUDA wheel index when there is an NVIDIA GPU, the default (CPU or Apple) build otherwise."""
    pkgs = [f"torch=={version}", f"torchaudio=={tv}"]
    if ARGS.cpu or platform.system() == "Darwin":
        pip(py, *pkgs)
    else:
        pip(py, *pkgs, "--index-url", f"https://download.pytorch.org/whl/{cuda_tag}")


def hf_download(py, repo_id, local_dir=None):
    code = f"from huggingface_hub import snapshot_download; snapshot_download({repo_id!r}" + (f", local_dir={str(local_dir)!r}" if local_dir else "") + ")"
    env = {**os.environ, "HF_HOME": str(config.HF_HOME)}
    run([py, "-c", code], env=env)


# ---------------------------------------------------------------- parts
def part_api():
    say("Demo server environment (.venv)")
    make_venv(ROOT / ".venv")
    pip(ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"), "-r", ROOT / "requirements.txt")


def part_qwen():
    say("Qwen3-TTS: environment and weights")
    py = venv_python("qwen")
    make_venv(ROOT / ".venvs" / "qwen")
    torch_install(py, "2.11.0", "2.11.0", "cu128")
    pip(py, "-r", ROOT / "requirements" / "qwen.txt")
    hf_download(py, config.QWEN_MODEL)


def part_cosyvoice():
    say("CosyVoice 2: environment, code and weights")
    py = venv_python("cosyvoice")
    make_venv(ROOT / ".venvs" / "cosyvoice")
    torch_install(py, "2.11.0", "2.11.0", "cu128")
    pip(py, "-r", ROOT / "requirements" / "cosyvoice.txt")
    repo = config.COSYVOICE_REPO
    if not repo.exists():
        run(["git", "clone", "--recursive", COSYVOICE_REPO_URL, repo])
        run(["git", "-C", repo, "checkout", COSYVOICE_COMMIT])
        run(["git", "-C", repo, "submodule", "update", "--init", "--recursive"])
    hf_download(py, COSYVOICE_HF_ID, config.COSYVOICE_MODEL_DIR)


def sha256_of(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def part_spectra(spectra_from=None):
    say("Clone-check model (Spectra-AASIST3)")
    dest = Path(config.SPECTRA_ONNX)
    if dest.is_file():
        print(f"   present: {dest} ({dest.stat().st_size / 1e6:.0f} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = os.environ.get("SPECTRA_URL", SPECTRA_URL)
    part = dest.with_suffix(".onnx.part")
    if spectra_from:
        print(f"   copying {spectra_from}")
        if not ARGS.dry_run:
            shutil.copyfile(spectra_from, part)
    else:
        print(f"   downloading {url}")
        if not ARGS.dry_run:
            req = urllib.request.Request(url)
            if os.environ.get("SPECTRA_TOKEN"):
                req.add_header("Authorization", "Bearer " + os.environ["SPECTRA_TOKEN"])
            with urllib.request.urlopen(req) as r, open(part, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
    if ARGS.dry_run:
        return
    if url == SPECTRA_URL or spectra_from:       # the published file: check it is the exact one we tested
        if sha256_of(part) != SPECTRA_SHA256:
            part.unlink()
            sys.exit("The clone-check model did not match its published checksum, so it was not installed. Try again, or check the file.")
    part.replace(dest)
    print(f"   installed {dest} ({dest.stat().st_size / 1e6:.0f} MB, checksum ok)")


def part_frontend():
    say("React quiz (frontend/)")
    npm = shutil.which("npm")
    if not npm:
        print("   npm not found. Install Node.js 20 or later and run this again. Until then the server falls back to the plain page.")
        return
    run([npm, "install", "--no-audit", "--no-fund"], cwd=ROOT / "frontend")
    run([npm, "run", "build"], cwd=ROOT / "frontend")       # the server serves frontend/dist at http://localhost:8000


def check():
    def mark(ok, what, hint=""):
        print(f"  [{'ok' if ok else '--'}] {what}" + ("" if ok else f"   <- {hint}"))
    say("Status")
    mark((ROOT / ".venv").exists() or sys.prefix != sys.base_prefix, "demo server environment", "python setup.py --only api")
    mark(venv_python("qwen").exists() or Path(config.QWEN_PYTHON).exists(), "Qwen3-TTS environment", "python setup.py --only qwen")
    hub = Path(config.HF_HOME) / "hub" / ("models--" + config.QWEN_MODEL.replace("/", "--"))
    mark(hub.exists(), "Qwen3-TTS weights", "python setup.py --only qwen")
    mark(Path(config.COSYVOICE_PYTHON).exists(), "CosyVoice environment", "python setup.py --only cosyvoice")
    mark(Path(config.COSYVOICE_REPO).exists() and Path(config.COSYVOICE_MODEL_DIR).exists(), "CosyVoice code and weights", "python setup.py --only cosyvoice")
    mark(Path(config.SPECTRA_ONNX).is_file(), "clone-check model", "see python setup.py --help")
    mark(bool(os.environ.get("SARVAM_API_KEY")), "Sarvam key in the environment (Windows: also checked in user variables at run time)", "set SARVAM_API_KEY")
    mark((ROOT / "frontend" / "dist" / "index.html").exists(), "React quiz build (the demo page)", "python setup.py --only frontend (needs Node.js 20+)")


def main():
    global ARGS
    if sys.version_info < (3, 11):
        sys.exit(f"Python 3.11 or later is needed to run setup (this is {platform.python_version()}). On a Mac: `brew install python@3.12`, then `python3.12 setup.py`.")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="api,qwen,cosyvoice,spectra,frontend")
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--spectra-from")
    ARGS = ap.parse_args()
    if ARGS.check:
        return check()
    parts = {"api": part_api, "qwen": part_qwen, "cosyvoice": part_cosyvoice, "frontend": part_frontend,
             "spectra": lambda: part_spectra(ARGS.spectra_from)}
    for name in ARGS.only.split(","):
        if name not in parts:
            sys.exit(f"unknown part {name!r}; choose from {', '.join(parts)}")
        parts[name]()
    check()
    print("\nNext: set SARVAM_API_KEY, then start the demo with start_demo.ps1 (Windows) or start_demo.sh (Mac/Linux).")


if __name__ == "__main__":
    main()
