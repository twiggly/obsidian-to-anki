import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

MAKE = shutil.which("make")
GIT = shutil.which("git")
MAKEFILE = Path(__file__).resolve().parents[1] / "Makefile"
PR_TEMPLATE = MAKEFILE.parent / ".github/pull_request_template.md"
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
        self.pr_template = self.directory / ".github/pull_request_template.md"
        self.pr_template.parent.mkdir()
        shutil.copyfile(PR_TEMPLATE, self.pr_template)
        self.pr_body = self.directory / "pr-body.md"
        self.bin_directory = self.directory / "bin"
        self.bin_directory.mkdir()
        self.command_log = self.directory / "commands.log"
        # Exclude the real PATH so tests cannot accidentally invoke Git or GitHub CLI.
        self.environment = {
            "PATH": str(self.bin_directory),
            "HOME": str(self.directory),
            "COMMAND_LOG": str(self.command_log),
            "PR_BODY": str(self.pr_body),
            "TEST_BRANCH": "codex/example",
        }
        self.write_python_stub(self.bin_directory / "python3.15", "fallback")
        self.write_python_stub(self.bin_directory / "override-python", "override")
        self.write_stub(
            self.bin_directory / "git",
            'printf "git %s\\n" "$*" >> "$COMMAND_LOG"\n'
            'if [ "$*" = "${FAIL_GIT_COMMAND:-}" ]; then exit 1; fi\n'
            'if [ "$1" = branch ] && [ "$2" = --show-current ]; then\n'
            '  printf "%s\\n" "$TEST_BRANCH"\n'
            '  exit "${BRANCH_EXIT_STATUS:-0}"\n'
            "fi\n"
            'if [ "$1" = status ]; then\n'
            '  printf "%s" "${TEST_STATUS:-}"\n'
            '  exit "${STATUS_EXIT_STATUS:-0}"\n'
            "fi\n"
            'if [ "$1" = push ]; then exit "${PUSH_EXIT_STATUS:-0}"; fi\n',
        )
        self.write_stub(
            self.bin_directory / "gh",
            'printf "gh %s\\n" "$*" >> "$COMMAND_LOG"\n'
            'if [ "$1" = pr ] && [ "$2" = list ]; then\n'
            '  printf "%s" "${TEST_PR_URL:-}"\n'
            '  exit "${PR_LOOKUP_EXIT_STATUS:-0}"\n'
            "fi\n"
            'while [ "$#" -gt 0 ]; do\n'
            '  if [ "$1" = --body-file ]; then\n'
            "    shift\n"
            '    while IFS= read -r line || [ -n "$line" ]; do\n'
            '      printf "%s\\n" "$line"\n'
            '    done < "$1" > "$PR_BODY" || exit 1\n'
            "  fi\n"
            "  shift\n"
            "done\n",
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
            "git status --porcelain --untracked-files=all",
            *self.check_commands(label),
            "gh pr list --head codex/example --base main --state open "
            "--json url,isCrossRepository --jq "
            ".[] | select(.isCrossRepository == false) | .url",
            "git push -u origin codex/example",
            "gh pr create --base main --head codex/example --fill --draft "
            "--body-file .github/pull_request_template.md",
        ]

    def finish_commands(self) -> list[str]:
        return [
            "git check-ref-format refs/heads/codex/example",
            "git status --porcelain --untracked-files=all",
            "git show-ref --verify --quiet refs/heads/codex/example",
            "git fetch --prune origin",
            "git merge-base --is-ancestor refs/heads/codex/example refs/remotes/origin/main",
            "git merge-base --is-ancestor refs/heads/main refs/remotes/origin/main",
            "git switch main",
            "git merge --ff-only refs/remotes/origin/main",
            "git branch -d -- codex/example",
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
                    self.pr_commands("virtualenv")[: index + 3],
                )

    def test_pr_uses_shared_checklist_without_marking_checks_complete(self) -> None:
        self.assert_success(self.run_make("pr"))
        self.assertEqual(self.commands(), self.pr_commands("fallback"))
        body = self.pr_body.read_text(encoding="utf-8")
        self.assertEqual(body, PR_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("## Summary", body)
        self.assertIn("- [ ] `make check` passed.", body)
        self.assertIn("GUI check:", body)
        self.assertNotIn("- [x]", body.lower())

    def test_repeated_pr_run_pushes_and_reuses_existing_pr_without_editing_it(self) -> None:
        self.assert_success(self.run_make("pr"))
        edited_body = "## Summary\nReviewed changes.\n\n- [x] Checks passed.\n"
        self.pr_body.write_text(edited_body, encoding="utf-8")
        url = "https://github.com/example/project/pull/123"

        self.assert_success(result := self.run_make("pr", TEST_PR_URL=url))

        self.assertEqual(self.commands(), self.pr_commands("fallback")[:-1])
        self.assertIn(url, result.stdout)
        self.assertEqual(self.pr_body.read_text(encoding="utf-8"), edited_body)

    def test_pr_lookup_failures_prevent_push_and_creation(self) -> None:
        for status in ("1", "4"):
            with self.subTest(exit_status=status):
                result = self.run_make(
                    "pr", PR_LOOKUP_EXIT_STATUS=status, TEST_PR_URL="partial output"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.commands(), self.pr_commands("fallback")[:-2])
                self.assertFalse(self.pr_body.exists())

    def test_pr_requires_template_before_checks_or_remote_actions(self) -> None:
        self.pr_template.unlink()
        for state in ("missing", "directory"):
            with self.subTest(state=state):
                if state == "directory":
                    self.pr_template.mkdir()
                result = self.run_make("pr")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("PR checklist template is missing or unreadable", result.stdout)
                self.assertEqual(self.commands(), self.pr_commands("fallback")[:2])
                self.assertFalse(self.pr_body.exists())

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

    def test_pr_rejects_uncommitted_changes_before_checks_or_remote_actions(self) -> None:
        for status in (" M README.md\n", "M  Makefile\n", "?? new-file.txt\n"):
            with self.subTest(status=status):
                result = self.run_make("pr", TEST_STATUS=status)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Commit or stash all changes", result.stdout)
                self.assertEqual(self.commands(), self.pr_commands("fallback")[:2])

    def test_pr_stops_when_git_status_fails(self) -> None:
        result = self.run_make("pr", STATUS_EXIT_STATUS="128")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands(), self.pr_commands("fallback")[:2])

    def test_branch_requires_a_name_before_calling_git(self) -> None:
        result = self.run_make("branch", TEST_BRANCH="main")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage: make branch NAME=short-description", result.stdout)
        self.assertEqual(self.commands(), [])

    def test_branch_requires_main_before_creating_a_branch(self) -> None:
        for branch in ("codex/another-feature", "release", ""):
            with self.subTest(branch=branch):
                result = self.run_make("branch", "NAME=example", TEST_BRANCH=branch)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Run make sync-main first", result.stdout)
                self.assertEqual(self.commands(), ["git branch --show-current"])

    def test_branch_creates_requested_branch_from_main(self) -> None:
        self.assert_success(self.run_make("branch", "NAME=example", TEST_BRANCH="main"))
        self.assertEqual(
            self.commands(), ["git branch --show-current", "git switch -c codex/example"]
        )

    def test_git_branch_failures_stop_branch_and_pr(self) -> None:
        for target, branch in (("branch", "main"), ("pr", "codex/example")):
            with self.subTest(target=target):
                result = self.run_make(
                    target, "NAME=example", TEST_BRANCH=branch, BRANCH_EXIT_STATUS="128"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.commands(), ["git branch --show-current"])

    def test_finish_updates_main_then_deletes_only_the_named_branch(self) -> None:
        self.assert_success(self.run_make("finish", "BRANCH=codex/example"))
        self.assertEqual(self.commands(), self.finish_commands())

    def test_finish_requires_a_branch_and_refuses_main_before_calling_git(self) -> None:
        for branch, message in (
            ("", "Usage: make finish BRANCH="),
            ("main", "Cannot delete main"),
        ):
            with self.subTest(branch=branch):
                result = self.run_make("finish", f"BRANCH={branch}")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout)
                self.assertEqual(self.commands(), [])

    def test_finish_rejects_uncommitted_changes_before_fetching_or_switching(self) -> None:
        for status in (" M README.md\n", "M  Makefile\n", "?? new-file.txt\n"):
            with self.subTest(status=status):
                result = self.run_make("finish", "BRANCH=codex/example", TEST_STATUS=status)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Commit or stash all changes", result.stdout)
                self.assertEqual(self.commands(), self.finish_commands()[:2])

    def test_finish_stops_on_each_git_failure(self) -> None:
        for index, command in enumerate(self.finish_commands()):
            with self.subTest(command=command):
                result = self.run_make(
                    "finish", "BRANCH=codex/example", FAIL_GIT_COMMAND=command.removeprefix("git ")
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.commands(), self.finish_commands()[: index + 1])


@unittest.skipUnless(
    MAKE and GIT and os.name == "posix", "Cleanup tests require POSIX make and Git"
)
class FinishWorkflowGitTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.directory = Path(temporary_directory.name)
        self.remote = self.directory / "remote.git"
        self.repository = self.directory / "repository"
        # Only disposable local repositories are reachable; ignore user Git configuration.
        self.environment = {
            "PATH": os.defpath,
            "HOME": str(self.directory),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ALLOW_PROTOCOL": "file",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "Workflow Tests",
            "GIT_AUTHOR_EMAIL": "workflow@example.invalid",
            "GIT_COMMITTER_NAME": "Workflow Tests",
            "GIT_COMMITTER_EMAIL": "workflow@example.invalid",
        }
        self.git("init", "--bare", "--initial-branch=main", str(self.remote), cwd=self.directory)
        self.git("clone", str(self.remote), str(self.repository), cwd=self.directory)
        shutil.copyfile(MAKEFILE, self.repository / "Makefile")
        self.git("add", "Makefile")
        self.git("commit", "-m", "Initial commit")
        self.git("push", "-u", "origin", "main")
        self.initial_commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("switch", "-c", "codex/example")
        self.git("commit", "--allow-empty", "-m", "Feature commit")
        self.git("push", "-u", "origin", "codex/example")
        self.feature_commit = self.git("rev-parse", "HEAD").stdout.strip()

    def git(
        self, *arguments: str, cwd: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [GIT, *arguments],
            cwd=cwd or self.repository,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=check,
        )

    def publish_merge(self) -> None:
        publisher = self.directory / "publisher"
        self.git("clone", str(self.remote), str(publisher), cwd=self.directory)
        self.git("merge", "--no-ff", "-m", "Merge feature", "origin/codex/example", cwd=publisher)
        self.git("push", "origin", "main", cwd=publisher)
        self.git("push", "origin", "--delete", "codex/example", cwd=publisher)

    def finish(self, branch: str = "codex/example") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [MAKE, "--no-print-directory", "finish", f"BRANCH={branch}"],
            cwd=self.repository,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def assert_branch_present(self, branch: str = "codex/example") -> None:
        self.git("show-ref", "--verify", f"refs/heads/{branch}")

    def assert_branch_absent(self, ref: str) -> None:
        self.assertNotEqual(self.git("show-ref", "--verify", ref, check=False).returncode, 0)

    def test_finish_fast_forwards_main_prunes_and_deletes_merged_branch(self) -> None:
        self.publish_merge()

        result = self.finish()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git("branch", "--show-current").stdout.strip(), "main")
        self.assertEqual(
            self.git("rev-parse", "main").stdout, self.git("rev-parse", "origin/main").stdout
        )
        self.assert_branch_absent("refs/heads/codex/example")
        self.assert_branch_absent("refs/remotes/origin/codex/example")
        self.assertEqual(self.git("status", "--porcelain").stdout, "")

    def test_finish_can_start_on_main(self) -> None:
        self.publish_merge()
        self.git("switch", "main")
        result = self.finish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_branch_absent("refs/heads/codex/example")

    def test_finish_keeps_unmerged_branch_even_when_its_upstream_contains_it(self) -> None:
        result = self.finish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fully merged into origin/main", result.stdout)
        self.assert_branch_present()
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.feature_commit)
        self.assertEqual(self.git("rev-parse", "main").stdout.strip(), self.initial_commit)

    def test_finish_keeps_new_local_commits_after_remote_merge(self) -> None:
        self.publish_merge()
        self.git("commit", "--allow-empty", "-m", "Unmerged follow-up")
        follow_up = self.git("rev-parse", "HEAD").stdout
        self.assertNotEqual(self.finish().returncode, 0)
        self.assert_branch_present()
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, follow_up)

    def test_finish_preserves_untracked_files_and_current_branch(self) -> None:
        self.publish_merge()
        unfinished_file = self.repository / "unfinished.txt"
        unfinished_file.write_text("Keep this work.\n", encoding="utf-8")
        self.assertNotEqual(self.finish().returncode, 0)
        self.assert_branch_present()
        self.assertEqual(self.git("branch", "--show-current").stdout.strip(), "codex/example")
        self.assertEqual(unfinished_file.read_text(encoding="utf-8"), "Keep this work.\n")

    def test_finish_refuses_divergent_main_without_switching(self) -> None:
        self.publish_merge()
        self.git("switch", "main")
        self.git("commit", "--allow-empty", "-m", "Divergent main work")
        local_main = self.git("rev-parse", "main").stdout
        self.git("switch", "codex/example")

        result = self.finish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Local main is missing or has commits", result.stdout)
        self.assert_branch_present()
        self.assertEqual(self.git("rev-parse", "main").stdout, local_main)
        self.assertEqual(self.git("branch", "--show-current").stdout.strip(), "codex/example")

    def test_finish_refuses_main_ahead_of_origin(self) -> None:
        self.publish_merge()
        self.git("fetch", "origin")
        self.git("switch", "main")
        self.git("merge", "--ff-only", "origin/main")
        self.git("commit", "--allow-empty", "-m", "Unpushed main work")
        local_main = self.git("rev-parse", "main").stdout
        self.assertNotEqual(self.finish().returncode, 0)
        self.assert_branch_present()
        self.assertEqual(self.git("rev-parse", "main").stdout, local_main)

    def test_finish_does_not_delete_branch_checked_out_in_another_worktree(self) -> None:
        self.publish_merge()
        self.git("switch", "main")
        worktree = self.directory / "other-worktree"
        self.git("worktree", "add", str(worktree), "codex/example")
        self.assertNotEqual(self.finish().returncode, 0)
        self.assert_branch_present()
        self.assertTrue((worktree / "Makefile").is_file())
        self.assertEqual(
            self.git("rev-parse", "HEAD", cwd=worktree).stdout.strip(), self.feature_commit
        )

    def test_finish_treats_branch_argument_as_data(self) -> None:
        result = self.finish('codex/no"; touch injected; #')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid local branch name", result.stdout)
        self.assertFalse((self.repository / "injected").exists())
        self.assert_branch_present()

    def test_finish_refuses_missing_branch(self) -> None:
        result = self.finish("codex/missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot find local branch", result.stdout)
        self.assert_branch_present()
