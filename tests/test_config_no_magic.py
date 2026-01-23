"""Tests that verify no magic numbers in code.

TDD: These tests define the contract that ALL tunable parameters
must be loaded from configuration, not hardcoded.

Target: Zero hardcoded numeric constants in core business logic.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import NamedTuple

import pytest


class MagicNumber(NamedTuple):
    """Found magic number in code."""

    file: str
    line: int
    value: str
    context: str


# Allowed numeric literals (not considered magic numbers)
ALLOWED_LITERALS = {
    # Common programming constants
    "0",
    "1",
    "-1",
    "2",
    # Boolean-like
    "True",
    "False",
    "None",
    # String/list operations
    "0.0",
    "1.0",
    # Range boundaries for validation
    "100",  # percentage
    # HTTP status codes (allowed inline)
    "200",
    "201",
    "204",
    "400",
    "401",
    "403",
    "404",
    "500",
    "501",
    "502",
    "503",
}

# Files/patterns to skip
SKIP_PATTERNS = [
    "test_",  # Test files can have literals
    "__pycache__",
    ".pyc",
    "conftest.py",
]

# Known exceptions with justification
KNOWN_EXCEPTIONS = {
    # Format: (filename, line_number, value): "justification"
    ("models.py", "hour", "23"): "hour validation range",
    ("models.py", "minute", "59"): "minute validation range",
    ("models.py", "hour", "0"): "hour validation range",
    ("models.py", "minute", "0"): "minute validation range",
}


def find_magic_numbers_in_file(filepath: Path) -> list[MagicNumber]:
    """Find potential magic numbers in a Python file."""
    magic_numbers: list[MagicNumber] = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return []

    lines = content.split("\n")

    for node in ast.walk(tree):
        # Check numeric literals
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            value = str(node.value)
            if value not in ALLOWED_LITERALS:
                line_num = node.lineno
                context = lines[line_num - 1].strip() if line_num <= len(lines) else ""

                # Skip if in allowed exceptions
                filename = filepath.name
                if any(filename == exc[0] and exc[1] in context for exc in KNOWN_EXCEPTIONS):
                    continue

                # Skip if it's a type annotation or default in function signature
                if "def " in context and "=" in context:
                    # Might be a default parameter - check if it's config-loaded
                    pass

                magic_numbers.append(
                    MagicNumber(
                        file=str(filepath.relative_to(filepath.parent.parent)),
                        line=line_num,
                        value=value,
                        context=context,
                    )
                )

    return magic_numbers


def get_core_python_files() -> list[Path]:
    """Get all Python files in src/core/."""
    core_dir = Path(__file__).parent.parent / "src" / "core"
    if not core_dir.exists():
        return []

    files = []
    for filepath in core_dir.rglob("*.py"):
        # Skip test files and cache
        if any(pattern in str(filepath) for pattern in SKIP_PATTERNS):
            continue
        files.append(filepath)

    return files


class TestNoMagicNumbers:
    """Tests that core modules have no magic numbers."""

    def test_time_parse_no_magic_confidence(self) -> None:
        """time_parse.py should load confidence values from config."""
        filepath = Path(__file__).parent.parent / "src" / "core" / "time_parse.py"
        if not filepath.exists():
            pytest.skip("File not found")

        content = filepath.read_text()

        # Check for hardcoded confidence values
        confidence_pattern = r"confidence\s*[=:]\s*(0\.\d+)"
        matches = re.findall(confidence_pattern, content)

        assert not matches, (
            f"Found hardcoded confidence values in time_parse.py: {matches}. "
            "These should be loaded from settings.config.time_parsing.confidence.*"
        )

    def test_time_classifier_no_magic_thresholds(self) -> None:
        """time_classifier.py should load thresholds from config."""
        filepath = Path(__file__).parent.parent / "src" / "core" / "time_classifier.py"
        if not filepath.exists():
            pytest.skip("File not found")

        content = filepath.read_text()
        lines = content.split("\n")

        # Check for hardcoded module-level constants
        module_constants = ["_LONG_TEXT_THRESHOLD", "_WINDOW_SIZE"]
        hardcoded = []
        for const in module_constants:
            if f"{const} = " in content:
                hardcoded.append(const)

        # Check for hardcoded values in function calls (not using config)
        for i, line in enumerate(lines, 1):
            # Skip comments and imports
            stripped = line.strip()
            if stripped.startswith("#") or "import" in line:
                continue

            # Check for hardcoded numeric values in specific patterns
            # These should use config.* references instead
            if "ngram_range=" in line and "config" not in line:
                hardcoded.append(f"ngram_range at line {i}")
            if "min_df=" in line and "config" not in line:
                hardcoded.append(f"min_df at line {i}")
            if "max_df=" in line and "config" not in line:
                hardcoded.append(f"max_df at line {i}")
            if "max_iter=" in line and "config" not in line:
                hardcoded.append(f"max_iter at line {i}")
            if "random_state=" in line and "config" not in line:
                hardcoded.append(f"random_state at line {i}")

        assert not hardcoded, (
            f"Found hardcoded values in time_classifier.py: {hardcoded}. "
            "These should be loaded from settings.config.classifier.*"
        )

    def test_timezone_identity_no_magic_confidence(self) -> None:
        """timezone_identity.py should load confidence values from config."""
        filepath = Path(__file__).parent.parent / "src" / "core" / "timezone_identity.py"
        if not filepath.exists():
            pytest.skip("File not found")

        content = filepath.read_text()

        # Check for hardcoded confidence values like 0.9, 0.6, 0.5
        # that are not from settings
        lines = content.split("\n")
        issues = []

        for i, line in enumerate(lines, 1):
            # Skip comments and imports
            if line.strip().startswith("#") or "import" in line:
                continue

            # Look for hardcoded confidence assignments
            if (
                re.search(r"confidence\s*=\s*0\.[0-9]+", line)
                and "settings" not in line
                and "config" not in line
            ):
                issues.append(f"Line {i}: {line.strip()}")

        assert not issues, (
            "Found hardcoded confidence in timezone_identity.py:\n"
            + "\n".join(issues)
            + "\nThese should be loaded from settings.config.confidence.*"
        )

    def test_llm_fallback_no_magic_timeouts(self) -> None:
        """llm_fallback.py should load timeouts and params from config."""
        filepath = Path(__file__).parent.parent / "src" / "core" / "llm_fallback.py"
        if not filepath.exists():
            pytest.skip("File not found")

        content = filepath.read_text()

        # Check for hardcoded timeout values
        timeout_pattern = r"timeout\s*=\s*(\d+\.?\d*)"
        matches = re.findall(timeout_pattern, content)

        # Filter out settings references
        issues = [m for m in matches if float(m) > 1.0]  # > 1 second is suspicious

        assert not issues, (
            f"Found hardcoded timeouts in llm_fallback.py: {issues}. "
            "These should be loaded from settings.config.llm.detection.timeout "
            "and settings.config.llm.extraction.timeout"
        )


class TestConfigCompleteness:
    """Tests that configuration has all required sections."""

    def test_config_has_time_parsing_section(self) -> None:
        """configuration.yaml must have time_parsing.confidence section."""
        from src.settings import get_settings

        settings = get_settings()

        # This will fail until we add the section
        assert hasattr(settings.config, "time_parsing"), (
            "configuration.yaml must have 'time_parsing' section with confidence values"
        )

    def test_config_has_classifier_section(self) -> None:
        """configuration.yaml must have classifier section."""
        from src.settings import get_settings

        settings = get_settings()

        assert hasattr(settings.config, "classifier"), (
            "configuration.yaml must have 'classifier' section with ML parameters"
        )

    def test_config_has_http_timeouts_section(self) -> None:
        """configuration.yaml must have http.timeouts section."""
        from src.settings import get_settings

        settings = get_settings()

        assert hasattr(settings.config, "http"), (
            "configuration.yaml must have 'http' section with timeouts"
        )
