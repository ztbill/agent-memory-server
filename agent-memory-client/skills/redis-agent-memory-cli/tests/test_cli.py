import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

script_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.abspath(os.path.join(script_dir, ".."))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.env_vars = {
            "AGENT_MEMORY_BASE_URL": None,
            "AGENT_MEMORY_API_KEY": None,
            "AGENT_MEMORY_TIMEOUT": None,
            "DISABLE_AUTH": None,
        }
        for key, value in self.env_vars.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    def tearDown(self):
        for key in self.env_vars:
            if key in os.environ:
                del os.environ[key]

    def test_default_values(self):
        import importlib
        import scripts.cli_memory as cli

        importlib.reload(cli)

        settings = cli.Settings()
        self.assertEqual(settings.base_url, "http://localhost:8000")
        self.assertIsNone(settings.api_key)
        self.assertEqual(settings.timeout, 30)
        self.assertTrue(settings.disable_auth)

    def test_custom_base_url(self):
        os.environ["AGENT_MEMORY_BASE_URL"] = "http://custom:9000"
        import importlib
        import scripts.cli_memory as cli

        importlib.reload(cli)

        settings = cli.Settings()
        self.assertEqual(settings.base_url, "http://custom:9000")

    def test_custom_api_key(self):
        os.environ["AGENT_MEMORY_API_KEY"] = "test-key-123"
        import importlib
        import scripts.cli_memory as cli

        importlib.reload(cli)

        settings = cli.Settings()
        self.assertEqual(settings.api_key, "test-key-123")

    def test_custom_timeout(self):
        os.environ["AGENT_MEMORY_TIMEOUT"] = "60"
        import importlib
        import scripts.cli_memory as cli

        importlib.reload(cli)

        settings = cli.Settings()
        self.assertEqual(settings.timeout, 60)

    def test_disable_auth_false(self):
        os.environ["DISABLE_AUTH"] = "false"
        import importlib
        import scripts.cli_memory as cli

        importlib.reload(cli)

        settings = cli.Settings()
        self.assertFalse(settings.disable_auth)

    def test_get_headers_without_api_key(self):
        import importlib
        import scripts.cli_memory as cli

        importlib.reload(cli)

        settings = cli.Settings()
        headers = settings.get_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertNotIn("Authorization", headers)

    def test_get_headers_with_api_key(self):
        os.environ["AGENT_MEMORY_API_KEY"] = "secret-key"
        import importlib
        import scripts.cli_memory as cli

        importlib.reload(cli)

        settings = cli.Settings()
        headers = settings.get_headers()
        self.assertEqual(headers["Authorization"], "Bearer secret-key")


class TestHTTPClient(unittest.TestCase):
    def setUp(self):
        for key in [
            "AGENT_MEMORY_BASE_URL",
            "AGENT_MEMORY_API_KEY",
            "AGENT_MEMORY_TIMEOUT",
            "DISABLE_AUTH",
        ]:
            if key in os.environ:
                del os.environ[key]

    @patch("scripts.cli_memory.settings")
    def test_make_request_get(self, mock_settings):
        mock_response = MagicMock()
        mock_response.content = b'{"result": "success"}'
        mock_response.json.return_value = {"result": "success"}
        mock_response.raise_for_status = MagicMock()

        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_response

        mock_settings.base_url = "http://localhost:8000"
        mock_settings.timeout = 30
        mock_settings.get_headers.return_value = {"Content-Type": "application/json"}

        with patch.dict("sys.modules", {"requests": mock_requests}):
            import importlib
            import scripts.cli_memory as cli

            importlib.reload(cli)

            result = cli.make_request("GET", "/v1/health")

            self.assertEqual(result, {"result": "success"})
            mock_requests.get.assert_called_once()

    @patch("scripts.cli_memory.settings")
    def test_make_request_post(self, mock_settings):
        mock_response = MagicMock()
        mock_response.content = b'{"id": "123"}'
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        mock_requests = MagicMock()
        mock_requests.post.return_value = mock_response

        mock_settings.base_url = "http://localhost:8000"
        mock_settings.timeout = 30
        mock_settings.get_headers.return_value = {"Content-Type": "application/json"}

        with patch.dict("sys.modules", {"requests": mock_requests}):
            import importlib
            import scripts.cli_memory as cli

            importlib.reload(cli)

            result = cli.make_request(
                "POST",
                "/v1/working-memory/session-1",
                data={"messages": [{"role": "user", "content": "hello"}]},
            )

            self.assertEqual(result, {"id": "123"})
            mock_requests.post.assert_called_once()

    @patch("scripts.cli_memory.settings")
    def test_make_request_put(self, mock_settings):
        mock_response = MagicMock()
        mock_response.content = b'{"ok": true}'
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        mock_requests = MagicMock()
        mock_requests.put.return_value = mock_response

        mock_settings.base_url = "http://localhost:8000"
        mock_settings.timeout = 30
        mock_settings.get_headers.return_value = {"Content-Type": "application/json"}

        with patch.dict("sys.modules", {"requests": mock_requests}):
            import importlib
            import scripts.cli_memory as cli

            importlib.reload(cli)

            result = cli.make_request(
                "PUT",
                "/v1/long-term-memory/mem-1",
                data={"text": "Updated text"},
            )

            self.assertEqual(result, {"ok": True})

    @patch("scripts.cli_memory.settings")
    def test_make_request_delete(self, mock_settings):
        mock_response = MagicMock()
        mock_response.content = b'{"deleted": true}'
        mock_response.json.return_value = {"deleted": True}
        mock_response.raise_for_status = MagicMock()

        mock_requests = MagicMock()
        mock_requests.delete.return_value = mock_response

        mock_settings.base_url = "http://localhost:8000"
        mock_settings.timeout = 30
        mock_settings.get_headers.return_value = {"Content-Type": "application/json"}

        with patch.dict("sys.modules", {"requests": mock_requests}):
            import importlib
            import scripts.cli_memory as cli

            importlib.reload(cli)

            result = cli.make_request("DELETE", "/v1/working-memory/session-1")

            self.assertEqual(result, {"deleted": True})

    @patch("scripts.cli_memory.settings")
    def test_make_request_empty_response(self, mock_settings):
        mock_response = MagicMock()
        mock_response.content = b""
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_response

        mock_settings.base_url = "http://localhost:8000"
        mock_settings.timeout = 30
        mock_settings.get_headers.return_value = {"Content-Type": "application/json"}

        with patch.dict("sys.modules", {"requests": mock_requests}):
            import importlib
            import scripts.cli_memory as cli

            importlib.reload(cli)

            result = cli.make_request("GET", "/v1/health")

            self.assertEqual(result, {})


class TestWorkingMemoryCommands(unittest.TestCase):
    def setUp(self):
        for key in [
            "AGENT_MEMORY_BASE_URL",
            "AGENT_MEMORY_API_KEY",
            "AGENT_MEMORY_TIMEOUT",
            "DISABLE_AUTH",
        ]:
            if key in os.environ:
                del os.environ[key]

    @patch("scripts.cli_memory.make_request")
    def test_cmd_add_message(self, mock_request):
        mock_request.return_value = {"session_id": "session-1", "messages": []}

        import scripts.cli_memory as cli

        args = Mock()
        args.session_id = "session-1"
        args.role = "user"
        args.content = "Hello world"
        args.user_id = None
        args.namespace = None
        args.created_at = None

        cli.cmd_add_message(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "PUT")
        self.assertEqual(call_args[0][1], "/v1/working-memory/session-1")

    @patch("scripts.cli_memory.make_request")
    def test_cmd_get_session(self, mock_request):
        mock_request.return_value = {
            "session_id": "session-1",
            "messages": [{"role": "user", "content": "hi"}],
        }

        import scripts.cli_memory as cli

        args = Mock()
        args.session_id = "session-1"
        args.user_id = None
        args.namespace = None
        args.model_name = None
        args.context_window_max = None
        args.recent_messages_limit = None

        cli.cmd_get_session(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "GET")
        self.assertEqual(call_args[0][1], "/v1/working-memory/session-1")

    @patch("scripts.cli_memory.make_request")
    def test_cmd_list_sessions(self, mock_request):
        mock_request.return_value = {"sessions": ["s1", "s2"]}

        import scripts.cli_memory as cli

        args = Mock()
        args.limit = 10
        args.offset = 0
        args.namespace = None
        args.user_id = None

        cli.cmd_list_sessions(args)

        mock_request.assert_called_once()

    @patch("scripts.cli_memory.make_request")
    def test_cmd_delete_session(self, mock_request):
        mock_request.return_value = {"deleted": True}

        import scripts.cli_memory as cli

        args = Mock()
        args.session_id = "session-1"
        args.user_id = None
        args.namespace = None

        cli.cmd_delete_session(args)

        mock_request.assert_called_once()


class TestLongTermMemoryCommands(unittest.TestCase):
    def setUp(self):
        for key in [
            "AGENT_MEMORY_BASE_URL",
            "AGENT_MEMORY_API_KEY",
            "AGENT_MEMORY_TIMEOUT",
            "DISABLE_AUTH",
        ]:
            if key in os.environ:
                del os.environ[key]

    @patch("scripts.cli_memory.make_request")
    def test_cmd_create_memory(self, mock_request):
        mock_request.return_value = {"created": ["mem-1"]}

        import scripts.cli_memory as cli

        args = Mock()
        args.id = "mem-1"
        args.text = "User prefers dark mode"
        args.memory_type = "semantic"
        args.event_date = None
        args.topics = "preferences,ui"
        args.entities = None
        args.namespace = None
        args.user_id = "user-1"
        args.session_id = None
        args.pinned = False
        args.no_deduplicate = False

        cli.cmd_create_memory(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertEqual(call_args[0][1], "/v1/long-term-memory/")

    @patch("scripts.cli_memory.make_request")
    def test_cmd_search(self, mock_request):
        mock_request.return_value = {"memories": [], "total": 0}

        import scripts.cli_memory as cli

        args = Mock()
        args.query = "user preferences"
        args.search_mode = "semantic"
        args.hybrid_alpha = 0.7
        args.limit = 10
        args.offset = 0
        args.namespace = None
        args.user_id = None
        args.session_id = None
        args.memory_type = None
        args.topics = None
        args.entities = None
        args.distance_threshold = None
        args.recency_boost = None

        cli.cmd_search(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertEqual(call_args[0][1], "/v1/long-term-memory/search")
        payload = call_args[1]["data"]
        self.assertEqual(payload["text"], "user preferences")
        self.assertEqual(payload["limit"], 10)

    @patch("scripts.cli_memory.make_request")
    def test_cmd_get_memory(self, mock_request):
        mock_request.return_value = {"id": "mem-1", "text": "test"}

        import scripts.cli_memory as cli

        args = Mock()
        args.memory_id = "mem-1"

        cli.cmd_get_memory(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][1], "/v1/long-term-memory/mem-1")

    @patch("scripts.cli_memory.make_request")
    def test_cmd_update_memory(self, mock_request):
        mock_request.return_value = {"updated": True}

        import scripts.cli_memory as cli

        args = Mock()
        args.memory_id = "mem-1"
        args.text = "Updated text"
        args.topics = None
        args.entities = None
        args.memory_type = None
        args.namespace = None
        args.user_id = None
        args.session_id = None
        args.event_date = None
        args.pinned = None

        cli.cmd_update_memory(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "PATCH")
        self.assertEqual(call_args[0][1], "/v1/long-term-memory/mem-1")

    @patch("scripts.cli_memory.make_request")
    def test_cmd_delete_memories(self, mock_request):
        mock_request.return_value = {"deleted": 2}

        import scripts.cli_memory as cli

        args = Mock()
        args.memory_ids = "mem-1,mem-2"

        cli.cmd_delete_memories(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "DELETE")
        self.assertEqual(call_args[1]["params"]["memory_ids"], ["mem-1", "mem-2"])


class TestMemoryPromptCommands(unittest.TestCase):
    def setUp(self):
        for key in [
            "AGENT_MEMORY_BASE_URL",
            "AGENT_MEMORY_API_KEY",
            "AGENT_MEMORY_TIMEOUT",
            "DISABLE_AUTH",
        ]:
            if key in os.environ:
                del os.environ[key]

    @patch("scripts.cli_memory.make_request")
    def test_cmd_memory_prompt_basic(self, mock_request):
        mock_request.return_value = {"prompt": "Context: ...", "query": "test?"}

        import scripts.cli_memory as cli

        args = Mock()
        args.query = "What did we discuss?"
        args.session_id = None
        args.user_id = None
        args.namespace = None
        args.model_name = None
        args.context_window_max = None
        args.long_term_search = False

        cli.cmd_memory_prompt(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertEqual(call_args[0][1], "/v1/memory/prompt")
        payload = call_args[1]["data"]
        self.assertEqual(payload["query"], "What did we discuss?")

    @patch("scripts.cli_memory.make_request")
    def test_cmd_memory_prompt_with_session(self, mock_request):
        mock_request.return_value = {"prompt": "Context: session data"}

        import scripts.cli_memory as cli

        args = Mock()
        args.query = "What did we discuss?"
        args.session_id = "session-1"
        args.user_id = "user-1"
        args.namespace = "app"
        args.model_name = "gpt-4"
        args.context_window_max = 8000
        args.long_term_search = False

        cli.cmd_memory_prompt(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        payload = call_args[1]["data"]
        self.assertIn("session", payload)
        self.assertEqual(payload["session"]["session_id"], "session-1")


class TestSummaryViewCommands(unittest.TestCase):
    def setUp(self):
        for key in [
            "AGENT_MEMORY_BASE_URL",
            "AGENT_MEMORY_API_KEY",
            "AGENT_MEMORY_TIMEOUT",
            "DISABLE_AUTH",
        ]:
            if key in os.environ:
                del os.environ[key]

    @patch("scripts.cli_memory.make_request")
    def test_cmd_create_summary_view(self, mock_request):
        mock_request.return_value = {"id": "view-1", "name": "test-view"}

        import scripts.cli_memory as cli

        args = Mock()
        args.name = "test-view"
        args.source = "long_term"
        args.group_by = "user_id,namespace"
        args.filters = None
        args.time_window_days = None
        args.continuous = False
        args.prompt = None
        args.model_name = None

        cli.cmd_create_summary_view(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertEqual(call_args[0][1], "/v1/summary-views")
        payload = call_args[1]["data"]
        self.assertEqual(payload["source"], "long_term")
        self.assertEqual(payload["group_by"], ["user_id", "namespace"])

    @patch("scripts.cli_memory.make_request")
    def test_cmd_list_summary_views(self, mock_request):
        mock_request.return_value = {"views": []}

        import scripts.cli_memory as cli

        cli.cmd_list_summary_views(Mock())

        mock_request.assert_called_once()

    @patch("scripts.cli_memory.make_request")
    def test_cmd_run_summary_view(self, mock_request):
        mock_request.return_value = {"task_id": "task-123"}

        import scripts.cli_memory as cli

        args = Mock()
        args.view_id = "view-1"
        args.task_id = None

        cli.cmd_run_summary_view(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][1], "/v1/summary-views/view-1/run")


class TestTaskCommands(unittest.TestCase):
    def setUp(self):
        for key in [
            "AGENT_MEMORY_BASE_URL",
            "AGENT_MEMORY_API_KEY",
            "AGENT_MEMORY_TIMEOUT",
            "DISABLE_AUTH",
        ]:
            if key in os.environ:
                del os.environ[key]

    @patch("scripts.cli_memory.make_request")
    def test_cmd_get_task(self, mock_request):
        mock_request.return_value = {
            "task_id": "task-1",
            "status": "success",
        }

        import scripts.cli_memory as cli

        args = Mock()
        args.task_id = "task-1"

        cli.cmd_get_task(args)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "GET")
        self.assertEqual(call_args[0][1], "/v1/tasks/task-1")


class TestArgumentParsing(unittest.TestCase):
    def test_add_message_arguments(self):
        import importlib
        import scripts.cli_memory as cli

        importlib.reload(cli)

        self.assertIsNotNone(cli.main)


if __name__ == "__main__":
    unittest.main()
