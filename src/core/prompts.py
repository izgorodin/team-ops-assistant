"""Prompt loading utilities with Jinja2 templating.

Centralizes prompt loading and caching for consistent template management.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Template

# Prompts directory relative to repository root
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# Template cache
_template_cache: dict[str, Template] = {}


def load_prompt(name: str, **variables: Any) -> str:
    """Load and render a prompt template.

    Args:
        name: Prompt name (e.g., "agent_timezone" or "ui/onboarding").
        **variables: Template variables to render.

    Returns:
        Rendered prompt string.

    Raises:
        FileNotFoundError: If prompt file doesn't exist.
    """
    # Get cached template or load from file
    if name not in _template_cache:
        prompt_path = PROMPTS_DIR / f"{name}.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_path}")

        with prompt_path.open(encoding="utf-8") as f:
            _template_cache[name] = Template(f.read())

    # Render template with variables
    return _template_cache[name].render(**variables).strip()


def get_agent_system_prompt(current_tz: str | None = None) -> str:
    """Get the timezone agent system prompt.

    Args:
        current_tz: Current user timezone for re-verify context.

    Returns:
        Rendered system prompt.
    """
    return load_prompt("agent_timezone", current_tz=current_tz)


def get_ui_message(name: str, **variables: Any) -> str:
    """Get a UI message template.

    Args:
        name: UI message name (e.g., "onboarding", "saved").
        **variables: Template variables.

    Returns:
        Rendered UI message.
    """
    return load_prompt(f"ui/{name}", **variables)
