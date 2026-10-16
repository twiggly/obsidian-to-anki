import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

MAKE = shutil.which("make")
MAKEFILE = Path(__file__).resolve().parents[1] / "Makefile"
CHECK_ARGUMENTS = (
    "-m ruff check .",
    "-m ruff format --check .",
    "-m unittest discover -s tests -v",
)


@unittest.skipUnless(MAKE and os.name == "posix", "Workflow tests require POSIX make")
class DevelopmentWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.directory = Path(temporary_directory.name)
        shutil.copyfile(MAKEFILE, self.directory / "Makefile")
        self.bin_directory = self.directory / "bin"
        self.bin_directory.mkdir()
        self.command_log = self.directory / "commands.log"
        # Exclude the real PATH so tests cannot accidentally invoke Git or GitHub CLI.
        self.environment = {
            "PATH": str(self.bin_directory),
            "HOME": str(self.directory),
            "COMMAND_LOG": str(self.command_log),
            "TEST_BRANCH": "codex/example",
        }
        self.write_python_stub(self.bin_directory / "python3.15", "fallback")
        self.write_python_stub(self.bin_directory / "override-python", "override")
        self.write_stub(
            self.bin_directory / "git",
            'printf "git %s\\n" "$*" >> "$COMMAND_LOG"\n'
            'if [ "$1" = branch ]; then printf "%s\\n" "$TEST_BRANCH"; fi\n'
            'if [ "$1" = push ]; then exit "${PUSH_EXIT_STATUS:-0}"; fi\n',
        )
        self.write_stub(
            self.bin_directory / "gh",
            'printf "gh %s\\n" "$*" >> "$COMMAND_LOG"\n',
        )

    def write_stub(self, path: Path, body: str, *, executable: bool = True) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755 if executable else 0o644)

    def write_python_stub(self, path: Path, label: str, *, executable: bool = True) -> None:
        self.write_stub(
            path,
            f'printf "{label} %s\\n" "$*" >> "$COMMAND_LOG"\n'
            'if [ "$*" = "${FAIL_COMMAND:-}" ]; then exit 42; fi\n',
            executable=executable,
        )

    def add_virtualenv(self, *, executable: bool = True) -> None:
        self.write_python_stub(
            self.directory / ".venv/bin/python", "virtualenv", executable=executable
        )

    def run_make(self, *arguments: str, **environment: str) -> subprocess.CompletedProcess[str]:
        self.command_log.unlink(missing_ok=True)
        return subprocess.run(
            [MAKE, "--no-print-directory", *arguments],
            cwd=self.directory,
            env={**self.environment, **environment},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def commands(self) -> list[str]:
        if not self.command_log.exists():
            return []
        return self.command_log.read_text(encoding="utf-8").splitlines()

    def assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def check_commands(self, label: str) -> list[str]:
        return [f"{label} {arguments}" for arguments in CHECK_ARGUMENTS]

    def pr_commands(self, label: str) -> list[str]:
        return [
            "git branch --show-current",
            *self.check_commands(label),
            "git push -u origin codex/example",
            "gh pr create --fill --draft",
        ]

    def test_check_prefers_executable_project_python(self) -> None:
        self.add_virtualenv()
        self.assert_success(self.run_make("check"))
        self.assertEqual(self.commands(), self.check_commands("virtualenv"))

    def test_check_falls_back_when_project_python_is_missing_or_not_executable(self) -> None:
        for state in ("missing", "not executable"):
            with self.subTest(state=state):
                if state == "not executable":
                    self.add_virtualenv(executable=False)
                self.assert_success(self.run_make("check"))
                self.assertEqual(self.commands(), self.check_commands("fallback"))

    def test_python_overrides_apply_to_check_and_recursive_pr_checks(self) -> None:
        self.add_virtualenv()
        for target in ("check", "pr"):
            for source in ("environment", "command line"):
                with self.subTest(target=target, source=source):
                    if source == "environment":
                        result = self.run_make(target, PYTHON="override-python")
                    else:
                        result = self.run_make(
                            target, "PYTHON=override-python", PYTHON="python3.15"
                        )
                    self.assert_success(result)
                    expected = (
                        self.pr_commands("override")
                        if target == "pr"
                        else self.check_commands("override")
                    )
                    self.assertEqual(self.commands(), expected)

    def test_format_uses_project_python(self) -> None:
        self.add_virtualenv()
        self.assert_success(self.run_make("format"))
        self.assertEqual(self.commands(), ["virtualenv -m ruff format ."])

    def test_pr_preserves_default_interpreter_in_recursive_make(self) -> None:
        for label in ("fallback", "virtualenv"):
            with self.subTest(interpreter=label):
                if label == "virtualenv":
                    self.add_virtualenv()
                self.assert_success(self.run_make("pr"))
                self.assertEqual(self.commands(), self.pr_commands(label))

    def test_each_failed_check_prevents_push_and_pr_creation(self) -> None:
        self.add_virtualenv()
        for index, failing_command in enumerate(CHECK_ARGUMENTS):
            with self.subTest(command=failing_command):
                result = self.run_make("pr", FAIL_COMMAND=failing_command)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(
                    self.commands(),
                    ["git branch --show-current", *self.check_commands("virtualenv")[: index + 1]],
                )

    def test_pr_requires_github_cli_before_running_checks(self) -> None:
        (self.bin_directory / "gh").unlink()
        result = self.run_make("pr")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GitHub CLI (gh) is required", result.stdout)
        self.assertEqual(self.commands(), [])

    def test_pr_rejects_main_and_missing_branch_before_running_checks(self) -> None:
        for branch, message in (
            ("main", "Switch to a feature branch"),
            ("", "Could not determine the current branch"),
        ):
            with self.subTest(branch=branch):
                result = self.run_make("pr", TEST_BRANCH=branch)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout)
                self.assertEqual(self.commands(), ["git branch --show-current"])

    def test_failed_push_prevents_pr_creation(self) -> None:
        result = self.run_make("pr", PUSH_EXIT_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands(), self.pr_commands("fallback")[:-1])
