"""LLM-based intent classification for ambiguous geo detections.

When a city is detected via geonames but no explicit relocation pattern matched,
this module classifies the user's intent using an LLM.

Intents:
- time_query: User asking about time/scheduling in that city
- relocation: User moved to, is in, or traveling to that city
- false_positive: City mentioned but not about time or location
- uncertain: Cannot determine intent - ask user

Usage:
    intent = await classify_geo_intent("я в москве", "Moscow")
    if intent == GeoIntent.RELOCATION:
        # Create CONFIRM_RELOCATION session
"""

from __future__ import annotations

import logging
from enum import Enum

from langchain_openai import ChatOpenAI

from src.core.prompts import load_prompt
from src.settings import get_settings

logger = logging.getLogger(__name__)


class GeoIntent(str, Enum):
    """Intent classification for ambiguous geo mentions."""

    TIME_QUERY = "time_query"  # User asking about time in city
    RELOCATION = "relocation"  # User moved to / is in city
    FALSE_POSITIVE = "false_positive"  # City mentioned but not relevant
    UNCERTAIN = "uncertain"  # Can't determine - ask user


async def classify_geo_intent(
    text: str,
    city: str,
) -> GeoIntent:
    """Classify intent when city is detected but pattern unclear.

    Uses LLM to determine what the user wants when they mention a city
    without explicit relocation or time patterns.

    Args:
        text: Original message text.
        city: Detected city name (normalized).

    Returns:
        GeoIntent classification.

    Examples:
        >>> await classify_geo_intent("в 15 по москве", "Moscow")
        GeoIntent.TIME_QUERY
        >>> await classify_geo_intent("я в москве", "Moscow")
        GeoIntent.RELOCATION
        >>> await classify_geo_intent("москва - столица", "Moscow")
        GeoIntent.FALSE_POSITIVE
    """
    settings = get_settings()

    try:
        llm = ChatOpenAI(
            base_url=settings.config.llm.base_url,
            api_key=settings.nvidia_api_key,  # type: ignore[arg-type]
            model=settings.config.llm.model,
            temperature=0,
            timeout=10.0,
        ).bind(max_tokens=20)

        prompt = load_prompt("geo_classify", text=text, city=city)
        result = await llm.ainvoke(prompt)
        intent_str = str(result.content).strip().lower()

        # Try to parse the intent
        try:
            return GeoIntent(intent_str)
        except ValueError:
            # LLM returned unexpected value
            logger.warning(f"Unknown intent from LLM: {intent_str!r} for text={text!r}")
            return GeoIntent.UNCERTAIN

    except Exception as e:
        logger.warning(f"Geo intent classification failed: {e}")
        # On error, default to uncertain (will ask user)
        return GeoIntent.UNCERTAIN
