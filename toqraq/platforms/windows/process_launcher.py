"""Atomic Windows process launch and process-local ownership guardian."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from ...core.errors import LaunchError, ProcessTerminationError
from ...core.process_tree import ProcessEnvironment, ProcessLaunch
from .process_creation import WindowsProcessCreationApi
from .process_handles import WindowsHandleApi
from .process_jobs import WindowsJobApi
from .process_output import WindowsProcessOutput
from .process_parent import WindowsLaunchParent
from .process_pipes import WindowsPipeApi
from .process_transaction import (
    LaunchTransaction,
    _CreationApi,
    _HandleApi,
    _JobApi,
    _OutputFactory,
    _PipeApi,
    _WindowApi,
)
from .process_tree import WindowsProcessTree, _require_timeout
from .process_types import NativeCommand
from .process_windows import WindowsProcessWindowApi

DEFAULT_OUTPUT_CHARACTER_LIMIT = 64 * 1024
DEFAULT_OUTPUT_READ_SIZE = 4 * 1024
DEFAULT_OUTPUT_IDLE_INTERVAL_SECONDS = 0.01
DEFAULT_ROLLBACK_TIMEOUT_SECONDS = 2.0


class WindowsProcessTreeLauncher:
    """Launch atomically and retain one owner for every native acquisition."""

    def __init__(
        self,
        *,
        handles: _HandleApi | None = None,
        jobs: _JobApi | None = None,
        pipes: _PipeApi | None = None,
        creation: _CreationApi | None = None,
        windows: _WindowApi | None = None,
        helper_command: NativeCommand | None = None,
        output_factory: _OutputFactory = WindowsProcessOutput,
        output_character_limit: int = DEFAULT_OUTPUT_CHARACTER_LIMIT,
        output_read_size: int = DEFAULT_OUTPUT_READ_SIZE,
        output_idle_interval: float = DEFAULT_OUTPUT_IDLE_INTERVAL_SECONDS,
        rollback_timeout: float = DEFAULT_ROLLBACK_TIMEOUT_SECONDS,
    ) -> None:
        """Compose explicit native capabilities and bounded process policy."""
        if isinstance(output_character_limit, bool) or output_character_limit < 1:
            raise ValueError("process output character limit is invalid")
        if isinstance(output_read_size, bool) or output_read_size < 1:
            raise ValueError("process output read size is invalid")
        _require_timeout(output_idle_interval, allow_zero=False)
        _require_timeout(rollback_timeout)
        supplied = (handles, jobs, pipes, creation, windows)
        if any(item is None for item in supplied):
            if any(item is not None for item in supplied):
                raise ValueError("Windows process dependencies must be supplied together")
            _require_supported_windows()
            handles = WindowsHandleApi()
            jobs = WindowsJobApi()
            pipes = WindowsPipeApi()
            creation = WindowsProcessCreationApi()
            windows = WindowsProcessWindowApi()
        assert handles is not None
        assert jobs is not None
        assert pipes is not None
        assert creation is not None
        assert windows is not None
        self._handles = handles
        self._jobs = jobs
        self._pipes = pipes
        self._creation = creation
        self._windows = windows
        self._output_factory = output_factory
        self._output_character_limit = output_character_limit
        self._output_read_size = output_read_size
        self._output_idle_interval = output_idle_interval
        self._rollback_timeout = rollback_timeout
        self._parent = WindowsLaunchParent(
            handles,
            jobs,
            creation,
            command=helper_command or _default_helper_command(),
            cleanup_timeout=rollback_timeout,
        )
        self._pending: list[LaunchTransaction] = []
        self._active: list[WindowsProcessTree] = []
        self._ownership_lock = threading.RLock()

    @property
    def parent_process_id(self) -> int | None:
        """Return the helper PID for diagnostics and conformance tests."""
        return self._parent.pid

    def launch(self, command: ProcessLaunch) -> WindowsProcessTree:
        """Create a running root already owned by both required jobs."""
        with self._ownership_lock:
            try:
                self._retry_failed_launches()
            except ProcessTerminationError as exc:
                raise LaunchError(
                    details={"reason": "previous_launch_cleanup_failed", "retryable": True},
                    cause=exc,
                ) from exc
            try:
                validated = _validated_command(command)
                self._parent.ensure_ready()
            except Exception as exc:
                raise LaunchError(
                    details={"reason": "windows_launch_precondition_failed"},
                    cause=exc,
                ) from exc
            transaction = LaunchTransaction(
                self._handles,
                self._jobs,
                self._pipes,
                self._creation,
                self._parent,
                rollback_timeout=self._rollback_timeout,
            )
            self._pending.append(transaction)
            try:
                transaction.prepare(
                    validated,
                    output_factory=self._output_factory,
                    output_character_limit=self._output_character_limit,
                    output_read_size=self._output_read_size,
                    output_idle_interval=self._output_idle_interval,
                )
                tree = transaction.commit(
                    self._windows,
                    on_released=self._forget_tree,
                )
                self._active.append(tree)
                transaction.mark_transferred()
                self._pending.remove(transaction)
                return tree
            except Exception as exc:
                transaction.rollback()
                if transaction.empty:
                    self._pending.remove(transaction)
                raise LaunchError(
                    details={"reason": "windows_process_tree_launch_failed"},
                    cause=exc,
                ) from exc

    def close(self) -> None:
        """Terminate active trees and retry every retained launch owner."""
        with self._ownership_lock:
            failures: list[Exception] = []
            for tree in tuple(self._active):
                try:
                    tree.close(graceful_timeout=0, forced_timeout=self._rollback_timeout)
                except ProcessTerminationError as exc:
                    failures.append(exc)
            try:
                self._retry_failed_launches()
            except ProcessTerminationError as exc:
                failures.append(exc)
            if not self._active and not self._pending:
                try:
                    self._parent.close()
                except (OSError, TimeoutError) as exc:
                    failures.append(exc)
            if failures or self._active or self._pending:
                cause = failures[0] if failures else OSError("launcher resources remain owned")
                raise ProcessTerminationError(
                    details={"reason": "windows_launcher_cleanup_failed", "retryable": True},
                    cause=cause,
                ) from cause

    def _retry_failed_launches(self) -> None:
        retained: list[LaunchTransaction] = []
        failures: list[Exception] = []
        for transaction in self._pending:
            if transaction.transferred:
                continue
            try:
                transaction.rollback()
            except Exception as exc:
                failures.append(exc)
            if not transaction.empty:
                retained.append(transaction)
        self._pending = retained
        if retained or failures:
            cause = failures[0] if failures else None
            raise ProcessTerminationError(
                details={"reason": "failed_launch_cleanup_retained", "retryable": True},
                cause=cause,
            ) from cause

    def _forget_tree(self, tree: WindowsProcessTree) -> None:
        with self._ownership_lock:
            if tree in self._active:
                self._active.remove(tree)


def _validated_command(command: ProcessLaunch) -> ProcessLaunch:
    """Resolve native filesystem inputs before acquiring resources."""
    executable = command.executable.resolve(strict=True)
    working_directory = command.working_directory.resolve(strict=True)
    if not executable.is_file():
        raise OSError("managed executable is not a file")
    if not working_directory.is_dir():
        raise OSError("process working directory is not a directory")
    return ProcessLaunch(
        executable=Path(executable),
        arguments=command.arguments,
        working_directory=Path(working_directory),
        environment=command.environment,
        bootstrap=command.bootstrap,
    )


def _default_helper_command() -> NativeCommand:
    """Build the isolated helper invocation from this installed plugin."""
    executable = Path(sys.executable).resolve(strict=True)
    script = Path(__file__).with_name("process_helper.py").resolve(strict=True)
    return NativeCommand(
        executable=executable,
        arguments=("-I", str(script), str(os.getpid())),
        working_directory=script.parent,
        environment=ProcessEnvironment(variables=()),
    )


def _require_supported_windows() -> None:
    """Reject platforms without atomic PROC_THREAD_ATTRIBUTE_JOB_LIST."""
    if sys.platform != "win32":
        raise OSError("Windows process ownership requires Windows")
    version = sys.getwindowsversion()
    if version.major < 10:
        raise OSError("Windows process ownership requires Windows 10 or Server 2016")
