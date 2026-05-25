"""Sphinx configuration for rampa."""

from __future__ import annotations

import pathlib
import sys
import tomllib

from gp_sphinx.config import merge_sphinx_config
from sphinx.application import Sphinx

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
        "sphinx_autodoc_fastmcp",
        "sphinx_autodoc_argparse.exemplar",
        "docs._ext.widgets",
    ],
    intersphinx_mapping={
        "python": ("https://docs.python.org/3/", None),
    },
    theme_options={
        "announcement": (
            "<em>Pre-alpha.</em> APIs may change. "
            "<a href='https://github.com/tony/rampa/issues'>Feedback welcome</a>."
        ),
    },
)

# FastMCP tool collector
conf["fastmcp_tool_modules"] = ["rampa_fastmcp"]
conf["fastmcp_collector_mode"] = "introspect"
conf["fastmcp_area_map"] = {"rampa_fastmcp": "mcp/tools"}
conf["fastmcp_server_module"] = "rampa.mcp.server:build_mcp_server"

# Safety badges on tool sections
conf["fastmcp_section_badge_map"] = {
    "Run Lifecycle": "mutating",
    "Metrics": "readonly",
    "Thresholds": "readonly",
}
conf["fastmcp_section_badge_pages"] = ("mcp/tools", "mcp/index", "index")

# Argparse exemplar
conf["argparse_examples_code_language"] = "console"
conf["argparse_reorder_usage_before_examples"] = True

_gp_setup = conf.pop("setup")


def setup(app: Sphinx) -> None:
    """Configure project-specific Sphinx hooks."""
    _gp_setup(app)
    app.add_css_file("css/project-cards.css")


globals().update(conf)
