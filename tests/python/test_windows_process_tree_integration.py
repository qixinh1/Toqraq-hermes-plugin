"""Real Windows Job Object, process-tree, and output integration tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from toqraq.core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessEnvironmentVariable,
    ProcessLaunch,
    ProcessOutputStream,
    ProcessTree,
)
from toqraq.platforms.windows.process_launcher import WindowsProcessTreeLauncher

from windows_process_support import (
    close_test_handle,
    open_process_for_wait,
    terminate_test_process,
    wait_for,
    wait_handle_ended,
)

pytestmark = [
    pytest.mark.windows,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows Job Objects"),
]

_EMPTY_ENVIRONMENT = ProcessEnvironment(variables=())
_TEST_BOOTSTRAP = ProcessBootstrap(payload=b"integration-bootstrap")
_DIRECT_PYTHON_EXECUTABLE = Path(sys._base_executable)


def _launch_python(
    tmp_path: Path,
    source: str,
    *arguments: str,
    output_limit: int = 64 * 1024,
    output_idle_interval: float | None = None,
    environment: ProcessEnvironment = _EMPTY_ENVIRONMENT,
) -> tuple[WindowsProcessTreeLauncher, ProcessTree]:
    """Launch the direct interpreter process through the real adapter."""
    if output_idle_interval is None:
        launcher = WindowsProcessTreeLauncher(output_character_limit=output_limit)
    else:
        launcher = WindowsProcessTreeLauncher(
            output_character_limit=output_limit,
            output_idle_interval=output_idle_interval,
        )
    tree = launcher.launch(
        ProcessLaunch(
            executable=_DIRECT_PYTHON_EXECUTABLE,
            arguments=("-c", source, *arguments),
            working_directory=tmp_path,
            environment=environment,
            bootstrap=_TEST_BOOTSTRAP,
        )
    )
    return launcher, tree


def test_real_job_owns_and_forcibly_closes_root_and_grandchild(tmp_path: Path) -> None:
    pid_file = tmp_path / "tree-pids.txt"
    source = """
import os
import subprocess
import sys
import time

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
with open(sys.argv[1], "w", encoding="ascii") as output:
    output.write(f"{os.getpid()} {child.pid}")
    output.flush()
print(f"tree-ready {os.getpid()} {child.pid}", flush=True)
time.sleep(120)
"""
    launcher, tree = _launch_python(tmp_path, source, str(pid_file))
    test_handles: list[int] = []
    try:
        published: tuple[int, int] | None = None

        def read_published_pids() -> bool:
            nonlocal published
            try:
                values = tuple(int(value) for value in pid_file.read_text().split())
            except (FileNotFoundError, ValueError):
                return False
            if len(values) != 2:
                return False
            published = (values[0], values[1])
            return True

        wait_for(read_published_pids, 5)
        assert published is not None
        root_pid, child_pid = published
        test_handles.extend((open_process_for_wait(root_pid), open_process_for_wait(child_pid)))

        tree.close(graceful_timeout=0, forced_timeout=5)

        assert root_pid == tree.root_pid
        assert all(wait_handle_ended(handle, 1) for handle in test_handles)
    finally:
        try:
            tree.close(graceful_timeout=0, forced_timeout=5)
        finally:
            try:
                for handle in test_handles:
                    close_test_handle(handle)
            finally:
                launcher.close()


def test_real_kill_on_close_survives_abrupt_launcher_process_exit(tmp_path: Path) -> None:
    pid_file = tmp_path / "kill-on-close-pid.txt"
    release_file = tmp_path / "release-launcher.txt"
    repository = Path(__file__).parents[2]
    helper_source = """
import os
import sys
import time
from pathlib import Path

from toqraq.core.process_tree import ProcessBootstrap, ProcessEnvironment, ProcessLaunch
from toqraq.platforms.windows.process_launcher import WindowsProcessTreeLauncher

pid_file = Path(sys.argv[1])
release_file = Path(sys.argv[2])
tree = WindowsProcessTreeLauncher().launch(
    ProcessLaunch(
        executable=Path(sys.executable),
        arguments=("-c", "import time; time.sleep(120)"),
        working_directory=pid_file.parent,
        environment=ProcessEnvironment(variables=()),
        bootstrap=ProcessBootstrap(payload=b"host-exit-bootstrap"),
    )
)
pid_file.write_text(str(tree.root_pid), encoding="ascii")
deadline = time.monotonic() + 10
while not release_file.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
if not release_file.exists():
    tree.close(graceful_timeout=0, forced_timeout=5)
    raise SystemExit(2)
os._exit(0)
"""
    helper = subprocess.Popen(
        [sys.executable, "-c", helper_source, str(pid_file), str(release_file)],
        cwd=repository,
    )
    process_handle: int | None = None
    try:
        published_pid: int | None = None

        def read_published_pid() -> bool:
            nonlocal published_pid
            try:
                published_pid = int(pid_file.read_text(encoding="ascii"))
            except (FileNotFoundError, ValueError):
                return False
            return True

        wait_for(read_published_pid, 5)
        assert published_pid is not None
        process_handle = open_process_for_wait(published_pid)
        release_file.write_text("release", encoding="ascii")

        assert helper.wait(timeout=5) == 0
        assert wait_handle_ended(process_handle, 5)
    finally:
        if helper.poll() is None:
            helper.kill()
            helper.wait(timeout=5)
        if process_handle is not None:
            if not wait_handle_ended(process_handle, 0):
                terminate_test_process(process_handle)
            close_test_handle(process_handle)


def test_real_window_process_exits_during_graceful_deadline(tmp_path: Path) -> None:
    source = """
import ctypes
import os
from ctypes import wintypes

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.UnregisterClassW.restype = wintypes.BOOL

@WNDPROC
def window_proc(window, message, wparam, lparam):
    if message == WM_CLOSE:
        user32.DestroyWindow(window)
        return 0
    if message == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(window, message, wparam, lparam)

instance = kernel32.GetModuleHandleW(None)
class_name = f"ToqraqProcessTreeTest{os.getpid()}"
window_class = WNDCLASSW()
window_class.lpfnWndProc = window_proc
window_class.hInstance = instance
window_class.lpszClassName = class_name
if not user32.RegisterClassW(ctypes.byref(window_class)):
    raise ctypes.WinError(ctypes.get_last_error())
window = user32.CreateWindowExW(
    0, class_name, "toqraq-test", 0, 0, 0, 64, 64, None, None, instance, None
)
if not window:
    raise ctypes.WinError(ctypes.get_last_error())
print("window-ready", flush=True)
message = wintypes.MSG()
while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
    user32.TranslateMessage(ctypes.byref(message))
    user32.DispatchMessageW(ctypes.byref(message))
user32.UnregisterClassW(class_name, instance)
"""
    launcher, tree = _launch_python(tmp_path, source)
    try:
        wait_for(
            lambda: "window-ready" in "".join(chunk.text for chunk in tree.output().chunks),
            5,
        )

        tree.close(graceful_timeout=5, forced_timeout=5)

        assert tree.poll() == 0, tree.output()
    finally:
        try:
            tree.close(graceful_timeout=0, forced_timeout=5)
        finally:
            launcher.close()


def test_real_output_snapshot_sequences_both_streams(tmp_path: Path) -> None:
    source = """
import sys
print("stdout-evidence", flush=True)
print("stderr-evidence", file=sys.stderr, flush=True)
"""
    launcher, tree = _launch_python(tmp_path, source)
    try:
        assert tree.wait(5) == 0, tree.output()
        tree.close(graceful_timeout=0, forced_timeout=5)
        snapshot = tree.output()

        assert {chunk.stream for chunk in snapshot.chunks} == {
            ProcessOutputStream.STDOUT,
            ProcessOutputStream.STDERR,
        }
        assert tuple(chunk.sequence for chunk in snapshot.chunks) == tuple(
            sorted(chunk.sequence for chunk in snapshot.chunks)
        )
        assert snapshot.failed_streams == frozenset()
    finally:
        try:
            tree.close(graceful_timeout=0, forced_timeout=5)
        finally:
            launcher.close()


def test_real_close_drains_output_while_collector_is_idle(tmp_path: Path) -> None:
    source = """
print("tail-evidence", flush=True)
"""
    launcher, tree = _launch_python(tmp_path, source, output_idle_interval=0.5)
    try:
        assert tree.wait(5) == 0
        tree.close(graceful_timeout=0, forced_timeout=5)

        text = "".join(chunk.text for chunk in tree.output().chunks)
        assert text.splitlines() == ["tail-evidence"]
    finally:
        try:
            tree.close(graceful_timeout=0, forced_timeout=5)
        finally:
            launcher.close()


def test_real_output_snapshot_discards_only_bounded_old_text(tmp_path: Path) -> None:
    output_limit = 128
    source = """
import os
os.write(1, ("discard-" * 1024 + "retained-tail").encode())
"""
    launcher, tree = _launch_python(tmp_path, source, output_limit=output_limit)
    try:
        assert tree.wait(5) == 0
        tree.close(graceful_timeout=0, forced_timeout=5)
        snapshot = tree.output()
        text = "".join(chunk.text for chunk in snapshot.chunks)

        assert len(text) == output_limit
        assert text.endswith("retained-tail")
        assert snapshot.truncated is True
        assert snapshot.next_sequence > 1
    finally:
        try:
            tree.close(graceful_timeout=0, forced_timeout=5)
        finally:
            launcher.close()


def test_real_child_receives_only_explicit_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent_secret_name = "TOQRAQ_PARENT_SECRET_SENTINEL"
    monkeypatch.setenv(parent_secret_name, "must-not-cross-process-boundary")
    environment = ProcessEnvironment(
        variables=(ProcessEnvironmentVariable(name="TOQRAQ_SAFE_VALUE", value="present"),)
    )
    source = f"""
import os
print(os.environ.get({parent_secret_name!r}, 'absent'), flush=True)
print(os.environ.get('TOQRAQ_SAFE_VALUE', 'absent'), flush=True)
"""
    launcher, tree = _launch_python(tmp_path, source, environment=environment)
    try:
        assert tree.wait(5) == 0
        tree.close(graceful_timeout=0, forced_timeout=5)
        text = "".join(chunk.text for chunk in tree.output().chunks)

        assert "must-not-cross-process-boundary" not in text
        assert "absent" in text
        assert "present" in text
    finally:
        try:
            tree.close(graceful_timeout=0, forced_timeout=5)
        finally:
            launcher.close()
