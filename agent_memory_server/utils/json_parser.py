"""Utility functions for parsing JSON responses, especially from LLM outputs."""

import json
import re


def clean_json_string(content: str) -> str:
    """
    Clean a JSON string by removing common LLM output artifacts.

    Handles:
    - Markdown code blocks (```json ... ``` or ``` ... ```)
    - Leading/trailing whitespace
    - BOM characters

    Args:
        content: The raw string content from LLM response

    Returns:
        Cleaned string ready for json.loads()
    """
    if not content:
        return content

    # Strip BOM and whitespace
    content = content.strip()

    # Handle UTF-8 BOM
    if content.startswith("\ufeff"):
        content = content[1:]

    # Remove markdown code block wrappers
    # Match ```json ... ``` or just ``` ... ```
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]

    # Remove closing ``` if present
    content = content.rstrip()
    if content.endswith("```"):
        content = content[:-3]

    return content.strip()


def parse_json_with_fallback(content: str, logger=None) -> dict:
    """
    Parse JSON with fallback repair mechanisms for malformed responses.

    Args:
        content: The JSON content to parse
        logger: Optional logger instance for warning/error reporting

    Returns:
        Parsed JSON dictionary

    Raises:
        json.JSONDecodeError: If all parsing attempts fail
    """
    # First try: clean and parse
    cleaned = clean_json_string(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Second try: attempt repair for common issues
    if logger:
        logger.warning(
            f"Initial JSON parsing failed, attempting repair on content: {cleaned[:500]}..."
        )

    # Try to extract memories array and reconstruct
    memories_match = re.search(r'"memories"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
    if memories_match:
        try:
            memories_json = '{"memories": [' + memories_match.group(1) + "]}"
            result = json.loads(memories_json)
            if logger:
                logger.info("Successfully repaired malformed JSON response")
            return result
        except json.JSONDecodeError:
            pass

    # Third try: look for any JSON object in the content
    json_match = re.search(r"\{[\s\S]*\}", cleaned)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # If all attempts fail, try the original content one more time
    return json.loads(content)
