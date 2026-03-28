#!/usr/bin/env python3
"""
SimpleMem Engine Demo

This demo shows how to use the SimpleMem engine for:
1. Memory extraction from dialogues
2. Hybrid retrieval (semantic + keyword + structured)
3. Answer generation

Usage:
    python simplemem_demo.py

Environment:
    - DISABLE_AUTH=true (for local testing)
    - Redis must be running
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def demo_basic_extraction():
    """Demo 1: Basic memory extraction from dialogues."""
    print("\n" + "=" * 60)
    print("Demo 1: Basic Memory Extraction")
    print("=" * 60)

    from agent_memory_server.engines.simplemem import SimpleMemEngine

    engine = SimpleMemEngine(namespace="demo", user_id="demo_user")

    dialogues = [
        ("Alice", "Hi, I'm planning a trip to Tokyo next month."),
        ("Bob", "That sounds great! When exactly are you going?"),
        ("Alice", "I'm going from March 15th to March 22nd, 2026."),
        ("Bob", "Nice! I've been to Tokyo before. What's your budget?"),
        ("Alice", "Around $3000 for the whole trip including flights."),
        ("Bob", "You should definitely visit Shibuya and try the local food."),
    ]

    for speaker, content in dialogues:
        engine.add_dialogue(
            speaker=speaker,
            content=content,
            timestamp="2026-01-15T10:00:00",
            auto_process=False,
        )

    print(f"\nAdded {len(dialogues)} dialogues to buffer")

    engine.process_remaining()

    print(f"\nProcessed {engine.memory_builder.processed_count} dialogues")
    print("Memories stored in RedisVL index!")


def demo_search():
    """Demo 2: Memory search."""
    print("\n" + "=" * 60)
    print("Demo 2: Memory Search")
    print("=" * 60)

    from agent_memory_server.engines.simplemem import SimpleMemEngine

    engine = SimpleMemEngine(namespace="demo", user_id="demo_user")

    # First extract some memories
    dialogues = [
        ("Alice", "I work as a software engineer at Google."),
        ("Bob", "What programming languages do you use?"),
        ("Alice", "I mainly use Python and TypeScript."),
        ("Bob", "That's cool! I use Java and Kotlin."),
        ("Alice", "My favorite IDE is VS Code."),
    ]

    for speaker, content in dialogues:
        engine.add_dialogue(
            speaker=speaker,
            content=content,
            auto_process=False,
        )

    engine.process_remaining()

    # Search queries
    queries = [
        "What is Alice's profession?",
        "programming languages",
        "IDE",
    ]

    for query in queries:
        print(f"\n--- Query: '{query}' ---")

        # Semantic search
        results = engine.search(query, search_mode="semantic", top_k=3)
        print(f"Semantic results ({len(results)}):")
        for r in results:
            print(f"  - {r.lossless_restatement[:80]}...")

        # Keyword search
        results = engine.search(query, search_mode="keyword", top_k=3)
        print(f"Keyword results ({len(results)}):")
        for r in results:
            print(f"  - {r.lossless_restatement[:80]}...")


def demo_hybrid_retrieval():
    """Demo 3: Hybrid retrieval with reflection."""
    print("\n" + "=" * 60)
    print("Demo 3: Hybrid Retrieval with Reflection")
    print("=" * 60)

    from agent_memory_server.engines.simplemem import SimpleMemEngine

    engine = SimpleMemEngine(
        namespace="demo",
        user_id="demo_user",
        enable_planning=True,
        enable_reflection=True,
        max_reflection_rounds=2,
    )

    # Extract memories about a meeting
    dialogues = [
        ("Alice", "Let's schedule a team meeting for next week."),
        ("Bob", "Sure, how about Tuesday at 2pm?"),
        ("Alice", "Tuesday works. Let's do it in Conference Room A."),
        ("Bob", "I'll send out the calendar invite."),
        ("Alice", "Thanks! Please include the agenda in the invite."),
    ]

    for speaker, content in dialogues:
        engine.add_dialogue(speaker=speaker, content=content, auto_process=False)

    engine.process_remaining()

    # Complex query that benefits from reflection
    query = "When and where is the meeting?"

    print(f"\nQuery: '{query}'")
    print("\nUsing hybrid retrieval with reflection...")

    results = engine.retrieve(query)

    print(f"\nRetrieved {len(results)} memories:")
    for i, r in enumerate(results, 1):
        print(f"\n  [{i}] {r.lossless_restatement}")
        print(f"      Topic: {r.topic}")
        print(f"      Keywords: {r.keywords}")


def demo_answer_generation():
    """Demo 4: Generate answer from retrieved context."""
    print("\n" + "=" * 60)
    print("Demo 4: Answer Generation")
    print("=" * 60)

    from agent_memory_server.engines.simplemem import SimpleMemEngine

    engine = SimpleMemEngine(namespace="demo", user_id="demo_user")

    dialogues = [
        ("Alice", "I'm planning to buy a new laptop."),
        ("Bob", "What are you looking for in a laptop?"),
        ("Alice", "I need something with at least 16GB RAM, good battery life."),
        ("Bob", "Have you considered the MacBook Pro? It has great battery."),
        ("Alice", "Yes, I'm also looking at Dell XPS and ThinkPad."),
        ("Bob", "All good choices. The ThinkPad is great for developers."),
    ]

    for speaker, content in dialogues:
        engine.add_dialogue(speaker=speaker, content=content, auto_process=False)

    engine.process_remaining()

    queries = [
        "What are Alice's laptop requirements?",
        "What laptops is Alice considering?",
    ]

    for query in queries:
        print(f"\n--- Query: '{query}' ---")

        # Generate answer
        answer = engine.generate_answer(query)

        print(f"Answer: {answer}")


async def demo_native_integration():
    """Demo 5: Native agent-memory-server integration."""
    print("\n" + "=" * 60)
    print("Demo 5: Native Agent-Memory-Server Integration")
    print("=" * 60)

    from agent_memory_server.engines.simplemem import SimpleMemEngine

    engine = SimpleMemEngine(namespace="demo", user_id="demo_user")

    # Add a memory using native method
    print("\nAdding memory via native method...")
    memory_id = await engine.add_memory_native(
        text="User prefers dark mode in IDE settings",
        topics=["preference", "IDE", "dark mode"],
        entities=[],
    )
    print(f"Created memory with ID: {memory_id}")

    # Search using native method
    print("\nSearching via native method...")
    results = await engine.search_native(
        query="dark mode preference",
        search_mode="semantic",
        limit=5,
    )

    print(f"Found {len(results.memories)} native memories:")
    for r in results.memories:
        print(f"  - {r.text[:60]}...")


def demo_parallel_processing():
    """Demo 6: Parallel processing for large dialogue sets."""
    print("\n" + "=" * 60)
    print("Demo 6: Parallel Processing")
    print("=" * 60)

    from agent_memory_server.engines.simplemem import SimpleMemEngine

    engine = SimpleMemEngine(
        namespace="demo",
        user_id="demo_user",
        enable_parallel_processing=True,
        max_parallel_workers=3,
    )

    # Simulate a large conversation
    dialogues = []
    for i in range(50):
        dialogues.append(
            (
                "User",
                f"I like to eat {['pizza', 'sushi', 'pasta', 'salad'][i % 4]} on {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'][i % 5]}.",
            )
        )

    print(f"\nAdding {len(dialogues)} dialogues...")

    for speaker, content in dialogues:
        engine.add_dialogue(speaker=speaker, content=content, auto_process=False)

    print("Processing with parallel workers...")
    engine.process_remaining()

    print(f"\nProcessed {engine.memory_builder.processed_count} dialogues")


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("SimpleMem Engine Demo")
    print("=" * 60)

    demos = [
        ("Basic Extraction", demo_basic_extraction),
        ("Search", demo_search),
        ("Hybrid Retrieval", demo_hybrid_retrieval),
        ("Answer Generation", demo_answer_generation),
        ("Parallel Processing", demo_parallel_processing),
    ]

    for name, demo_func in demos:
        try:
            demo_func()
        except Exception as e:
            logger.error(f"Demo '{name}' failed: {e}", exc_info=True)
            print(f"\nError in {name}: {e}")

    # Run async demo separately
    try:
        asyncio.run(demo_native_integration())
    except Exception as e:
        logger.error(f"Demo 'Native Integration' failed: {e}", exc_info=True)
        print(f"\nError in Native Integration: {e}")

    print("\n" + "=" * 60)
    print("All demos completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
