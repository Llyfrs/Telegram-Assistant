"""Ephemeral shell execution utilities for the assistant."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ShellResult:
    """Structured output returned after a shell command finishes."""

    command: str
    exit_code: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool
    cwd: str

    def as_dict(self) -> Dict[str, object]:
        """Return a JSON-serialisable representation of the result."""
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "cwd": self.cwd,
        }


class EphemeralShell:
    """Execute commands inside an isolated, temporary workspace.

    The workspace lives in a temporary directory that is discarded whenever the
    process restarts or when :meth:`reset` is called.  Commands run without an
    interactive shell which prevents features such as redirection or chaining
    through ``;``.  Only the command itself is executed which keeps execution
    deterministic and limits the risk of shell injection.
    """

    def __init__(self, *, max_timeout: int = 30, max_command_length: int = 1024):
        self._workspace = tempfile.mkdtemp(prefix="assistant-shell-")
        self._max_timeout = max(1, max_timeout)
        self._max_command_length = max_command_length
        self._base_env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        self._refresh_env()

    def _refresh_env(self) -> None:
        """Update HOME/PWD in the sandboxed environment."""
        self._base_env["HOME"] = self._workspace
        self._base_env["PWD"] = self._workspace

    @property
    def workspace(self) -> str:
        """Return the current workspace path."""
        return self._workspace

    def run(self, command: str, timeout_seconds: Optional[int] = None) -> Dict[str, object]:
        """Execute *command* inside the ephemeral workspace.

        Args:
            command: Command to execute.  The command is tokenised using
                :func:`shlex.split` and therefore must not rely on shell
                features such as redirection.
            timeout_seconds: Optional timeout for the command.  Values above the
                configured maximum are clipped.
        """

        cleaned_command = command.strip()
        if not cleaned_command:
            return ShellResult(
                command="",
                exit_code=None,
                stdout="",
                stderr="No command provided.",
                timed_out=False,
                cwd=self.workspace,
            ).as_dict()

        if len(cleaned_command) > self._max_command_length:
            return ShellResult(
                command=cleaned_command,
                exit_code=None,
                stdout="",
                stderr="Command too long.",
                timed_out=False,
                cwd=self.workspace,
            ).as_dict()

        try:
            args = shlex.split(cleaned_command)
        except ValueError as exc:  # Raised when quotes are not balanced.
            return ShellResult(
                command=cleaned_command,
                exit_code=None,
                stdout="",
                stderr=f"Failed to parse command: {exc}",
                timed_out=False,
                cwd=self.workspace,
            ).as_dict()

        if not args:
            return ShellResult(
                command=cleaned_command,
                exit_code=None,
                stdout="",
                stderr="No executable specified.",
                timed_out=False,
                cwd=self.workspace,
            ).as_dict()

        timeout = timeout_seconds or self._max_timeout
        timeout = min(max(1, timeout), self._max_timeout)

        try:
            completed = subprocess.run(
                args,
                cwd=self.workspace,
                timeout=timeout,
                capture_output=True,
                text=True,
                env=self._base_env,
            )
            result = ShellResult(
                command=cleaned_command,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                cwd=self.workspace,
            )
        except FileNotFoundError:
            result = ShellResult(
                command=cleaned_command,
                exit_code=None,
                stdout="",
                stderr=f"Executable not found: {args[0]}",
                timed_out=False,
                cwd=self.workspace,
            )
        except subprocess.TimeoutExpired as exc:
            result = ShellResult(
                command=cleaned_command,
                exit_code=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                timed_out=True,
                cwd=self.workspace,
            )

        return result.as_dict()

    def list_workspace(self) -> Dict[str, object]:
        """Return a snapshot of files present in the workspace."""
        contents = []
        for root, dirs, files in os.walk(self.workspace):
            relative_root = os.path.relpath(root, self.workspace)
            if relative_root == ".":
                relative_root = ""
            for directory in sorted(dirs):
                path = os.path.join(relative_root, directory).strip("/")
                contents.append({"type": "directory", "path": path or "."})
            for file_name in sorted(files):
                path = os.path.join(relative_root, file_name).strip("/")
                contents.append({"type": "file", "path": path or file_name})
        return {"workspace": self.workspace, "contents": contents}

    def reset(self) -> Dict[str, object]:
        """Reset the workspace by creating a fresh temporary directory."""
        shutil.rmtree(self.workspace, ignore_errors=True)
        self._workspace = tempfile.mkdtemp(prefix="assistant-shell-")
        self._refresh_env()
        return {"status": "reset", "workspace": self.workspace}

    def __del__(self) -> None:  # pragma: no cover - defensive cleanup
        try:
            shutil.rmtree(self.workspace, ignore_errors=True)
        except Exception:
            pass
