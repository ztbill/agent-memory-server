import asyncio
import json
from typing import Any

from agent_memory_server.config import settings


class LLMClientAdapter:
    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
    ):
        self.model = model or settings.generation_model
        self.temperature = temperature

    async def achat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        from agent_memory_server.llm import LLMClient

        temp = temperature if temperature is not None else self.temperature
        response = await LLMClient.create_chat_completion(
            model=self.model,
            messages=messages,
            temperature=temp,
            response_format=response_format,
        )
        return response.content

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        response_format: dict[str, str] | None = None,
        max_retries: int = 3,
    ) -> str:
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self.achat_completion(messages, temperature, response_format)
                )
                return result
            except Exception as e:
                if attempt < max_retries - 1:
                    import time

                    wait_time = 2**attempt
                    print(
                        f"LLM API call failed (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise

    def extract_json(self, text: str) -> Any:
        text = text.strip()

        common_prefixes = [
            "Here's the JSON:",
            "Here is the JSON:",
            "The JSON is:",
            "JSON:",
            "Result:",
            "Output:",
            "Answer:",
        ]
        for prefix in common_prefixes:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix) :].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```json" in text.lower():
            start_marker = "```json"
            start_idx = text.lower().find(start_marker)
            if start_idx != -1:
                start = start_idx + len(start_marker)
                end = text.find("```", start)
                if end != -1:
                    json_str = text[start:end].strip()
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        pass

        if "```" in text:
            start = text.find("```") + 3
            newline = text.find("\n", start)
            if newline != -1 and newline - start < 20:
                start = newline + 1
            end = text.find("```", start)
            if end != -1:
                json_str = text[start:end].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        raise ValueError(
            f"Failed to extract valid JSON from response. First 300 chars: {text[:300]}..."
        )
