"""Self-contained test archives for distributed execution.

A ``.rampa`` file is a zip archive containing the test script,
data files, dependency list, and a manifest for reproducibility.

>>> import rampa.distributed.archive
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import typing as t
import zipfile
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArchiveManifest:
    """Metadata for a rampa test archive.

    >>> m = ArchiveManifest(entrypoint="load_test.py")
    >>> m.version
    1
    """

    version: int = 1
    entrypoint: str = "script.py"
    python_version: str = ""
    dependencies: list[str] = field(default_factory=list)
    data_files: list[str] = field(default_factory=list)
    config: dict[str, t.Any] = field(default_factory=dict)
    sha256: str = ""


def create_archive(
    script_path: str | pathlib.Path,
    output_path: str | pathlib.Path,
    data_files: list[str | pathlib.Path] | None = None,
    requirements: list[str] | None = None,
) -> pathlib.Path:
    """Create a self-contained ``.rampa`` test archive.

    Parameters
    ----------
    script_path : str | Path
        Path to the test script.
    output_path : str | Path
        Output ``.rampa`` file path.
    data_files : list[str | Path] | None
        Additional data files to include.
    requirements : list[str] | None
        pip-compatible dependency strings.

    Returns
    -------
    Path
        The created archive path.

    >>> import tempfile, pathlib
    >>> with tempfile.TemporaryDirectory() as d:
    ...     script = pathlib.Path(d) / "test.py"
    ...     _ = script.write_text("async def default(w): pass")
    ...     out = pathlib.Path(d) / "test.rampa"
    ...     result = create_archive(script, out)
    ...     result.suffix
    '.rampa'
    """
    script = pathlib.Path(script_path)
    output = pathlib.Path(output_path)

    if not script.exists():
        msg = f"script not found: {script}"
        raise FileNotFoundError(msg)

    manifest = ArchiveManifest(
        entrypoint="script.py",
        dependencies=requirements or [],
        data_files=[str(f) for f in (data_files or [])],
    )

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("script.py", script.read_text())

        if data_files:
            for df in data_files:
                df_path = pathlib.Path(df)
                zf.write(df_path, f"data/{df_path.name}")

        if requirements:
            zf.writestr(
                "requirements.txt",
                "\n".join(requirements) + "\n",
            )

        manifest_dict = {
            "version": manifest.version,
            "entrypoint": manifest.entrypoint,
            "dependencies": manifest.dependencies,
            "data_files": manifest.data_files,
        }
        zf.writestr("manifest.json", json.dumps(manifest_dict, indent=2))

    file_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    with zipfile.ZipFile(output, "a") as zf:
        zf.comment = f"sha256:{file_hash}".encode()

    return output


def extract_archive(
    archive_path: str | pathlib.Path,
    target_dir: str | pathlib.Path,
) -> ArchiveManifest:
    """Extract a ``.rampa`` archive and return its manifest.

    Parameters
    ----------
    archive_path : str | Path
        Path to the ``.rampa`` file.
    target_dir : str | Path
        Directory to extract into.

    Returns
    -------
    ArchiveManifest
        Parsed manifest from the archive.

    >>> import tempfile, pathlib
    >>> with tempfile.TemporaryDirectory() as d:
    ...     script = pathlib.Path(d) / "test.py"
    ...     _ = script.write_text("async def default(w): pass")
    ...     archive = pathlib.Path(d) / "test.rampa"
    ...     _ = create_archive(script, archive)
    ...     out_dir = pathlib.Path(d) / "extracted"
    ...     manifest = extract_archive(archive, out_dir)
    ...     manifest.entrypoint
    'script.py'
    """
    archive = pathlib.Path(archive_path)
    target = pathlib.Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target)
        manifest_text = zf.read("manifest.json").decode()

    manifest_data = json.loads(manifest_text)
    return ArchiveManifest(
        version=manifest_data.get("version", 1),
        entrypoint=manifest_data.get("entrypoint", "script.py"),
        dependencies=manifest_data.get("dependencies", []),
        data_files=manifest_data.get("data_files", []),
        config=manifest_data.get("config", {}),
    )
