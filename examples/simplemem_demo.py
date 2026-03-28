#!/usr/bin/env python3
"""
SimpleMem Demo - Matches SimpleMem/demo-simple.py interface

Usage:
    python examples/simplemem_demo.py

Environment:
    - Configure via simplemem_config.yaml
"""

import os
import sys

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "simplemem_config.yaml")

if os.path.exists(CONFIG_FILE):
    import yaml

    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)

    env_mapping = {
        "openai_api_base": "OPENAI_API_BASE",
        "openai_api_key": "OPENAI_API_KEY",
        "generation_model": "GENERATION_MODEL",
        "embedding_model": "EMBEDDING_MODEL",
        "redis_url": "REDIS_URL",
        "disable_auth": "DISABLE_AUTH",
    }

    for key, value in config.items():
        if key in env_mapping:
            os.environ[env_mapping[key]] = str(value)
        elif key.startswith("redisvl_"):
            os.environ[key.upper()] = str(value)

    print(f"Loaded config from: {CONFIG_FILE}")
else:
    print(f"Warning: Config file not found: {CONFIG_FILE}")


def main():
    from agent_memory_server.engines.simplemem import SimpleMemEngine

    print("=" * 60)
    print("SimpleMem Engine Demo")
    print("=" * 60)

    print("\nInitializing system...")
    system = SimpleMemEngine(namespace="demo", user_id="demo_user")

    print("\nAdding dialogues (Stage 1: Semantic Structured Compression)...")
    system.add_dialogue(
        "Alice", "Bob，我们明天下午2点在星巴克见面吧", "2025-11-15T14:30:00"
    )
    print("Memory added: Bob，我们明天下午2点在星巴克见面吧")

    system.add_dialogue(
        "Bob", "不行，我明天有事情，你觉得后天上午10点怎么样？", "2025-11-15T14:31:00"
    )
    print("Memory added: 不行，我明天有事情，你觉得后天上午10点怎么样？")

    system.add_dialogue(
        "Alice", "我看下，后天我要去运动，要不后天上午9点如何？", "2025-11-15T14:32:00"
    )
    print("Memory added: 我看下，后天我要去运动，要不后天上午9点如何？")

    system.add_dialogue("Bob", "好的，我会带上市场分析报告", "2025-11-15T14:33:00")
    print("Memory added: 好的，我会带上市场分析报告")

    print("\nFinalizing (Stage 2: Online Semantic Synthesis)...")
    system.finalize()

    print("\nIntent-Aware Retrieval (Stage 3: Intent-Aware Retrieval Planning)...")
    answer = system.ask("Alice 和 Bob 什么时候在哪里见面？")
    print(answer)


if __name__ == "__main__":
    main()
