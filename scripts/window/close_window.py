"""Close a window by hwnd: graceful WM_CLOSE first, optional process-exit wait and force-kill fallback.

Sends WM_CLOSE to the window (same as clicking the X / Alt+F4). If the window
is still alive after --grace-ms, exits 2 unless --force is set. When
--wait-process-ms is set, also waits for the owning process to exit after the
window closes; if it remains alive, exits 2 or terminates it when --force is set.

Exit codes:
  0  closed cleanly
  1  hwnd does not exist
  2  window or process still alive after its timeout and --force not set
  3  bad usage / unexpected error
"""
import argparse, ctypes, sys, time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_CLOSE = 0x0010
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259

user32.IsWindow.argtypes = [wintypes.HWND]; user32.IsWindow.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def owning_pid(hwnd):
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_alive(pid):
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        exit_code = wintypes.DWORD(0)
        if not kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(h)


def force_kill(pid, exit_code=1):
    h = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not h:
        raise OSError(f"OpenProcess(TERMINATE, pid={pid}) failed "
                      f"(error {ctypes.get_last_error()})")
    try:
        if not kernel32.TerminateProcess(h, exit_code):
            raise OSError(f"TerminateProcess(pid={pid}) failed "
                          f"(error {ctypes.get_last_error()})")
    finally:
        kernel32.CloseHandle(h)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("hwnd", type=lambda s: int(s, 0))
    p.add_argument("--grace-ms", dest="grace_ms", type=int, default=2000,
                   help="how long to wait for WM_CLOSE to take effect (default 2000)")
    p.add_argument("--poll-ms", dest="poll_ms", type=int, default=100)
    p.add_argument("--wait-process-ms", dest="wait_process_ms", type=int, default=0,
                   help="after the window closes, wait this long for its process to exit")
    p.add_argument("--force", action="store_true",
                   help="TerminateProcess the owning pid if WM_CLOSE doesn't work")
    a = p.parse_args()

    if not user32.IsWindow(a.hwnd):
        print(f"ERROR: hwnd {a.hwnd} does not exist", file=sys.stderr); sys.exit(1)

    pid = owning_pid(a.hwnd)
    if not pid:
        print(f"ERROR: could not resolve owning pid for hwnd {a.hwnd}", file=sys.stderr); sys.exit(3)

    if not user32.PostMessageW(a.hwnd, WM_CLOSE, 0, 0):
        print(f"ERROR: PostMessage(WM_CLOSE) failed "
              f"(error {ctypes.get_last_error()})", file=sys.stderr); sys.exit(3)

    deadline = time.time() + a.grace_ms / 1000.0
    interval = max(a.poll_ms, 0) / 1000.0
    window_closed = False
    while time.time() < deadline:
        if not user32.IsWindow(a.hwnd):
            window_closed = True
            break
        if not process_alive(pid):
            print(f"closed hwnd={a.hwnd} pid={pid} via WM_CLOSE")
            return
        time.sleep(interval)

    if not window_closed:
        if not a.force:
            print(f"window {a.hwnd} (pid {pid}) still alive after {a.grace_ms}ms "
                  f"and --force not set", file=sys.stderr); sys.exit(2)

        try:
            force_kill(pid)
        except OSError as e:
            print(f"ERROR: force kill failed: {e}", file=sys.stderr); sys.exit(3)
        print(f"force-killed hwnd={a.hwnd} pid={pid} after WM_CLOSE timeout")
        return

    if a.wait_process_ms <= 0:
        suffix = "" if not process_alive(pid) else " (process still alive)"
        print(f"closed hwnd={a.hwnd} pid={pid} via WM_CLOSE{suffix}")
        return

    process_deadline = time.time() + a.wait_process_ms / 1000.0
    while time.time() < process_deadline:
        if not process_alive(pid):
            print(f"closed hwnd={a.hwnd} pid={pid} via WM_CLOSE; process exited")
            return
        time.sleep(interval)

    if not a.force:
        print(f"window {a.hwnd} closed but pid {pid} still alive after "
              f"{a.wait_process_ms}ms and --force not set", file=sys.stderr); sys.exit(2)

    if not process_alive(pid):
        print(f"closed hwnd={a.hwnd} pid={pid} via WM_CLOSE; process exited")
        return

    try:
        force_kill(pid)
    except OSError as e:
        if not process_alive(pid):
            print(f"closed hwnd={a.hwnd} pid={pid} via WM_CLOSE; process exited")
            return
        print(f"ERROR: force kill failed: {e}", file=sys.stderr); sys.exit(3)
    print(f"closed hwnd={a.hwnd}; force-killed pid={pid} after process-exit timeout")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(3)
