"""LLM fallback for time detection and extraction.

When ML classifier is uncertain (probability 0.3-0.7), use LLM for final decision.
When regex extraction fails, use LLM to extract times.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import httpx
from jinja2 import Template

from src.core.models import ParsedTime

logger = logging.getLogger(__name__)

# Load prompt templates
DETECT_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "trigger_detect.md"
EXTRACT_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "parse_time.md"
_detect_prompt_template: Template | None = None
_extract_prompt_template: Template | None = None


def _get_detect_prompt_template() -> Template:
    """Load and cache detection prompt template."""
    global _detect_prompt_template
    if _detect_prompt_template is None:
        with DETECT_PROMPT_PATH.open(encoding="utf-8") as f:
            _detect_prompt_template = Template(f.read())
    assert _detect_prompt_template is not None
    return _detect_prompt_template


def _get_extract_prompt_template() -> Template:
    """Load and cache extraction prompt template."""
    global _extract_prompt_template
    if _extract_prompt_template is None:
        with EXTRACT_PROMPT_PATH.open(encoding="utf-8") as f:
            _extract_prompt_template = Template(f.read())
    assert _extract_prompt_template is not None
    return _extract_prompt_template


async def detect_time_with_llm(text: str) -> bool:
    """Use LLM to detect if text contains a time reference.

    Args:
        text: Message text to analyze.

    Returns:
        True if LLM detects a time reference.
    """
    from src.settings import get_settings

    settings = get_settings()

    # Check API key
    api_key = settings.nvidia_api_key
    if not api_key:
        logger.warning("NVIDIA_API_KEY not set, falling back to uncertain=True")
        return True  # Fail open - better to have false positive than miss

    # Build prompt
    template = _get_detect_prompt_template()
    prompt = template.render(message=text)

    # Call LLM API with detection-specific settings
    detection_config = settings.config.llm.detection
    try:
        async with httpx.AsyncClient(timeout=detection_config.timeout) as client:
            response = await client.post(
                f"{settings.config.llm.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.config.llm.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": detection_config.max_tokens,
                    "temperature": detection_config.temperature,
                },
            )
            response.raise_for_status()
            data = response.json()

        # Parse response
        content = data["choices"][0]["message"]["content"]
        result = _parse_llm_response(content)

        logger.debug(f"LLM fallback: '{text[:50]}...' -> {result}")
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code}")
        return True  # Fail open
    except httpx.TimeoutException:
        logger.error("LLM API timeout")
        return True  # Fail open
    except Exception as e:
        logger.error(f"LLM fallback error: {e}")
        return True  # Fail open


def _parse_llm_response(content: str) -> bool:
    """Parse LLM response to extract time detection result.

    Args:
        content: Raw LLM response content.

    Returns:
        True if LLM says contains_time is true.
    """
    # Try to extract JSON from response
    try:
        # Look for JSON block in markdown
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            json_str = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            json_str = content[start:end].strip()
        else:
            # Try to find JSON object directly
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end] if start != -1 and end > start else content

        result = json.loads(json_str)
        return bool(result.get("contains_time", False))

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        # Fallback: look for keywords, fail open (True) unless explicitly false
        content_lower = content.lower()
        has_false = (
            '"contains_time": false' in content_lower or '"contains_time":false' in content_lower
        )
        return not has_false


# ============================================================================
# LLM Extraction Fallback (when regex fails)
# ============================================================================


async def extract_times_with_llm(text: str, tz_hint: str | None = None) -> list[ParsedTime]:
    """Use LLM to extract times when regex fails.

    Args:
        text: Message text to parse.
        tz_hint: Optional timezone hint from context.

    Returns:
        List of parsed times, empty if extraction fails.
    """
    from src.settings import get_settings

    settings = get_settings()

    api_key = settings.nvidia_api_key
    if not api_key:
        logger.warning("NVIDIA_API_KEY not set, cannot extract times")
        return []

    # Build prompt
    template = _get_extract_prompt_template()
    prompt = template.render(
        message=text,
        current_datetime=datetime.now().isoformat(),
        timezone_hints=tz_hint or "none",
    )

    # Use extraction-specific settings
    extraction_config = settings.config.llm.extraction
    try:
        async with httpx.AsyncClient(timeout=extraction_config.timeout) as client:
            response = await client.post(
                f"{settings.config.llm.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.config.llm.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": extraction_config.max_tokens,
                    "temperature": extraction_config.temperature,
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        times = _parse_extraction_response(content)

        logger.debug(f"LLM extraction: '{text[:50]}...' -> {len(times)} times")
        return times

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code}")
        return []
    except httpx.TimeoutException:
        logger.error("LLM API timeout")
        return []
    except Exception as e:
        logger.error(f"LLM extraction error: {e}")
        return []


def _parse_extraction_response(content: str) -> list[ParsedTime]:
    """Parse LLM extraction response to get ParsedTime list.

    Args:
        content: Raw LLM response content.

    Returns:
        List of ParsedTime objects.
    """
    try:
        # Extract JSON from response
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            json_str = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            json_str = content[start:end].strip()
        else:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
            else:
                return []

        result = json.loads(json_str)
        times_data = result.get("times", [])

        parsed: list[ParsedTime] = []
        for t in times_data:
            try:
                hour = int(t.get("hour", 0))
                minute = int(t.get("minute", 0))

                # Validate hour/minute
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    continue

                parsed.append(
                    ParsedTime(
                        original_text=str(t.get("original_text", "")),
                        hour=hour,
                        minute=minute,
                        timezone_hint=t.get("timezone_hint"),
                        is_tomorrow=bool(t.get("is_tomorrow", False)),
                        confidence=float(t.get("confidence", 0.8)),
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Failed to parse time entry: {e}")
                continue

        return parsed

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse LLM extraction response: {e}")
        return []
