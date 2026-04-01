#!/usr/bin/env python3
"""
CLI for Redis Agent Memory Server operations.

Usage examples:
    # Working memory operations
    python scripts/cli_memory.py add-message --session-id "my-session" --role "user" --content "Hello"
    python scripts/cli_memory.py get-session --session-id "my-session"
    python scripts/cli_memory.py list-sessions
    python scripts/cli_memory.py delete-session --session-id "my-session"

    # Long-term memory operations
    python scripts/cli_memory.py create-memory --id "mem-001" --text "User prefers dark mode"
    python scripts/cli_memory.py search --query "user preferences"
    python scripts/cli_memory.py get-memory --memory-id "mem-001"
    python scripts/cli_memory.py update-memory --memory-id "mem-001" --text "Updated"
    python scripts/cli_memory.py delete-memories --memory-ids "mem-001" "mem-002"

    # Memory prompt
    python scripts/cli_memory.py memory-prompt --query "What did we discuss?" --session-id "my-session"

    # Summary views
    python scripts/cli_memory.py create-summary-view --name "my-view" --source "long_term" --group-by "user_id"
    python scripts/cli_memory.py list-summary-views
    python scripts/cli_memory.py run-summary-view --view-id "view-001"

    # Tasks
    python scripts/cli_memory.py get-task --task-id "task-001"

The script performs a single operation per invocation and exits.
Configuration via environment variables or config.py file.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.abspath(os.path.join(script_dir, ".."))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

# Try to import config from skill directory
try:
    from config import settings as config_settings
except ImportError:
    config_settings = None


# -----------------------------
# Configuration
# -----------------------------


class Settings:
    """Settings class that reads from environment or config file."""

    def __init__(self):
        # Base URL for the agent memory server
        self.base_url = os.environ.get("AGENT_MEMORY_BASE_URL", "http://localhost:8000")
        # API key for authentication
        self.api_key = os.environ.get("AGENT_MEMORY_API_KEY", None)
        # Request timeout in seconds
        self.timeout = int(os.environ.get("AGENT_MEMORY_TIMEOUT", "30"))
        # Disable auth for development
        self.disable_auth = os.environ.get("DISABLE_AUTH", "true").lower() == "true"

    def get_headers(self) -> dict:
        """Get headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


# Global settings instance
settings = Settings()


# -----------------------------
# HTTP Client
# -----------------------------


def make_request(
    method: str,
    path: str,
    data: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Make an HTTP request to the agent memory server."""
    import requests

    url = f"{settings.base_url}{path}"
    headers = settings.get_headers()

    try:
        if method.upper() == "GET":
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=settings.timeout,
            )
        elif method.upper() == "POST":
            response = requests.post(
                url,
                headers=headers,
                json=data,
                params=params,
                timeout=settings.timeout,
            )
        elif method.upper() == "PUT":
            response = requests.put(
                url,
                headers=headers,
                json=data,
                params=params,
                timeout=settings.timeout,
            )
        elif method.upper() == "PATCH":
            response = requests.patch(
                url,
                headers=headers,
                json=data,
                params=params,
                timeout=settings.timeout,
            )
        elif method.upper() == "DELETE":
            response = requests.delete(
                url,
                headers=headers,
                params=params,
                timeout=settings.timeout,
            )
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to make request to {url}: {e}")
        sys.exit(1)


# -----------------------------
# Working Memory Commands
# -----------------------------


def cmd_add_message(args):
    """Add a message to working memory."""
    from ulid import ULID

    message = {
        "role": args.role,
        "content": args.content,
        "id": str(ULID()),
    }

    # If created_at provided, add it
    if args.created_at:
        message["created_at"] = args.created_at

    payload = {
        "messages": [message],
    }

    if args.user_id:
        payload["user_id"] = args.user_id
    if args.namespace:
        payload["namespace"] = args.namespace

    result = make_request(
        "PUT",
        f"/v1/working-memory/{args.session_id}",
        data=payload,
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_set_working_memory(args):
    """Set working memory with messages and memories."""
    messages = json.loads(args.messages) if args.messages else []

    payload = {"messages": messages}

    if args.user_id:
        payload["user_id"] = args.user_id
    if args.namespace:
        payload["namespace"] = args.namespace

    result = make_request(
        "PUT",
        f"/v1/working-memory/{args.session_id}",
        data=payload,
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_get_session(args):
    """Get working memory for a session."""
    params = {}
    if args.user_id:
        params["user_id"] = args.user_id
    if args.namespace:
        params["namespace"] = args.namespace
    if args.model_name:
        params["model_name"] = args.model_name
    if args.context_window_max:
        params["context_window_max"] = str(args.context_window_max)
    if args.recent_messages_limit:
        params["recent_messages_limit"] = str(args.recent_messages_limit)

    result = make_request(
        "GET",
        f"/v1/working-memory/{args.session_id}",
        params=params if params else None,
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_delete_session(args):
    result = make_request(
        "DELETE",
        f"/v1/working-memory/{args.session_id}",
    )

    print(json.dumps(result, indent=2))


def cmd_list_sessions(args):
    """List all sessions."""
    params = {}
    if args.limit:
        params["limit"] = str(args.limit)
    if args.offset:
        params["offset"] = str(args.offset)
    if args.namespace:
        params["namespace"] = args.namespace
    if args.user_id:
        params["user_id"] = args.user_id

    result = make_request(
        "GET",
        "/v1/working-memory/",
        params=params if params else None,
    )

    print(json.dumps(result, indent=2, default=str))


# -----------------------------
# Long-term Memory Commands
# -----------------------------


def cmd_create_memory(args):
    """Create a long-term memory."""
    memory = {
        "id": args.id,
        "text": args.text,
    }

    if args.memory_type:
        memory["memory_type"] = args.memory_type
    if args.event_date:
        memory["event_date"] = args.event_date
    if args.topics:
        memory["topics"] = (
            args.topics.split(",") if isinstance(args.topics, str) else args.topics
        )
    if args.entities:
        memory["entities"] = (
            args.entities.split(",")
            if isinstance(args.entities, str)
            else args.entities
        )
    if args.namespace:
        memory["namespace"] = args.namespace
    if args.user_id:
        memory["user_id"] = args.user_id
    if args.session_id:
        memory["session_id"] = args.session_id
    if args.pinned:
        memory["pinned"] = args.pinned

    payload = {
        "memories": [memory],
        "deduplicate": not args.no_deduplicate,
    }

    result = make_request(
        "POST",
        "/v1/long-term-memory/",
        data=payload,
    )

    print(json.dumps(result, indent=2))


def cmd_search(args):
    """Search long-term memories."""
    payload = {
        "text": args.query,
        "limit": args.limit or 10,
    }

    if args.search_mode:
        payload["search_mode"] = args.search_mode
    if args.hybrid_alpha:
        payload["hybrid_alpha"] = args.hybrid_alpha
    if args.namespace:
        payload["namespace"] = {"eq": args.namespace}
    if args.user_id:
        payload["user_id"] = {"eq": args.user_id}
    if args.session_id:
        payload["session_id"] = {"eq": args.session_id}
    if args.memory_type:
        payload["memory_type"] = {"eq": args.memory_type}
    if args.topics:
        payload["topics"] = {
            "any": args.topics.split(",")
            if isinstance(args.topics, str)
            else args.topics
        }
    if args.entities:
        payload["entities"] = {
            "any": args.entities.split(",")
            if isinstance(args.entities, str)
            else args.entities
        }
    if args.distance_threshold:
        payload["distance_threshold"] = args.distance_threshold
    if args.offset:
        payload["offset"] = args.offset

    # Recency params
    if args.recency_boost is not None:
        payload["recency_boost"] = args.recency_boost

    result = make_request(
        "POST",
        "/v1/long-term-memory/search",
        data=payload,
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_get_memory(args):
    """Get a long-term memory by ID."""
    result = make_request(
        "GET",
        f"/v1/long-term-memory/{args.memory_id}",
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_update_memory(args):
    """Update a long-term memory."""
    updates = {}

    if args.text is not None:
        updates["text"] = args.text
    if args.topics is not None:
        updates["topics"] = (
            args.topics.split(",") if isinstance(args.topics, str) else args.topics
        )
    if args.entities is not None:
        updates["entities"] = (
            args.entities.split(",")
            if isinstance(args.entities, str)
            else args.entities
        )
    if args.memory_type is not None:
        updates["memory_type"] = args.memory_type
    if args.namespace is not None:
        updates["namespace"] = args.namespace
    if args.user_id is not None:
        updates["user_id"] = args.user_id
    if args.session_id is not None:
        updates["session_id"] = args.session_id
    if args.event_date is not None:
        updates["event_date"] = args.event_date
    if args.pinned is not None:
        updates["pinned"] = args.pinned

    result = make_request(
        "PATCH",
        f"/v1/long-term-memory/{args.memory_id}",
        data=updates,
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_delete_memories(args):
    """Delete long-term memories by IDs."""
    memory_ids = (
        args.memory_ids.split(",")
        if isinstance(args.memory_ids, str)
        else args.memory_ids
    )

    result = make_request(
        "DELETE",
        "/v1/long-term-memory",
        params={"memory_ids": memory_ids},
    )

    print(json.dumps(result, indent=2))


def cmd_compact_memories(args):
    """Compact long-term memories."""
    params = {}
    if args.namespace:
        params["namespace"] = args.namespace
    if args.user_id:
        params["user_id"] = args.user_id

    result = make_request(
        "POST",
        "/v1/long-term-memory/compact",
        params=params if params else None,
    )

    print(json.dumps(result, indent=2))


# -----------------------------
# Memory Prompt Commands
# -----------------------------


def cmd_memory_prompt(args):
    """Get memory context for a query."""
    payload = {
        "query": args.query,
    }

    if args.session_id:
        session_payload = {}
        if args.user_id:
            session_payload["user_id"] = args.user_id
        if args.namespace:
            session_payload["namespace"] = args.namespace
        session_payload["session_id"] = args.session_id
        if args.model_name:
            session_payload["model_name"] = args.model_name
        if args.context_window_max:
            session_payload["context_window_max"] = args.context_window_max
        payload["session"] = session_payload

    if args.long_term_search:
        # If True, use default search
        if args.long_term_search is True:
            payload["long_term_search"] = True
        else:
            # Parse as JSON
            payload["long_term_search"] = json.loads(args.long_term_search)

    result = make_request(
        "POST",
        "/v1/memory/prompt",
        data=payload,
    )

    print(json.dumps(result, indent=2, default=str))


# -----------------------------
# Summary View Commands
# -----------------------------


def cmd_create_summary_view(args):
    """Create a summary view."""
    payload = {
        "source": args.source,
        "group_by": args.group_by.split(",")
        if isinstance(args.group_by, str)
        else args.group_by,
    }

    if args.name:
        payload["name"] = args.name
    if args.filters:
        payload["filters"] = (
            json.loads(args.filters) if isinstance(args.filters, str) else args.filters
        )
    if args.time_window_days:
        payload["time_window_days"] = args.time_window_days
    if args.continuous:
        payload["continuous"] = args.continuous
    if args.prompt:
        payload["prompt"] = args.prompt
    if args.model_name:
        payload["model_name"] = args.model_name

    result = make_request(
        "POST",
        "/v1/summary-views",
        data=payload,
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_list_summary_views(args):
    """List all summary views."""
    result = make_request(
        "GET",
        "/v1/summary-views",
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_get_summary_view(args):
    """Get a summary view by ID."""
    result = make_request(
        "GET",
        f"/v1/summary-views/{args.view_id}",
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_delete_summary_view(args):
    """Delete a summary view."""
    result = make_request(
        "DELETE",
        f"/v1/summary-views/{args.view_id}",
    )

    print(json.dumps(result, indent=2))


def cmd_run_summary_view(args):
    """Run a summary view."""
    payload = {}
    if args.task_id:
        payload["task_id"] = args.task_id

    result = make_request(
        "POST",
        f"/v1/summary-views/{args.view_id}/run",
        data=payload,
    )

    print(json.dumps(result, indent=2, default=str))


def cmd_get_summary_view_partitions(args):
    """Get summary view partitions."""
    params = {}
    if args.user_id:
        params["user_id"] = args.user_id
    if args.namespace:
        params["namespace"] = args.namespace
    if args.session_id:
        params["session_id"] = args.session_id
    if args.memory_type:
        params["memory_type"] = args.memory_type

    result = make_request(
        "GET",
        f"/v1/summary-views/{args.view_id}/partitions",
        params=params if params else None,
    )

    print(json.dumps(result, indent=2, default=str))


# -----------------------------
# Task Commands
# -----------------------------


def cmd_get_task(args):
    """Get task status."""
    result = make_request(
        "GET",
        f"/v1/tasks/{args.task_id}",
    )

    print(json.dumps(result, indent=2, default=str))


# -----------------------------
# Main
# -----------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Redis Agent Memory CLI - Manage persistent AI agent memory"
    )

    # Global options
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override base URL for the server",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Override API key for authentication",
    )

    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # -----------------------------
    # Working Memory Commands
    # -----------------------------

    # add-message
    p_add_msg = subparsers.add_parser(
        "add-message",
        help="Add a message to working memory",
        description="Add a message to an existing working memory session",
    )
    p_add_msg.add_argument("--session-id", required=True, help="Session ID")
    p_add_msg.add_argument(
        "--role",
        required=True,
        choices=["user", "assistant", "system"],
        help="Message role",
    )
    p_add_msg.add_argument("--content", required=True, help="Message content")
    p_add_msg.add_argument("--user-id", default=None, help="User ID")
    p_add_msg.add_argument("--namespace", default=None, help="Namespace")
    p_add_msg.add_argument("--created-at", default=None, help="ISO 8601 timestamp")
    p_add_msg.set_defaults(func=cmd_add_message)

    # set-working-memory
    p_set_wm = subparsers.add_parser(
        "set-working-memory",
        help="Set working memory with messages",
        description="Set entire working memory for a session",
    )
    p_set_wm.add_argument("--session-id", required=True, help="Session ID")
    p_set_wm.add_argument("--messages", default="[]", help="JSON array of messages")
    p_set_wm.add_argument("--user-id", default=None, help="User ID")
    p_set_wm.add_argument("--namespace", default=None, help="Namespace")
    p_set_wm.set_defaults(func=cmd_set_working_memory)

    # get-session
    p_get_sess = subparsers.add_parser(
        "get-session",
        help="Get working memory for a session",
        description="Retrieve working memory including messages and context",
    )
    p_get_sess.add_argument("--session-id", required=True, help="Session ID")
    p_get_sess.add_argument("--user-id", default=None, help="User ID")
    p_get_sess.add_argument("--namespace", default=None, help="Namespace")
    p_get_sess.add_argument(
        "--model-name", default=None, help="LLM model name for context window"
    )
    p_get_sess.add_argument(
        "--context-window-max", type=int, default=None, help="Max context tokens"
    )
    p_get_sess.add_argument(
        "--recent-messages-limit", type=int, default=None, help="Limit recent messages"
    )
    p_get_sess.set_defaults(func=cmd_get_session)

    # delete-session
    p_del_sess = subparsers.add_parser(
        "delete-session",
        help="Delete working memory for a session",
        description="Delete all working memory data for a session",
    )
    p_del_sess.add_argument("--session-id", required=True, help="Session ID")
    p_del_sess.add_argument("--user-id", default=None, help="User ID")
    p_del_sess.add_argument("--namespace", default=None, help="Namespace")
    p_del_sess.set_defaults(func=cmd_delete_session)

    # list-sessions
    p_list_sess = subparsers.add_parser(
        "list-sessions",
        help="List all sessions",
        description="List all session IDs with optional filtering",
    )
    p_list_sess.add_argument("--limit", type=int, default=20, help="Limit results")
    p_list_sess.add_argument("--offset", type=int, default=0, help="Offset")
    p_list_sess.add_argument("--namespace", default=None, help="Filter by namespace")
    p_list_sess.add_argument("--user-id", default=None, help="Filter by user ID")
    p_list_sess.set_defaults(func=cmd_list_sessions)

    # -----------------------------
    # Long-term Memory Commands
    # -----------------------------

    # create-memory
    p_create_mem = subparsers.add_parser(
        "create-memory",
        help="Create a long-term memory",
        description="Create a persistent memory record",
    )
    p_create_mem.add_argument("--id", required=True, help="Memory ID")
    p_create_mem.add_argument("--text", required=True, help="Memory text content")
    p_create_mem.add_argument(
        "--memory-type",
        default=None,
        choices=["semantic", "episodic", "message"],
        help="Memory type",
    )
    p_create_mem.add_argument(
        "--event-date", default=None, help="Event date (ISO 8601)"
    )
    p_create_mem.add_argument("--topics", default=None, help="Comma-separated topics")
    p_create_mem.add_argument(
        "--entities", default=None, help="Comma-separated entities"
    )
    p_create_mem.add_argument("--namespace", default=None, help="Namespace")
    p_create_mem.add_argument("--user-id", default=None, help="User ID")
    p_create_mem.add_argument("--session-id", default=None, help="Session ID")
    p_create_mem.add_argument("--pinned", action="store_true", help="Pin memory")
    p_create_mem.add_argument(
        "--no-deduplicate", action="store_true", help="Disable deduplication"
    )
    p_create_mem.set_defaults(func=cmd_create_memory)

    # search
    p_search = subparsers.add_parser(
        "search",
        help="Search long-term memories",
        description="Semantic, keyword, or hybrid search",
    )
    p_search.add_argument("--query", required=True, help="Search query text")
    p_search.add_argument(
        "--search-mode",
        default="semantic",
        choices=["semantic", "keyword", "hybrid"],
        help="Search mode",
    )
    p_search.add_argument(
        "--hybrid-alpha", type=float, default=0.7, help="Hybrid alpha weight"
    )
    p_search.add_argument("--limit", type=int, default=10, help="Result limit")
    p_search.add_argument("--offset", type=int, default=0, help="Result offset")
    p_search.add_argument("--namespace", default=None, help="Filter by namespace")
    p_search.add_argument("--user-id", default=None, help="Filter by user ID")
    p_search.add_argument("--session-id", default=None, help="Filter by session ID")
    p_search.add_argument("--memory-type", default=None, help="Filter by memory type")
    p_search.add_argument(
        "--topics", default=None, help="Filter by topics (comma-separated)"
    )
    p_search.add_argument(
        "--entities", default=None, help="Filter by entities (comma-separated)"
    )
    p_search.add_argument(
        "--distance-threshold",
        type=float,
        default=None,
        help="Semantic distance threshold",
    )
    p_search.add_argument(
        "--recency-boost", action="store_true", help="Enable recency boost"
    )
    p_search.set_defaults(func=cmd_search)

    # get-memory
    p_get_mem = subparsers.add_parser(
        "get-memory",
        help="Get a long-term memory by ID",
        description="Retrieve a specific memory record",
    )
    p_get_mem.add_argument("--memory-id", required=True, help="Memory ID")
    p_get_mem.set_defaults(func=cmd_get_memory)

    # update-memory
    p_upd_mem = subparsers.add_parser(
        "update-memory",
        help="Update a long-term memory",
        description="Update memory fields",
    )
    p_upd_mem.add_argument("--memory-id", required=True, help="Memory ID")
    p_upd_mem.add_argument("--text", default=None, help="Updated text")
    p_upd_mem.add_argument(
        "--topics", default=None, help="Updated topics (comma-separated)"
    )
    p_upd_mem.add_argument(
        "--entities", default=None, help="Updated entities (comma-separated)"
    )
    p_upd_mem.add_argument("--memory-type", default=None, help="Updated memory type")
    p_upd_mem.add_argument("--namespace", default=None, help="Updated namespace")
    p_upd_mem.add_argument("--user-id", default=None, help="Updated user ID")
    p_upd_mem.add_argument("--session-id", default=None, help="Updated session ID")
    p_upd_mem.add_argument("--event-date", default=None, help="Updated event date")
    p_upd_mem.add_argument(
        "--pinned", default=None, action="store_true", help="Pin/unpin memory"
    )
    p_upd_mem.set_defaults(func=cmd_update_memory)

    # delete-memories
    p_del_mems = subparsers.add_parser(
        "delete-memories",
        help="Delete long-term memories",
        description="Delete memories by IDs",
    )
    p_del_mems.add_argument(
        "--memory-ids", required=True, help="Comma-separated memory IDs"
    )
    p_del_mems.set_defaults(func=cmd_delete_memories)

    # compact-memories
    p_compact = subparsers.add_parser(
        "compact-memories",
        help="Compact long-term memories",
        description="Merge duplicate memories",
    )
    p_compact.add_argument("--namespace", default=None, help="Filter by namespace")
    p_compact.add_argument("--user-id", default=None, help="Filter by user ID")
    p_compact.set_defaults(func=cmd_compact_memories)

    # -----------------------------
    # Memory Prompt Commands
    # -----------------------------

    # memory-prompt
    p_mem_prompt = subparsers.add_parser(
        "memory-prompt",
        help="Get memory context for a query",
        description="Hydrate a query with working memory and/or long-term memory context",
    )
    p_mem_prompt.add_argument("--query", required=True, help="Query text")
    p_mem_prompt.add_argument(
        "--session-id", default=None, help="Session ID for working memory"
    )
    p_mem_prompt.add_argument("--user-id", default=None, help="User ID")
    p_mem_prompt.add_argument("--namespace", default=None, help="Namespace")
    p_mem_prompt.add_argument("--model-name", default=None, help="LLM model name")
    p_mem_prompt.add_argument(
        "--context-window-max", type=int, default=None, help="Max context tokens"
    )
    p_mem_prompt.add_argument(
        "--long-term-search",
        nargs="?",
        default=False,
        const=True,
        help="Include long-term memory search",
    )
    p_mem_prompt.set_defaults(func=cmd_memory_prompt)

    # -----------------------------
    # Summary View Commands
    # -----------------------------

    # create-summary-view
    p_create_sv = subparsers.add_parser(
        "create-summary-view",
        help="Create a summary view",
        description="Create a configuration for summarizing memories",
    )
    p_create_sv.add_argument("--name", default=None, help="View name")
    p_create_sv.add_argument(
        "--source",
        required=True,
        choices=["long_term", "working_memory"],
        help="Memory source",
    )
    p_create_sv.add_argument(
        "--group-by", required=True, help="Comma-separated group by fields"
    )
    p_create_sv.add_argument("--filters", default=None, help="JSON object of filters")
    p_create_sv.add_argument(
        "--time-window-days", type=int, default=None, help="Time window in days"
    )
    p_create_sv.add_argument(
        "--continuous", action="store_true", help="Enable continuous refresh"
    )
    p_create_sv.add_argument(
        "--prompt", default=None, help="Custom summarization prompt"
    )
    p_create_sv.add_argument(
        "--model-name", default=None, help="Model for summarization"
    )
    p_create_sv.set_defaults(func=cmd_create_summary_view)

    # list-summary-views
    p_list_sv = subparsers.add_parser(
        "list-summary-views",
        help="List all summary views",
        description="List all registered summary views",
    )
    p_list_sv.set_defaults(func=cmd_list_summary_views)

    # get-summary-view
    p_get_sv = subparsers.add_parser(
        "get-summary-view",
        help="Get a summary view by ID",
        description="Get summary view configuration",
    )
    p_get_sv.add_argument("--view-id", required=True, help="View ID")
    p_get_sv.set_defaults(func=cmd_get_summary_view)

    # delete-summary-view
    p_del_sv = subparsers.add_parser(
        "delete-summary-view",
        help="Delete a summary view",
        description="Delete a summary view configuration",
    )
    p_del_sv.add_argument("--view-id", required=True, help="View ID")
    p_del_sv.set_defaults(func=cmd_delete_summary_view)

    # run-summary-view
    p_run_sv = subparsers.add_parser(
        "run-summary-view",
        help="Run a summary view",
        description="Trigger a full recompute of a summary view",
    )
    p_run_sv.add_argument("--view-id", required=True, help="View ID")
    p_run_sv.add_argument("--task-id", default=None, help="Custom task ID")
    p_run_sv.set_defaults(func=cmd_run_summary_view)

    # get-summary-view-partitions
    p_get_part = subparsers.add_parser(
        "get-summary-view-partitions",
        help="Get summary view partitions",
        description="List materialized partition summaries",
    )
    p_get_part.add_argument("--view-id", required=True, help="View ID")
    p_get_part.add_argument("--user-id", default=None, help="Filter by user ID")
    p_get_part.add_argument("--namespace", default=None, help="Filter by namespace")
    p_get_part.add_argument("--session-id", default=None, help="Filter by session ID")
    p_get_part.add_argument("--memory-type", default=None, help="Filter by memory type")
    p_get_part.set_defaults(func=cmd_get_summary_view_partitions)

    # -----------------------------
    # Task Commands
    # -----------------------------

    # get-task
    p_get_task = subparsers.add_parser(
        "get-task",
        help="Get task status",
        description="Get background task status",
    )
    p_get_task.add_argument("--task-id", required=True, help="Task ID")
    p_get_task.set_defaults(func=cmd_get_task)

    args = parser.parse_args()

    # Override settings from command line
    if args.base_url:
        settings.base_url = args.base_url
    if args.api_key:
        settings.api_key = args.api_key

    args.func(args)


if __name__ == "__main__":
    main()
