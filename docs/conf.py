"""Sphinx configuration for rampa."""

from __future__ import annotations

import pathlib
import sys
import tomllib

from gp_sphinx.config import merge_sphinx_config

cwd = pathlib.Path(__file__).parent
project_root = cwd.parent
project_src = project_root / "src"

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_src))
sys.path.insert(0, str(cwd / "_ext"))

project_metadata = tomllib.loads((project_root / "pyproject.toml").read_text())["project"]

conf = merge_sphinx_config(
    project=project_metadata["name"],
    version=project_metadata["version"],
    copyright="2026, Tony Narlock",
    source_repository="https://github.com/tony/rampa/",
    docs_url="https://rampa.git-pull.com/",
    source_branch="main",
    extra_extensions=[
        "sphinx_autodoc_api_style",
        "docs._ext.widgets",
    ],
    intersphinx_mapping={
        "python": ("https://docs.python.org/3/", None),
    },
)

globals().update(conf)
