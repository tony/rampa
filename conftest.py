"""Root pytest configuration for ``rampa``."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import time

_PROJECT_ROOT = pathlib.Path(__file__).parent
_PACKAGE_DIR = _PROJECT_ROOT / "src" / "rampa"


def _tty() -> int | None:
    try:
        return os.open("/dev/tty", os.O_WRONLY)
    except OSError:
        return None


def _tty_write(msg: str, fd: int | None = None) -> None:
    if fd is not None:
        os.write(fd, msg.encode())
    else:
        sys.stderr.write(msg)
        sys.stderr.flush()


def _ensure_native_extension() -> None:
    if any(_PACKAGE_DIR.glob("_core*.so")):
        return
    manifest = _PROJECT_ROOT / "rust" / "Cargo.toml"
    if not manifest.exists():
        return
    if not shutil.which("cargo"):
        sys.stderr.write("⚠ cargo not found — skipping Rust build (Python fallback)\n")
        return
    tty_fd = _tty()
    t0 = time.monotonic()
    _tty_write("\033[1m→ building rampa._core (maturin develop)\033[0m\n", tty_fd)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "maturin", "develop", "--manifest-path", str(manifest), "--uv"],
            cwd=str(_PROJECT_ROOT),
            stdout=tty_fd,
            stderr=tty_fd,
            env={
                **os.environ,
                "CARGO_TERM_PROGRESS_WHEN": "always",
                "CARGO_TERM_PROGRESS_WIDTH": "80",
                "CARGO_TERM_COLOR": "always",
            },
        )
    except subprocess.CalledProcessError:
        _tty_write("\033[33m⚠ Rust build failed — using Python fallback\033[0m\n", tty_fd)
    except FileNotFoundError:
        _tty_write("\033[33m⚠ maturin not installed — using Python fallback\033[0m\n", tty_fd)
    else:
        import importlib

        try:
            importlib.import_module("rampa._core")
        except ImportError:
            _tty_write("\033[33m⚠ build succeeded but import failed\033[0m\n", tty_fd)
    finally:
        elapsed = time.monotonic() - t0
        _tty_write(f"\033[1m✓ native build ({elapsed:.1f}s)\033[0m\n", tty_fd)
        if tty_fd is not None:
            os.close(tty_fd)


_ensure_native_extension()
