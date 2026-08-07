"""Atomic Win32 helper and game process creation."""

from __future__ import annotations

import ctypes
import subprocess
from collections.abc import Callable
from ctypes import wintypes
from types import TracebackType

from ...core.process_tree import ProcessEnvironment, ProcessLaunch
from . import process_abi as abi
from .process_errors import handle_value, raise_last_error, raise_windows_error
from .process_types import NativeCommand, NativeHandle, NativeProcess

_MAX_ENVIRONMENT_BLOCK_CHARACTERS = 32_767


class WindowsProcessCreationApi:
    """Create processes with their complete ownership attributes in one call."""

    def __init__(self) -> None:
        """Bind attribute-list and process-creation functions."""
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._initialize_attributes = kernel32.InitializeProcThreadAttributeList
        self._initialize_attributes.argtypes = [
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self._initialize_attributes.restype = wintypes.BOOL
        self._update_attribute = kernel32.UpdateProcThreadAttribute
        self._update_attribute.argtypes = [
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.c_size_t,
            wintypes.LPVOID,
            ctypes.c_size_t,
            wintypes.LPVOID,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self._update_attribute.restype = wintypes.BOOL
        self._delete_attributes = kernel32.DeleteProcThreadAttributeList
        self._delete_attributes.argtypes = [wintypes.LPVOID]
        self._delete_attributes.restype = None
        self._create_process = kernel32.CreateProcessW
        self._create_process.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPCWSTR,
            ctypes.POINTER(abi.StartupInfo),
            ctypes.POINTER(abi.ProcessInformation),
        ]
        self._create_process.restype = wintypes.BOOL

    def create_helper(self, command: NativeCommand, *, lifetime_job: NativeHandle) -> NativeProcess:
        """Create the non-inheriting helper atomically inside its lifetime job."""
        jobs = (wintypes.HANDLE * 1)(lifetime_job)
        with self._attribute_list(1) as attributes:
            attributes.add(abi.PROC_THREAD_ATTRIBUTE_JOB_LIST, jobs)
            startup = _startup(attributes.pointer)
            return self._create(
                command,
                startup=startup,
                inherit_handles=False,
                extra_flags=abi.CREATE_NO_WINDOW,
            )

    def create_child(
        self,
        command: ProcessLaunch,
        *,
        parent_process: NativeHandle,
        session_job: NativeHandle,
        stdin_read: NativeHandle,
        stdout_write: NativeHandle,
        stderr_write: NativeHandle,
    ) -> NativeProcess:
        """Create a running child already owned by parent and session jobs."""
        parent = wintypes.HANDLE(parent_process)
        handles = (wintypes.HANDLE * 3)(stdin_read, stdout_write, stderr_write)
        jobs = (wintypes.HANDLE * 1)(session_job)
        with self._attribute_list(3) as attributes:
            attributes.add(abi.PROC_THREAD_ATTRIBUTE_PARENT_PROCESS, parent)
            attributes.add(abi.PROC_THREAD_ATTRIBUTE_HANDLE_LIST, handles)
            attributes.add(abi.PROC_THREAD_ATTRIBUTE_JOB_LIST, jobs)
            startup = _startup(attributes.pointer)
            startup.StartupInfo.dwFlags = abi.STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput = stdin_read
            startup.StartupInfo.hStdOutput = stdout_write
            startup.StartupInfo.hStdError = stderr_write
            native_command = NativeCommand(
                executable=command.executable,
                arguments=command.arguments,
                working_directory=command.working_directory,
                environment=command.environment,
            )
            # The helper has no console. This prevents console-subsystem
            # children from inheriting an unusable console attachment; Windows
            # ignores the flag for GUI-subsystem engine executables.
            return self._create(
                native_command,
                startup=startup,
                inherit_handles=True,
                extra_flags=abi.CREATE_NO_WINDOW,
            )

    def _create(
        self,
        command: NativeCommand,
        *,
        startup: abi.StartupInfoEx,
        inherit_handles: bool,
        extra_flags: int,
    ) -> NativeProcess:
        environment = _environment_block(command.environment)
        command_line = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(command.executable), *command.arguments])
        )
        information = abi.ProcessInformation()
        flags = abi.CREATE_UNICODE_ENVIRONMENT | abi.EXTENDED_STARTUPINFO_PRESENT | extra_flags
        if not self._create_process(
            str(command.executable),
            command_line,
            None,
            None,
            inherit_handles,
            flags,
            ctypes.cast(environment, wintypes.LPVOID),
            str(command.working_directory),
            ctypes.byref(startup.StartupInfo),
            ctypes.byref(information),
        ):
            raise_last_error()
        return NativeProcess(
            process=handle_value(information.hProcess),
            thread=handle_value(information.hThread),
            pid=int(information.dwProcessId),
        )

    def _attribute_list(self, count: int) -> _AttributeList:
        return _AttributeList(
            count,
            initialize=self._initialize_attributes,
            update=self._update_attribute,
            delete=self._delete_attributes,
        )


class _AttributeList:
    """Bound one initialized PROC_THREAD_ATTRIBUTE_LIST lifetime."""

    def __init__(
        self,
        count: int,
        *,
        initialize: Callable[..., int],
        update: Callable[..., int],
        delete: Callable[[object], None],
    ) -> None:
        self._count = count
        self._initialize = initialize
        self._update = update
        self._delete = delete
        self._buffer: ctypes.Array[ctypes.c_char] | None = None

    @property
    def pointer(self) -> wintypes.LPVOID:
        if self._buffer is None:
            raise RuntimeError("process attribute list is not initialized")
        return ctypes.cast(self._buffer, wintypes.LPVOID)

    def __enter__(self) -> _AttributeList:
        size = ctypes.c_size_t()
        ctypes.set_last_error(0)
        self._initialize(None, self._count, 0, ctypes.byref(size))
        error = ctypes.get_last_error()
        if error != abi.ERROR_INSUFFICIENT_BUFFER or not size.value:
            raise_windows_error(error)
        self._buffer = ctypes.create_string_buffer(size.value)
        if not self._initialize(self._buffer, self._count, 0, ctypes.byref(size)):
            raise_last_error()
        return self

    def add(
        self,
        attribute: int,
        value: ctypes.Array[ctypes.c_void_p] | ctypes.c_void_p,
    ) -> None:
        """Add one input attribute while its ctypes value remains in scope."""
        if not self._update(
            self.pointer,
            0,
            attribute,
            ctypes.byref(value),
            ctypes.sizeof(value),
            None,
            None,
        ):
            raise_last_error()

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._buffer is not None:
            self._delete(self._buffer)
            self._buffer = None


def _startup(attributes: wintypes.LPVOID) -> abi.StartupInfoEx:
    startup = abi.StartupInfoEx()
    startup.StartupInfo.cb = ctypes.sizeof(startup)
    startup.lpAttributeList = attributes
    return startup


def _environment_block(environment: ProcessEnvironment) -> ctypes.Array[ctypes.c_wchar]:
    """Build a double-NUL-terminated sorted Unicode environment block."""
    entries = tuple(
        f"{variable.name}={variable.value}"
        for variable in sorted(environment.variables, key=lambda item: item.name.casefold())
    )
    text = "\0".join(entries) + "\0\0"
    if len(text) > _MAX_ENVIRONMENT_BLOCK_CHARACTERS:
        raise ValueError("process environment block is too large")
    block = (ctypes.c_wchar * len(text))()
    block[:] = list(text)
    return block
