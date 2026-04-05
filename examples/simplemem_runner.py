#!/usr/bin/env python3
"""SimpleMem Demo Runner - Load config from YAML file."""

import argparse
import os
import sys

DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "..", "simplemem_config.yaml")


def load_config(config_file: str):
    if not os.path.exists(config_file):
        print(f"Config file not found: {config_file}")
        sys.exit(1)

    import yaml

    with open(config_file) as f:
        config = yaml.safe_load(f)

    for key, value in config.items():
        if key == "litellm_settings":
            continue
        os.environ[f"REDIS_MEMORY_{key.upper()}"] = str(value)
        if key == "openai_api_base":
            os.environ["OPENAI_API_BASE"] = str(value)
            # Also set for LiteLLM
            os.environ["OPENAI_BASE_URL"] = str(value)
        elif key == "openai_api_key":
            os.environ["OPENAI_API_KEY"] = str(value)
        elif key == "generation_model":
            os.environ["GENERATION_MODEL"] = str(value)
        elif key == "embedding_model":
            os.environ["EMBEDDING_MODEL"] = str(value)
        elif key == "redis_url":
            os.environ["REDIS_URL"] = str(value)
        elif key == "disable_auth":
            os.environ["DISABLE_AUTH"] = "true" if value else "false"
        elif key == "redisvl_vector_dimensions":
            os.environ["REDISVL_VECTOR_DIMENSIONS"] = str(value)
        elif key == "embedding_api_base":
            os.environ["EMBEDDING_API_BASE"] = str(value)

    # Configure LiteLLM - must be done before importing other modules
    os.environ["OPENAI_API_KEY"] = config.get("openai_api_key", "dummy")
    os.environ["LITELLM_DROP_PARAMS"] = "True"

    # Force LiteLLM to treat model as OpenAI-compatible
    import litellm

    litellm.drop_params = True

    # Monkey-patch to force OpenAI client for custom models
    original_get_llm_provider = litellm.utils.get_llm_provider

    def patched_get_llm_provider(model, **kwargs):
        # Check if model is one of our Docker Model Runner models
        if model in ["ai/qwen3-embedding:4B", "ai/qwen3:8B-Q4_0"]:
            return ("openai", "OpenAI", model, {})
        return original_get_llm_provider(model, **kwargs)

    litellm.utils.get_llm_provider = patched_get_llm_provider

    print(f"Loaded config from: {config_file}")
    print(f"  API Base: {config.get('openai_api_base')}")
    print(f"  Embedding API Base: {config.get('embedding_api_base')}")
    print(f"  Model: {config.get('generation_model')}")
    print(f"  Embedding: {config.get('embedding_model')}")
    print()


def main():
    parser = argparse.ArgumentParser(description="SimpleMem Demo Runner")
    parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG, help="Config file path"
    )
    args = parser.parse_args()

    load_config(args.config)

    from examples import simplemem_demo

    simplemem_demo.main()

    import litellm
    import asyncio

    try:
        asyncio.run(litellm.close_litellm_async_clients())
    except (AttributeError, RuntimeError):
        pass


if __name__ == "__main__":
    main()
