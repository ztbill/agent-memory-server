"""
Answer Generator - Final synthesis from retrieved contexts

Section 3.3: Intent-Aware Retrieval Planning
Generates answers from the merged context C_q after multi-view retrieval
"""

from agent_memory_server.config import settings
from agent_memory_server.engines.simplemem.adapters.llm_client import LLMClientAdapter
from agent_memory_server.engines.simplemem.adapters.memory_entry import (
    SimpleMemMemoryEntry as MemoryEntry,
)


class AnswerGenerator:
    """
    Answer Generator - Synthesis from retrieved memory units (Section 3.3)

    Generates answers from C_q = R_sem ∪ R_lex ∪ R_sym
    """

    def __init__(self, llm_client: LLMClientAdapter = None):
        self.llm_client = llm_client or LLMClientAdapter()

    def generate_answer(self, query: str, contexts: list[MemoryEntry]) -> str:
        if not contexts:
            return "No relevant information found"

        context_str = self._format_contexts(contexts)
        prompt = self._build_answer_prompt(query, context_str)

        messages = [
            {
                "role": "system",
                "content": "You are a professional Q&A assistant. Extract concise answers from context. You must output valid JSON format.",
            },
            {"role": "user", "content": prompt},
        ]

        max_retries = 3
        use_json_format = getattr(settings, "USE_JSON_FORMAT", False)
        for attempt in range(max_retries):
            try:
                response_format = None
                if use_json_format:
                    response_format = {"type": "json_object"}

                response = self.llm_client.chat_completion(
                    messages, temperature=0.1, response_format=response_format
                )

                result = self.llm_client.extract_json(response)
                return result.get("answer", response.strip())

            except Exception as e:
                if attempt < max_retries - 1:
                    print(
                        f"Answer generation attempt {attempt + 1}/{max_retries} failed: {e}. Retrying..."
                    )
                else:
                    print(
                        f"Warning: Failed to parse JSON response after {max_retries} attempts: {e}"
                    )
                    if "response" in locals():
                        return response.strip()
                    return "Failed to generate answer"

    def _format_contexts(self, contexts: list[MemoryEntry]) -> str:
        formatted = []
        for i, entry in enumerate(contexts, 1):
            parts = [f"[Context {i}]"]
            parts.append(f"Content: {entry.lossless_restatement}")

            if entry.timestamp:
                parts.append(f"Time: {entry.timestamp}")

            if entry.location:
                parts.append(f"Location: {entry.location}")

            if entry.persons:
                parts.append(f"Persons: {', '.join(entry.persons)}")

            if entry.entities:
                parts.append(f"Related Entities: {', '.join(entry.entities)}")

            if entry.topic:
                parts.append(f"Topic: {entry.topic}")

            formatted.append("\n".join(parts))

        return "\n\n".join(formatted)

    def _build_answer_prompt(self, query: str, context_str: str) -> str:
        return f"""
Answer the user's question based on the provided context.

User Question: {query}

Relevant Context:
{context_str}

Requirements:
1. First, think through the reasoning process
2. Then provide a very CONCISE answer (short phrase about core information)
3. Answer must be based ONLY on the provided context
4. All dates in the response must be formatted as 'DD Month YYYY' but you can output more or less details if needed
5. Return your response in JSON format
6. use chinese return

Output Format:
```json
{{
  "reasoning": "Brief explanation of your thought process",
  "answer": "Concise answer in a short phrase"
}}
```

Example:
Question: "When will they meet?"
Context: "Alice suggested meeting Bob at 2025-11-16T14:00:00..."

Output:
```json
{{
  "reasoning": "The context explicitly states the meeting time as 2025-11-16T14:00:00",
  "answer": "16 November 2025 at 2:00 PM"
}}
```

Now answer the question. Return ONLY the JSON, no other text.
"""
