"""LLM fallback for time detection and extraction.

When ML classifier is uncertain (probability 0.3-0.7), use LLM for final decision.
When regex extraction fails, use LLM to extract times.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from jinja2 import Template

from src.core.models import ParsedTime

if TYPE_CHECKING:
    from src.settings import CircuitBreakerConfig

logger = logging.getLogger(__name__)


# ============================================================================
# Circuit Breaker for API Resilience
# ============================================================================


class LLMCircuitBreaker:
    """Circuit breaker to prevent cascading failures when LLM API is down.

    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: After N failures, skip LLM calls for reset_timeout_seconds
    """

    def __init__(self, config: CircuitBreakerConfig) -> None:
        """Initialize circuit breaker with configuration."""
        self.config = config
        self._failures = 0
        self._last_failure_time = 0.0

    def is_open(self) -> bool:
        """Check if circuit is open (should skip LLM calls).

        Returns:
            True if circuit is open (skip LLM), False if closed (allow LLM).
        """
        if not self.config.enabled:
            return False

        if self._failures >= self.config.failure_threshold:
            # Check if reset timeout has passed
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.config.reset_timeout_seconds:
                # Reset after timeout - allow one retry
                self._failures = 0
                return False
            return True

        return False

    def record_failure(self) -> None:
        """Record an API failure."""
        self._failures += 1
        self._last_failure_time = time.time()
        logger.warning(f"LLM circuit breaker: failure #{self._failures}")

    def record_success(self) -> None:
        """Record a successful API call, resetting failure count."""
        if self._failures > 0:
            logger.info("LLM circuit breaker: success, resetting failure count")
        self._failures = 0

    def reset(self) -> None:
        """Reset circuit breaker to initial state (for testing)."""
        self._failures = 0
        self._last_failure_time = 0.0


# Global circuit breaker instance (lazy loaded with thread-safe initialization)
import threading

_circuit_breaker: LLMCircuitBreaker | None = None
_circuit_breaker_lock = threading.Lock()


def reset_circuit_breaker() -> None:
    """Reset global circuit breaker (useful for testing)."""
    global _circuit_breaker
    with _circuit_breaker_lock:
        _circuit_breaker = None


def get_circuit_breaker() -> LLMCircuitBreaker:
    """Get global circuit breaker instance.

    Thread-safe with double-checked locking pattern.
    """
    global _circuit_breaker

    # Fast path: already initialized
    if _circuit_breaker is not None:
        return _circuit_breaker

    # Slow path: acquire lock and initialize
    with _circuit_breaker_lock:
        # Double-check after acquiring lock
        if _circuit_breaker is not None:
            return _circuit_breaker

        from src.settings import get_settings

        config = get_settings().config.llm.circuit_breaker
        _circuit_breaker = LLMCircuitBreaker(config)
        return _circuit_breaker


# Load prompt templates
DETECT_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "trigger_detect.md"
EXTRACT_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "parse_time.md"
TZ_RESOLVE_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "timezone_resolve.md"
_detect_prompt_template: Template | None = None
_extract_prompt_template: Template | None = None
_tz_resolve_prompt_template: Template | None = None


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


def _get_tz_resolve_prompt_template() -> Template:
    """Load and cache timezone resolution prompt template."""
    global _tz_resolve_prompt_template
    if _tz_resolve_prompt_template is None:
        with TZ_RESOLVE_PROMPT_PATH.open(encoding="utf-8") as f:
            _tz_resolve_prompt_template = Template(f.read())
    assert _tz_resolve_prompt_template is not None
    return _tz_resolve_prompt_template


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

        # Parse response with null guards
        content = _extract_content_from_response(data)
        if content is None:
            logger.warning("LLM response missing content")
            return True  # Fail open
        result = _parse_llm_response(content)

        logger.debug(f"LLM fallback: '{text[:50]}...' -> {result}")
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code}")
        return True  # Fail open
    except httpx.TimeoutException:
        logger.error("LLM API timeout")
        return True  # Fail open
    except (KeyError, TypeError, ValueError) as e:
        # JSON parsing or response format issues
        logger.warning(f"LLM response parsing error: {e}")
        return True  # Fail open
    except Exception as e:
        logger.exception(f"Unexpected LLM fallback error: {e}")
        return True  # Fail open


def _extract_content_from_response(data: dict) -> str | None:
    """Safely extract content from LLM API response.

    Args:
        data: Parsed JSON response from LLM API.

    Returns:
        Content string or None if not found.
    """
    try:
        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            return None
        message = choices[0].get("message")
        if not message or not isinstance(message, dict):
            return None
        content = message.get("content")
        return str(content) if content is not None else None
    except (KeyError, IndexError, TypeError):
        return None


def _parse_llm_response(content: str) -> bool:
    """Parse LLM response to extract time detection result.

    Args:
        content: Raw LLM response content.

    Returns:
        True if LLM says contains_time is true.
    """
    # Try to extract JSON from response
    try:
        # Look for JSON block in markdown - use find() to avoid ValueError
        json_str = ""
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()

        # Fallback: find raw JSON object
        if not json_str:
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

    # Check circuit breaker first
    cb = get_circuit_breaker()
    if cb.is_open():
        logger.warning("LLM circuit breaker is open, skipping extraction")
        return []

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

        content = _extract_content_from_response(data)
        if content is None:
            logger.warning("LLM extraction response missing content")
            cb.record_failure()
            return []
        times = _parse_extraction_response(content, extraction_config.default_confidence)

        # Record success
        cb.record_success()

        logger.debug(f"LLM extraction: '{text[:50]}...' -> {len(times)} times")
        return times

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code}")
        cb.record_failure()
        return []
    except httpx.TimeoutException:
        logger.error("LLM API timeout")
        cb.record_failure()
        return []
    except (KeyError, TypeError, ValueError) as e:
        # JSON parsing or response format issues
        logger.warning(f"LLM extraction response parsing error: {e}")
        cb.record_failure()
        return []
    except Exception as e:
        logger.exception(f"Unexpected LLM extraction error: {e}")
        cb.record_failure()
        return []


def _parse_extraction_response(content: str, default_confidence: float = 0.8) -> list[ParsedTime]:
    """Parse LLM extraction response to get ParsedTime list.

    Args:
        content: Raw LLM response content.
        default_confidence: Default confidence for extracted times.

    Returns:
        List of ParsedTime objects.
    """
    try:
        # Extract JSON from response - use find() to avoid ValueError
        json_str = ""
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()

        # Fallback: find raw JSON object
        if not json_str:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
            else:
                logger.warning(f"No JSON found in LLM response: {content[:200]}")
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
                        confidence=float(t.get("confidence", default_confidence)),
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Failed to parse time entry: {e}")
                continue

        return parsed

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse LLM extraction response: {e}")
        return []


# ============================================================================
# Timezone Resolution (when explicit TZ unclear or clarification needed)
# ============================================================================


from dataclasses import dataclass as dc_dataclass


@dc_dataclass(frozen=True)
class TzResolutionResult:
    """Result of timezone resolution via LLM."""

    source_tz: str | None
    is_user_tz: bool
    confidence: float
    reasoning: str = ""


async def resolve_timezone_context(
    message: str,
    user_tz: str | None = None,
    detected_times: list[str] | None = None,
    recent_messages: list[str] | None = None,
    chat_tzs: list[str] | None = None,
) -> TzResolutionResult:
    """Use LLM to resolve which timezone a time reference is in.

    Determines whether user is speaking about their own timezone
    or explicitly mentioning a specific timezone.

    Args:
        message: Current message with time reference.
        user_tz: User's verified timezone (IANA format).
        detected_times: List of time strings detected in message.
        recent_messages: Previous messages for context.
        chat_tzs: Timezones of other chat participants.

    Returns:
        TzResolutionResult with source_tz, is_user_tz, confidence.
    """
    from src.settings import get_settings

    settings = get_settings()

    # Check circuit breaker first
    cb = get_circuit_breaker()
    if cb.is_open():
        logger.warning("LLM circuit breaker is open, using user's TZ as fallback")
        return TzResolutionResult(
            source_tz=user_tz,
            is_user_tz=True,
            confidence=0.5,
            reasoning="Circuit breaker open, defaulting to user timezone",
        )

    api_key = settings.nvidia_api_key
    if not api_key:
        logger.warning("NVIDIA_API_KEY not set, using user's TZ as fallback")
        return TzResolutionResult(
            source_tz=user_tz,
            is_user_tz=True,
            confidence=0.5,
            reasoning="No API key, defaulting to user timezone",
        )

    # Build prompt
    template = _get_tz_resolve_prompt_template()
    prompt = template.render(
        message=message,
        recent_messages=recent_messages or [],
        detected_times=detected_times or [],
        user_tz=user_tz or "unknown",
        chat_tzs=chat_tzs or [],
    )

    # Use extraction config (similar complexity)
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

        content = _extract_content_from_response(data)
        if content is None:
            logger.warning("LLM TZ resolution response missing content")
            cb.record_failure()
            return TzResolutionResult(
                source_tz=user_tz,
                is_user_tz=True,
                confidence=0.3,
                reasoning="API response missing content",
            )
        result = _parse_tz_resolution_response(content, user_tz)

        # Record success
        cb.record_success()

        logger.debug(
            f"LLM TZ resolution: '{message[:50]}...' -> "
            f"{result.source_tz} (is_user_tz={result.is_user_tz})"
        )
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error in TZ resolution: {e.response.status_code}")
        cb.record_failure()
        return TzResolutionResult(
            source_tz=user_tz,
            is_user_tz=True,
            confidence=0.3,
            reasoning=f"API error: {e.response.status_code}",
        )
    except httpx.TimeoutException:
        logger.error("LLM API timeout in TZ resolution")
        cb.record_failure()
        return TzResolutionResult(
            source_tz=user_tz,
            is_user_tz=True,
            confidence=0.3,
            reasoning="API timeout",
        )
    except (KeyError, TypeError, ValueError) as e:
        # JSON parsing or response format issues
        logger.warning(f"LLM TZ resolution response parsing error: {e}")
        cb.record_failure()
        return TzResolutionResult(
            source_tz=user_tz,
            is_user_tz=True,
            confidence=0.3,
            reasoning=f"Parse error: {e}",
        )
    except Exception as e:
        logger.exception(f"Unexpected LLM TZ resolution error: {e}")
        cb.record_failure()
        return TzResolutionResult(
            source_tz=user_tz,
            is_user_tz=True,
            confidence=0.3,
            reasoning=f"Unexpected error: {e}",
        )


def _parse_tz_resolution_response(content: str, fallback_tz: str | None) -> TzResolutionResult:
    """Parse LLM timezone resolution response.

    Args:
        content: Raw LLM response content.
        fallback_tz: Fallback timezone if parsing fails.

    Returns:
        TzResolutionResult parsed from response.
    """
    try:
        # Extract JSON from response
        json_str = ""
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()

        # Fallback: find raw JSON object
        if not json_str:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
            else:
                logger.warning(f"No JSON found in TZ resolution response: {content[:200]}")
                return TzResolutionResult(
                    source_tz=fallback_tz,
                    is_user_tz=True,
                    confidence=0.4,
                    reasoning="Failed to parse response",
                )

        result = json.loads(json_str)

        return TzResolutionResult(
            source_tz=result.get("source_tz") or fallback_tz,
            is_user_tz=bool(result.get("is_user_tz", True)),
            confidence=float(result.get("confidence", 0.7)),
            reasoning=str(result.get("reasoning", "")),
        )

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Failed to parse TZ resolution response: {e}")
        return TzResolutionResult(
            source_tz=fallback_tz,
            is_user_tz=True,
            confidence=0.4,
            reasoning=f"Parse error: {e}",
        )
