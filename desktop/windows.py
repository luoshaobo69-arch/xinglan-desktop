"""Narrow Win32 helpers. No hooks, titles, document reads, screenshots or IPC."""
from __future__ import annotations

import os


def foreground_process_name() -> str:
    if os.name != "nt":
        return ""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    process_id = wintypes.DWORD()
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if process_id.value == os.getpid():
        return "__self__"
    handle = kernel32.OpenProcess(0x1000, False, process_id.value)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            return buffer.value.rsplit("\\", 1)[-1]
        return ""
    finally:
        kernel32.CloseHandle(handle)


def no_activate(tk_window_id: int) -> None:
    """Only style our own Tk window: a click should not steal the editor's focus."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetParent.argtypes = (wintypes.HWND,)
    user32.GetParent.restype = wintypes.HWND
    parent = user32.GetParent(tk_window_id) or tk_window_id
    get_style = user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.GetWindowLongW
    set_style = user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.SetWindowLongW
    get_style.argtypes = (wintypes.HWND, ctypes.c_int)
    get_style.restype = ctypes.c_ssize_t
    set_style.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
    set_style.restype = ctypes.c_ssize_t
    extended = get_style(parent, -20)
    set_style(parent, -20, extended | 0x08000000 | 0x00000080)  # NOACTIVATE | TOOLWINDOW
