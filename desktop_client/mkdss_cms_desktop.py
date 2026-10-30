"""Windows desktop shell for the central MKDSS Compliance Management System.

This is a LAN client only. It does not start Django, copy the database, or store
user credentials. Authentication and permissions remain on the central server.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import Tk, StringVar, messagebox, ttk
from urllib.parse import urlsplit, urlunsplit

APP_NAME = "MKDSS Compliance Management System"
CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "MKDSS" / "CMSDesktop"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_URL = ""


def resource_path(relative_path: str) -> Path:
    """Return a resource path for both source runs and PyInstaller builds."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    base_dir = Path(bundle_dir) if bundle_dir else Path(__file__).resolve().parents[1]
    return base_dir / relative_path


APP_ICON = resource_path("assets/mkdss_icon.ico")
_WINDOW_ICON_HANDLE = None  # Keep the native icon alive for the lifetime of the process.


def set_tk_window_icon(root: Tk) -> None:
    """Apply the application icon to the initial server-configuration dialogs."""
    try:
        if APP_ICON.is_file():
            root.iconbitmap(default=str(APP_ICON))
    except Exception:
        # A missing/unsupported icon must never prevent the desktop client opening.
        pass


def apply_webview_window_icon() -> None:
    """Set the native Windows WebView window and taskbar icons."""
    global _WINDOW_ICON_HANDLE
    if os.name != "nt" or not APP_ICON.is_file():
        return

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        current_pid = kernel32.GetCurrentProcessId()

        user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.LoadImageW.restype = ctypes.c_void_p
        icon_handle = user32.LoadImageW(None, str(APP_ICON), IMAGE_ICON, 0, 0,
                                        LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not icon_handle:
            return
        _WINDOW_ICON_HANDLE = icon_handle

        enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        found = {"value": False}

        user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]

        def visit(hwnd, _lparam):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value != current_pid or not user32.IsWindowVisible(hwnd):
                return True
            title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title, len(title))
            if title.value != APP_NAME:
                return True
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, icon_handle)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, icon_handle)
            found["value"] = True
            return False

        callback = enum_windows_proc(visit)
        # pywebview creates its native window after its GUI loop starts.
        for _ in range(80):
            user32.EnumWindows(callback, 0)
            if found["value"]:
                return
            time.sleep(0.25)
    except Exception:
        # Icon integration is cosmetic; do not interrupt access to the CMS.
        return


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Enter the central CMS server address, for example http://10.1.200.3:8000/")
    if "://" not in value:
        value = "http://" + value
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("The server address must begin with http:// or https://.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Enter a valid server address without a username or password.")
    if parsed.query or parsed.fragment:
        raise ValueError("Do not include query strings or fragments in the server address.")
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def load_url() -> str | None:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return normalize_url(str(data.get("server_url", "")))
    except (OSError, ValueError, json.JSONDecodeError, AttributeError):
        return None


def save_url(url: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"server_url": url}, indent=2), encoding="utf-8")


def probe_server(url: str) -> tuple[bool, str]:
    target = url.rstrip("/") + "/login/"
    request = urllib.request.Request(target, headers={"User-Agent": "MKDSS-CMS-Desktop/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            if response.status < 500:
                return True, f"Server responded with HTTP {response.status}."
            return False, f"The server returned HTTP {response.status}."
    except urllib.error.HTTPError as exc:
        # 4xx can still confirm reachability (for example, a host/CSRF configuration issue).
        if exc.code < 500:
            return True, f"Server is reachable (HTTP {exc.code}); check server host configuration if the page fails."
        return False, f"The server returned HTTP {exc.code}."
    except Exception as exc:
        return False, f"Could not reach {target}. Check the server address, LAN connection, and firewall.\n\nDetails: {exc}"


def configure_dialog(initial: str = "") -> str | None:
    root = Tk()
    root.title("Connect to MKDSS CMS")
    set_tk_window_icon(root)
    root.resizable(False, False)
    root.geometry("540x205")
    root.attributes("-topmost", True)
    result: dict[str, str | None] = {"url": None}
    value = StringVar(value=initial or DEFAULT_URL)

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="MKDSS Compliance Management System", font=("Segoe UI", 12, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Enter the central server address. Do not enter a username or password here.").pack(anchor="w", pady=(8, 6))
    entry = ttk.Entry(frame, textvariable=value, width=66)
    entry.pack(fill="x")
    entry.focus_set()
    status = ttk.Label(frame, text="Example: http://10.1.200.3:8000/", foreground="#555555")
    status.pack(anchor="w", pady=(5, 10))

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")

    def connect() -> None:
        try:
            url = normalize_url(value.get())
        except ValueError as exc:
            messagebox.showerror("Invalid server address", str(exc), parent=root)
            return
        ok, info = probe_server(url)
        if not ok:
            if not messagebox.askyesno("Server not reachable", info + "\n\nSave this address and try opening it anyway?", parent=root):
                return
        save_url(url)
        result["url"] = url
        root.destroy()

    ttk.Button(buttons, text="Connect", command=connect).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=root.destroy).pack(side="right", padx=(0, 8))
    root.bind("<Return>", lambda _event: connect())
    root.mainloop()
    return result["url"]


def main() -> int:
    configure = "--configure" in sys.argv[1:]
    url = None if configure else load_url()
    if not url:
        url = configure_dialog(load_url() or "")
        if not url:
            return 0

    reachable, detail = probe_server(url)
    if not reachable:
        root = Tk()
        set_tk_window_icon(root)
        root.withdraw()
        change = messagebox.askyesno(
            "Cannot reach MKDSS CMS",
            detail + "\n\nWould you like to change the server address?",
            parent=root,
        )
        root.destroy()
        if change:
            url = configure_dialog(url)
            if not url:
                return 0
        else:
            return 1

    try:
        import webview
    except ImportError:
        root = Tk()
        set_tk_window_icon(root)
        root.withdraw()
        messagebox.showerror(
            "Desktop components missing",
            "The desktop runtime is not installed. Rebuild using build_windows.bat, or install the desktop requirements.",
            parent=root,
        )
        root.destroy()
        return 2

    # Enable WebView2 downloads. pywebview's Windows backend then presents a
    # native Save As dialog and writes the response body to the selected path.
    # Without this setting, pywebview cancels every download by default.
    webview.settings['ALLOW_DOWNLOADS'] = True

    webview.create_window(
        APP_NAME,
        url,
        width=1440,
        height=920,
        min_size=(1024, 700),
        text_select=True,
        confirm_close=True,
    )
    # pywebview uses the installed Microsoft Edge WebView2 runtime on Windows.
    # Set the native window icon once pywebview has created its HWND.
    if os.name == "nt":
        threading.Thread(target=apply_webview_window_icon, daemon=True).start()
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
