"""Compiles and renders the Jinja2 template into a clean Markdown report."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ...paths import repo_path


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(repo_path("templates", "valuation"))),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )


def render_valuation_report(report_context: dict[str, Any]) -> str:
    """Render the Markdown report from a built report context.
    Collapses multiple runs of blank lines for stable, readable output,
    and ensures a single trailing newline.
    """
    template_name = "valuation-analysis-v1.tr.md.j2"
    env = _environment()
    template = env.get_template(template_name)
    rendered = template.render(**report_context)

    lines = [line.rstrip() for line in rendered.splitlines()]
    collapsed: list[str] = []
    for line in lines:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return "\n".join(collapsed) + "\n"
