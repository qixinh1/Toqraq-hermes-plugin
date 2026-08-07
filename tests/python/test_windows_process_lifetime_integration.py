"""Real helper lifetime and secret-channel conformance on Windows."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
from ctypes import wintypes
from pathlib import Path

import pytest
from toqraq.core.errors import LaunchError
from toqraq.core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessLaunch,
    ProcessTree,
)
from toqraq.platforms.windows.process_creation import WindowsProcessCreationApi
from toqraq.platforms.windows.process_handles import WindowsHandleApi
from toqraq.platforms.windows.process_jobs import WindowsJobApi
from toqraq.platforms.windows.process_launcher import WindowsProcessTreeLauncher
from toqraq.platforms.windows.process_pipes import WindowsPipeApi
from toqraq.platforms.windows.process_windows import WindowsProcessWindowApi

from windows_process_support import (
    close_test_handle,
    open_process_for_wait,
    terminate_test_process,
    wait_handle_ended,
)

pytestmark = [
    pytest.mark.windows,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows Job Objects"),
]

_ENVIRONMENT = ProcessEnvironment(variables=())


def _command(tmp_path: Path, source: str, bootstrap: bytes) -> ProcessLaunch:
    return ProcessLaunch(
        executable=Path(sys.executable),
        arguments=("-c", source),
        working_directory=tmp_path,
        environment=_ENVIRONMENT,
        bootstrap=ProcessBootstrap(payload=bootstrap),
    )


def test_real_helper_crash_blocks_launch_without_releasing_active_game(tmp_path: Path) -> None:
    launcher = WindowsProcessTreeLauncher()
    tree = launcher.launch(
        _command(tmp_path, "import time; time.sleep(120)", b"helper-crash-bootstrap")
    )
    helper_handle: int | None = None
    game_handle = open_process_for_wait(tree.root_pid)
    try:
        helper_pid = launcher.parent_process_id
        assert helper_pid is not None
        helper_handle = open_process_for_wait(helper_pid)
        terminate_test_process(helper_handle)
        assert wait_handle_ended(helper_handle, 5)
        assert not wait_handle_ended(game_handle, 0)

        with pytest.raises(LaunchError):
            launcher.launch(_command(tmp_path, "pass", b"must-not-launch"))

        assert not wait_handle_ended(game_handle, 0)
        tree.close(graceful_timeout=0, forced_timeout=5)
        replacement = launcher.launch(_command(tmp_path, "pass", b"replacement-bootstrap"))
        try:
            assert replacement.wait(5) == 0, replacement.output()
        finally:
            replacement.close(graceful_timeout=0, forced_timeout=5)
    finally:
        try:
            tree.close(graceful_timeout=0, forced_timeout=5)
        finally:
            try:
                launcher.close()
            finally:
                close_test_handle(game_handle)
                if helper_handle is not None:
                    close_test_handle(helper_handle)


class _CoordinatedHandles(WindowsHandleApi):
    """Pause after the bootstrap read handle reaches the helper table."""

    def __init__(self) -> None:
        """Create one deterministic launch-concurrency observation point."""
        super().__init__()
        self.remote_ready = threading.Event()
        self.release = threading.Event()
        self.local_bootstrap_read: int | None = None
        self.remote_bootstrap_read: int | None = None
        self._duplicates = 0

    def duplicate_into(self, source: int, target_process: int) -> int:
        """Pause only the first, bootstrap-bearing remote duplication."""
        remote = super().duplicate_into(source, target_process)
        self._duplicates += 1
        if self._duplicates == 1:
            self.local_bootstrap_read = source
            self.remote_bootstrap_read = remote
            self.remote_ready.set()
            if not self.release.wait(5):
                raise TimeoutError("bootstrap concurrency observer was not released")
        return remote


def test_real_bootstrap_reaches_only_target_child_stdin(tmp_path: Path) -> None:
    bootstrap = b"B" * 4096
    handles = _CoordinatedHandles()
    launcher = WindowsProcessTreeLauncher(
        handles=handles,
        jobs=WindowsJobApi(),
        pipes=WindowsPipeApi(),
        creation=WindowsProcessCreationApi(),
        windows=WindowsProcessWindowApi(),
    )
    result: list[ProcessTree] = []
    failures: list[BaseException] = []

    def launch_target() -> None:
        try:
            result.append(
                launcher.launch(
                    _command(
                        tmp_path,
                        "import sys; print(sys.stdin.buffer.read().hex(), flush=True)",
                        bootstrap,
                    )
                )
            )
        except BaseException as exc:
            failures.append(exc)

    launch_thread = threading.Thread(target=launch_target, name="bootstrap-launch-test")
    tree: ProcessTree | None = None
    try:
        launch_thread.start()
        try:
            assert handles.remote_ready.wait(5)
            local_read = handles.local_bootstrap_read
            assert local_read is not None
            assert handles.is_inheritable(local_read) is False
            scanner_source = r"""
import ctypes
import sys
from ctypes import wintypes

handle = int(sys.argv[1])
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
peek = kernel32.PeekNamedPipe
peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                 ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                 ctypes.POINTER(wintypes.DWORD)]
peek.restype = wintypes.BOOL
read = kernel32.ReadFile
read.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                 ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
read.restype = wintypes.BOOL
available = wintypes.DWORD()
payload = b""
if peek(handle, None, 0, None, ctypes.byref(available), None) and available.value:
    buffer = ctypes.create_string_buffer(available.value)
    count = wintypes.DWORD()
    if read(handle, buffer, available.value, ctypes.byref(count), None):
        payload = bytes(buffer.raw[:count.value])
print(payload.hex())
"""
            unrelated = subprocess.check_output(
                [sys.executable, "-c", scanner_source, str(local_read)],
                close_fds=False,
                timeout=5,
                text=True,
            )
            assert bootstrap.hex() not in unrelated
        finally:
            handles.release.set()
            launch_thread.join(10)
        assert not launch_thread.is_alive()
        assert failures == []
        assert len(result) == 1
        tree = result[0]
        assert tree.wait(5) == 0, tree.output()
        tree.close(graceful_timeout=0, forced_timeout=5)
        output = "".join(chunk.text for chunk in tree.output().chunks)
        assert bootstrap.hex() in output
        with pytest.raises(OSError):
            handles.is_inheritable(local_read)
    finally:
        try:
            if tree is not None:
                tree.close(graceful_timeout=0, forced_timeout=5)
        finally:
            launcher.close()


def test_real_repeated_launches_do_not_grow_main_handle_count(tmp_path: Path) -> None:
    launcher = WindowsProcessTreeLauncher()
    warm = launcher.launch(_command(tmp_path, "pass", b"warm-bootstrap"))
    warm.wait(5)
    warm.close(graceful_timeout=0, forced_timeout=5)
    # Closed trees remain safe to inspect, so their Python synchronization
    # objects live until the caller releases the tree reference.
    del warm
    baseline = _current_process_handle_count()
    try:
        for index in range(25):
            tree = launcher.launch(_command(tmp_path, "pass", f"bootstrap-{index}".encode("ascii")))
            tree.wait(5)
            tree.close(graceful_timeout=0, forced_timeout=5)
            del tree
        assert _current_process_handle_count() == baseline
    finally:
        launcher.close()


def _current_process_handle_count() -> int:
    """Return the current test process handle count from Kernel32."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    current = kernel32.GetCurrentProcess
    current.argtypes = []
    current.restype = wintypes.HANDLE
    count_handles = kernel32.GetProcessHandleCount
    count_handles.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    count_handles.restype = wintypes.BOOL
    count = wintypes.DWORD()
    if not count_handles(current(), ctypes.byref(count)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(count.value)
