import io
from textwrap import dedent
from unittest.mock import MagicMock, patch

import docker
import PIL.Image
import pytest
from rich.console import Console

from smolagents.default_tools import FinalAnswerTool, WikipediaSearchTool
from smolagents.monitoring import AgentLogger, LogLevel
from smolagents.remote_executors import (
    DockerExecutor,
    E2BExecutor,
    RemotePythonExecutor,
    WasmExecutor,
    YepCodeExecutor,
)
from smolagents.utils import AgentError

from .utils.markers import require_run_all


class TestRemotePythonExecutor:
    def test_send_tools_empty_tools(self):
        executor = RemotePythonExecutor(additional_imports=[], logger=MagicMock())
        executor.run_code_raise_errors = MagicMock()
        executor.send_tools({})
        assert executor.run_code_raise_errors.call_count == 1
        # No new packages should be installed
        assert "!pip install" not in executor.run_code_raise_errors.call_args.args[0]

    @require_run_all
    def test_send_tools_with_default_wikipedia_search_tool(self):
        tool = WikipediaSearchTool()
        executor = RemotePythonExecutor(additional_imports=[], logger=MagicMock())
        executor.run_code_raise_errors = MagicMock()
        executor.send_tools({"wikipedia_search": tool})
        assert executor.run_code_raise_errors.call_count == 2
        assert "!pip install wikipedia-api" == executor.run_code_raise_errors.call_args_list[0].args[0]
        assert "class WikipediaSearchTool(Tool)" in executor.run_code_raise_errors.call_args_list[1].args[0]


class TestE2BExecutorUnit:
    def test_e2b_executor_instantiation(self):
        logger = MagicMock()
        with patch("e2b_code_interpreter.Sandbox") as mock_sandbox:
            mock_sandbox.return_value.commands.run.return_value.error = None
            mock_sandbox.return_value.run_code.return_value.error = None
            executor = E2BExecutor(
                additional_imports=[], logger=logger, api_key="dummy-api-key", template="dummy-template-id", timeout=60
            )
        assert isinstance(executor, E2BExecutor)
        assert executor.logger == logger
        assert executor.sandbox == mock_sandbox.return_value
        assert mock_sandbox.call_count == 1
        assert mock_sandbox.call_args.kwargs == {
            "api_key": "dummy-api-key",
            "template": "dummy-template-id",
            "timeout": 60,
        }

    def test_cleanup(self):
        """Test that the cleanup method properly shuts down the sandbox"""
        logger = MagicMock()
        with patch("e2b_code_interpreter.Sandbox") as mock_sandbox:
            # Setup mock
            mock_sandbox.return_value.kill = MagicMock()

            # Create executor
            executor = E2BExecutor(additional_imports=[], logger=logger, api_key="dummy-api-key")

            # Call cleanup
            executor.cleanup()

            # Verify sandbox was killed
            mock_sandbox.return_value.kill.assert_called_once()
            assert logger.log.call_count >= 2  # Should log start and completion messages


class TestYepCodeExecutorUnit:
    def test_yepcode_executor_instantiation(self):
        logger = MagicMock()
        with (
            patch("yepcode_run.YepCodeApiConfig") as mock_config,
            patch("yepcode_run.YepCodeRun") as mock_run,
            patch("os.getenv") as mock_getenv,
        ):
            mock_getenv.return_value = "dummy-api-token"
            mock_config.return_value = MagicMock()
            mock_run.return_value = MagicMock()

            executor = YepCodeExecutor(
                additional_imports=[], logger=logger, api_token="dummy-api-token", removeOnDone=True
            )

        assert isinstance(executor, YepCodeExecutor)
        assert executor.logger == logger
        assert executor.api_config == mock_config.return_value
        assert executor.runner == mock_run.return_value
        assert executor.kwargs == {"removeOnDone": True}
        assert mock_config.call_count == 1
        assert mock_config.call_args.kwargs == {"api_token": "dummy-api-token"}
        assert mock_run.call_count == 1
        assert mock_run.call_args.args[0] == mock_config.return_value

    def test_yepcode_executor_instantiation_with_env_token(self):
        logger = MagicMock()
        with (
            patch("yepcode_run.YepCodeApiConfig") as mock_config,
            patch("yepcode_run.YepCodeRun") as mock_run,
            patch("os.getenv") as mock_getenv,
        ):
            mock_getenv.return_value = "env-api-token"
            mock_config.return_value = MagicMock()
            mock_run.return_value = MagicMock()

            executor = YepCodeExecutor(additional_imports=[], logger=logger)

        assert isinstance(executor, YepCodeExecutor)
        assert executor.logger == logger
        assert mock_config.call_count == 1
        assert mock_config.call_args.kwargs == {"api_token": "env-api-token"}

    def test_yepcode_executor_instantiation_no_token_raises_error(self):
        logger = MagicMock()
        with (
            patch("os.getenv") as mock_getenv,
        ):
            mock_getenv.return_value = None

            with pytest.raises(ValueError) as excinfo:
                YepCodeExecutor(additional_imports=[], logger=logger)

            assert "YepCode API token is required" in str(excinfo.value)

    def test_cleanup(self):
        """Test that the cleanup method properly cleans up YepCode resources"""
        logger = MagicMock()
        with (
            patch("yepcode_run.YepCodeApiConfig") as mock_config,
            patch("yepcode_run.YepCodeRun") as mock_run,
            patch("os.getenv") as mock_getenv,
        ):
            mock_getenv.return_value = "dummy-api-token"
            mock_config.return_value = MagicMock()
            mock_run.return_value = MagicMock()

            # Create executor
            executor = YepCodeExecutor(additional_imports=[], logger=logger, api_token="dummy-api-token")

            # Call cleanup
            executor.cleanup()

            # Verify cleanup was logged
            assert logger.log.call_count >= 2  # Should log start and completion messages

            # Verify runner and api_config attributes are deleted
            assert not hasattr(executor, "runner")
            assert not hasattr(executor, "api_config")


@pytest.fixture
def e2b_executor():
    executor = E2BExecutor(
        additional_imports=["pillow", "numpy"],
        logger=AgentLogger(LogLevel.INFO, Console(force_terminal=False, file=io.StringIO())),
    )
    yield executor
    executor.cleanup()


@pytest.fixture
def yepcode_executor():
    executor = YepCodeExecutor(
        additional_imports=["pillow", "numpy"],
        logger=AgentLogger(LogLevel.INFO, Console(force_terminal=False, file=io.StringIO())),
    )
    yield executor
    executor.cleanup()


@require_run_all
class TestE2BExecutorIntegration:
    @pytest.fixture(autouse=True)
    def set_executor(self, e2b_executor):
        self.executor = e2b_executor

    @pytest.mark.parametrize(
        "code_action, expected_result",
        [
            (
                dedent('''
                    final_answer("""This is
                    a multiline
                    final answer""")
                '''),
                "This is\na multiline\nfinal answer",
            ),
            (
                dedent("""
                    text = '''Text containing
                    final_answer(5)
                    '''
                    final_answer(text)
                """),
                "Text containing\nfinal_answer(5)\n",
            ),
            (
                dedent("""
                    num = 2
                    if num == 1:
                        final_answer("One")
                    elif num == 2:
                        final_answer("Two")
                """),
                "Two",
            ),
        ],
    )
    def test_final_answer_patterns(self, code_action, expected_result):
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == expected_result

    def test_custom_final_answer(self):
        class CustomFinalAnswerTool(FinalAnswerTool):
            def forward(self, answer: str) -> str:
                return "CUSTOM" + answer

        self.executor.send_tools({"final_answer": CustomFinalAnswerTool()})
        code_action = dedent("""
            final_answer(answer="_answer")
        """)
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == "CUSTOM_answer"

    def test_custom_final_answer_with_custom_inputs(self):
        class CustomFinalAnswerToolWithCustomInputs(FinalAnswerTool):
            inputs = {
                "answer1": {"type": "string", "description": "First part of the answer."},
                "answer2": {"type": "string", "description": "Second part of the answer."},
            }

            def forward(self, answer1: str, answer2: str) -> str:
                return answer1 + "CUSTOM" + answer2

        self.executor.send_tools({"final_answer": CustomFinalAnswerToolWithCustomInputs()})
        code_action = dedent("""
            final_answer(
                answer1="answer1_",
                answer2="_answer2"
            )
        """)
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == "answer1_CUSTOM_answer2"


@require_run_all
class TestYepCodeExecutorIntegration:
    @pytest.fixture(autouse=True)
    def set_executor(self, yepcode_executor):
        self.executor = yepcode_executor

    @pytest.mark.parametrize(
        "code_action, expected_result",
        [
            (
                dedent('''
                    final_answer("""This is
                    a multiline
                    final answer""")
                '''),
                "This is\na multiline\nfinal answer",
            ),
            (
                dedent("""
                    text = '''Text containing
                    final_answer(5)
                    '''
                    final_answer(text)
                """),
                "Text containing\nfinal_answer(5)\n",
            ),
            (
                dedent("""
                    num = 2
                    if num == 1:
                        final_answer("One")
                    elif num == 2:
                        final_answer("Two")
                """),
                "Two",
            ),
        ],
    )
    def test_final_answer_patterns(self, code_action, expected_result):
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == expected_result

    def test_custom_final_answer(self):
        class CustomFinalAnswerTool(FinalAnswerTool):
            def forward(self, answer: str) -> str:
                return "CUSTOM" + answer

        self.executor.send_tools({"final_answer": CustomFinalAnswerTool()})
        code_action = dedent("""
            final_answer(answer="_answer")
        """)
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == "CUSTOM_answer"

    def test_custom_final_answer_with_custom_inputs(self):
        class CustomFinalAnswerToolWithCustomInputs(FinalAnswerTool):
            inputs = {
                "answer1": {"type": "string", "description": "First part of the answer."},
                "answer2": {"type": "string", "description": "Second part of the answer."},
            }

            def forward(self, answer1: str, answer2: str) -> str:
                return answer1 + "CUSTOM" + answer2

        self.executor.send_tools({"final_answer": CustomFinalAnswerToolWithCustomInputs()})
        code_action = dedent("""
            final_answer(
                answer1="answer1_",
                answer2="_answer2"
            )
        """)
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == "answer1_CUSTOM_answer2"

    def test_initialization(self):
        """Check if YepCodeExecutor initializes without errors"""
        assert self.executor.runner is not None, "Runner should be initialized"
        assert self.executor.api_config is not None, "API config should be initialized"

    def test_state_persistence(self):
        """Test that variables and imports from one snippet persist in the next"""
        code_action = "import numpy as np; a = 2"
        self.executor(code_action)

        code_action = "print(np.sqrt(a))"
        code_output = self.executor(code_action)
        assert "1.41421" in code_output.logs

    def test_execute_output(self):
        """Test execution that returns a string"""
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_action = 'final_answer("This is the final answer")'
        code_output = self.executor(code_action)
        assert code_output.output == "This is the final answer", "Result should be 'This is the final answer'"

    def test_execute_multiline_output(self):
        """Test execution that returns a string"""
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_action = 'result = "This is the final answer"\nfinal_answer(result)'
        code_output = self.executor(code_action)
        assert code_output.output == "This is the final answer", "Result should be 'This is the final answer'"

    def test_execute_image_output(self):
        """Test execution that returns a base64 image"""
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_action = dedent("""
            import base64
            from PIL import Image
            from io import BytesIO
            image = Image.new("RGB", (10, 10), (255, 0, 0))
            final_answer(image)
        """)
        code_output = self.executor(code_action)
        assert isinstance(code_output.output, PIL.Image.Image), "Result should be a PIL Image"

    def test_syntax_error_handling(self):
        """Test handling of syntax errors"""
        code_action = 'print("Missing Parenthesis'  # Syntax error
        with pytest.raises(AgentError) as exception_info:
            self.executor(code_action)
        assert "SyntaxError" in str(exception_info.value), "Should raise a syntax error"

    def test_automatic_package_installation(self):
        """Test that YepCode automatically installs packages from imports"""
        code_action = dedent("""
            import requests
            response = requests.get("https://httpbin.org/status/200")
            final_answer(f"Status: {response.status_code}")
        """)
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_output = self.executor(code_action)
        assert code_output.output == "Status: 200", "Should successfully use auto-installed requests package"

    def test_numpy_execution(self):
        """Test execution with NumPy (should be auto-installed)"""
        code_action = dedent("""
            import numpy as np
            arr = np.array([1, 2, 3, 4, 5])
            final_answer(f"Mean: {np.mean(arr)}")
        """)
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_output = self.executor(code_action)
        assert code_output.output == "Mean: 3.0", "Should successfully use auto-installed numpy"

    def test_runtime_error_handling(self):
        """Test handling of runtime errors"""
        code_action = "1/0"  # Division by zero
        with pytest.raises(AgentError) as exception_info:
            self.executor(code_action)
        assert "ZeroDivisionError" in str(exception_info.value), "Should raise a division by zero error"

    def test_variables_persistence_across_executions(self):
        """Test that variables sent via send_variables persist across executions"""
        # Send variables
        self.executor.send_variables({"x": 42, "message": "hello world"})

        # Use the variables in code execution
        code_action = dedent("""
            final_answer(f"x = {x}, message = {message}")
        """)
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_output = self.executor(code_action)
        assert code_output.output == "x = 42, message = hello world", "Variables should persist across executions"

    def test_tools_and_variables_together(self):
        """Test that tools and variables work together"""
        # Send variables and tools
        self.executor.send_variables({"multiplier": 5})
        self.executor.send_tools({"final_answer": FinalAnswerTool()})

        # Use both in code execution
        code_action = dedent("""
            result = 10 * multiplier
            final_answer(f"Result: {result}")
        """)
        code_output = self.executor(code_action)
        assert code_output.output == "Result: 50", "Tools and variables should work together"


class TestDockerExecutorUnit:
    def test_cleanup(self):
        """Test that cleanup properly stops and removes the container"""
        logger = MagicMock()
        with (
            patch("docker.from_env") as mock_docker_client,
            patch("requests.post") as mock_post,
            patch("websocket.create_connection"),
        ):
            # Setup mocks
            mock_container = MagicMock()
            mock_container.status = "running"
            mock_container.short_id = "test123"

            mock_docker_client.return_value.containers.run.return_value = mock_container
            mock_docker_client.return_value.images.get.return_value = MagicMock()

            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "test-kernel-id"}

            # Create executor
            executor = DockerExecutor(additional_imports=[], logger=logger, build_new_image=False)

            # Call cleanup
            executor.cleanup()

            # Verify container was stopped and removed
            mock_container.stop.assert_called_once()
            mock_container.remove.assert_called_once()


@pytest.fixture
def docker_executor():
    executor = DockerExecutor(
        additional_imports=["pillow", "numpy"],
        logger=AgentLogger(LogLevel.INFO, Console(force_terminal=False, file=io.StringIO())),
    )
    yield executor
    executor.delete()


@require_run_all
class TestDockerExecutorIntegration:
    @pytest.fixture(autouse=True)
    def set_executor(self, docker_executor):
        self.executor = docker_executor

    def test_initialization(self):
        """Check if DockerExecutor initializes without errors"""
        assert self.executor.container is not None, "Container should be initialized"

    def test_state_persistence(self):
        """Test that variables and imports form one snippet persist in the next"""
        code_action = "import numpy as np; a = 2"
        self.executor(code_action)

        code_action = "print(np.sqrt(a))"
        code_output = self.executor(code_action)
        assert "1.41421" in code_output.logs

    def test_execute_output(self):
        """Test execution that returns a string"""
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_action = 'final_answer("This is the final answer")'
        code_output = self.executor(code_action)
        assert code_output.output == "This is the final answer", "Result should be 'This is the final answer'"

    def test_execute_multiline_output(self):
        """Test execution that returns a string"""
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_action = 'result = "This is the final answer"\nfinal_answer(result)'
        code_output = self.executor(code_action)
        assert code_output.output == "This is the final answer", "Result should be 'This is the final answer'"

    def test_execute_image_output(self):
        """Test execution that returns a base64 image"""
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_action = dedent("""
            import base64
            from PIL import Image
            from io import BytesIO
            image = Image.new("RGB", (10, 10), (255, 0, 0))
            final_answer(image)
        """)
        code_output = self.executor(code_action)
        assert isinstance(code_output.output, PIL.Image.Image), "Result should be a PIL Image"

    def test_syntax_error_handling(self):
        """Test handling of syntax errors"""
        code_action = 'print("Missing Parenthesis'  # Syntax error
        with pytest.raises(AgentError) as exception_info:
            self.executor(code_action)
        assert "SyntaxError" in str(exception_info.value), "Should raise a syntax error"

    def test_cleanup_on_deletion(self):
        """Test if Docker container stops and removes on deletion"""
        container_id = self.executor.container.id
        self.executor.delete()  # Trigger cleanup

        client = docker.from_env()
        containers = [c.id for c in client.containers.list(all=True)]
        assert container_id not in containers, "Container should be removed"

    @pytest.mark.parametrize(
        "code_action, expected_result",
        [
            (
                dedent('''
                    final_answer("""This is
                    a multiline
                    final answer""")
                '''),
                "This is\na multiline\nfinal answer",
            ),
            (
                dedent("""
                    text = '''Text containing
                    final_answer(5)
                    '''
                    final_answer(text)
                """),
                "Text containing\nfinal_answer(5)\n",
            ),
            (
                dedent("""
                    num = 2
                    if num == 1:
                        final_answer("One")
                    elif num == 2:
                        final_answer("Two")
                """),
                "Two",
            ),
        ],
    )
    def test_final_answer_patterns(self, code_action, expected_result):
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == expected_result

    def test_custom_final_answer(self):
        class CustomFinalAnswerTool(FinalAnswerTool):
            def forward(self, answer: str) -> str:
                return "CUSTOM" + answer

        self.executor.send_tools({"final_answer": CustomFinalAnswerTool()})
        code_action = dedent("""
            final_answer(answer="_answer")
        """)
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == "CUSTOM_answer"

    def test_custom_final_answer_with_custom_inputs(self):
        class CustomFinalAnswerToolWithCustomInputs(FinalAnswerTool):
            inputs = {
                "answer1": {"type": "string", "description": "First part of the answer."},
                "answer2": {"type": "string", "description": "Second part of the answer."},
            }

            def forward(self, answer1: str, answer2: str) -> str:
                return answer1 + "CUSTOM" + answer2

        self.executor.send_tools({"final_answer": CustomFinalAnswerToolWithCustomInputs()})
        code_action = dedent("""
            final_answer(
                answer1="answer1_",
                answer2="_answer2"
            )
        """)
        code_output = self.executor(code_action)
        assert code_output.is_final_answer is True
        assert code_output.output == "answer1_CUSTOM_answer2"


class TestWasmExecutorUnit:
    def test_wasm_executor_instantiation(self):
        logger = MagicMock()

        # Mock subprocess.run to simulate Deno being installed
        with (
            patch("subprocess.run") as mock_run,
            patch("subprocess.Popen") as mock_popen,
            patch("requests.get") as mock_get,
            patch("time.sleep"),
        ):
            # Configure mocks
            mock_run.return_value.returncode = 0
            mock_process = MagicMock()
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process
            mock_get.return_value.status_code = 200

            # Create the executor
            executor = WasmExecutor(additional_imports=["numpy", "pandas"], logger=logger, timeout=30)

            # Verify the executor was created correctly
            assert isinstance(executor, WasmExecutor)
            assert executor.logger == logger
            assert executor.timeout == 30
            assert "numpy" in executor.installed_packages
            assert "pandas" in executor.installed_packages

            # Verify Deno was checked
            assert mock_run.call_count == 1
            assert mock_run.call_args.args[0][0] == "deno"
            assert mock_run.call_args.args[0][1] == "--version"

            # Verify server was started
            assert mock_popen.call_count == 1
            assert mock_popen.call_args.args[0][0] == "deno"
            assert mock_popen.call_args.args[0][1] == "run"

            # Clean up
            with patch("shutil.rmtree"):
                executor.cleanup()


@require_run_all
class TestWasmExecutorIntegration:
    """
    Integration tests for WasmExecutor.

    These tests require Deno to be installed on the system.
    Skip these tests if you don't have Deno installed.
    """

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test."""
        try:
            # Check if Deno is installed
            import subprocess

            subprocess.run(["deno", "--version"], capture_output=True, check=True)

            # Create the executor
            self.executor = WasmExecutor(
                additional_imports=["numpy", "pandas"],
                logger=AgentLogger(LogLevel.INFO, Console(force_terminal=False, file=io.StringIO())),
                timeout=60,
            )
            yield
            # Clean up
            self.executor.cleanup()
        except (subprocess.SubprocessError, FileNotFoundError):
            pytest.skip("Deno is not installed, skipping integration tests")

    def test_basic_execution(self):
        """Test basic code execution."""
        code = "a = 2 + 2; print(f'Result: {a}')"
        code_output = self.executor(code)
        assert "Result: 4" in code_output.logs

    def test_state_persistence(self):
        """Test that variables persist between executions."""
        # Define a variable
        self.executor("x = 42")

        # Use the variable in a subsequent execution
        code_output = self.executor("print(x)")
        assert "42" in code_output.logs

    def test_final_answer(self):
        """Test returning a final answer."""
        self.executor.send_tools({"final_answer": FinalAnswerTool()})
        code = 'final_answer("This is the final answer")'
        code_output = self.executor(code)
        assert code_output.output == "This is the final answer"
        assert code_output.is_final_answer is True

    def test_numpy_execution(self):
        """Test execution with NumPy."""
        code = """
        import numpy as np
        arr = np.array([1, 2, 3, 4, 5])
        print(f"Mean: {np.mean(arr)}")
        """
        code_output = self.executor(code)
        assert "Mean: 3.0" in code_output.logs

    def test_error_handling(self):
        """Test handling of Python errors."""
        code = "1/0"  # Division by zero
        with pytest.raises(AgentError) as excinfo:
            self.executor(code)
        assert "ZeroDivisionError" in str(excinfo.value)

    def test_syntax_error_handling(self):
        """Test handling of syntax errors."""
        code = "print('Missing parenthesis"  # Missing closing parenthesis
        with pytest.raises(AgentError) as excinfo:
            self.executor(code)
        assert "SyntaxError" in str(excinfo.value)
