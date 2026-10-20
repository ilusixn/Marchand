import ctypes
import sys
import threading
from ctypes import wintypes as w

WM_USER, WM_NULL, WM_DESTROY, WM_CLOSE, WM_COMMAND = 0x400, 0, 2, 0x10, 0x111
WM_TRAY = WM_USER + 1
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x202, 0x203, 0x205
NIM_ADD, NIM_DELETE = 0, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
ID_OPEN, ID_COFFEE, ID_QUIT = 1001, 1002, 1003
LRESULT = ctypes.c_ssize_t


class GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT), ("uFlags", w.UINT), ("uCallbackMessage", w.UINT), ("hIcon", w.HICON),
                ("szTip", w.WCHAR * 128), ("dwState", w.DWORD), ("dwStateMask", w.DWORD), ("szInfo", w.WCHAR * 256), ("uVersion", w.UINT),
                ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD), ("guidItem", GUID), ("hBalloonIcon", w.HICON)]


class Tray:
    def __init__(self, icon_path, tip, on_open, on_coffee, on_quit):
        self.icon_path, self.tip = icon_path, tip
        self.on_open, self.on_coffee, self.on_quit = on_open, on_coffee, on_quit
        self.hwnd = None
        self.ready = threading.Event()
        self.ok = False

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()
        self.ready.wait(5)
        return self.ok

    def stop(self):
        if self.hwnd:
            ctypes.windll.user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)

    def run(self):
        u, s = ctypes.windll.user32, ctypes.windll.shell32
        u.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        u.DefWindowProcW.restype = LRESULT
        u.CreateWindowExW.restype = w.HWND
        u.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
        u.LoadImageW.restype = w.HANDLE
        u.LoadImageW.argtypes = [w.HINSTANCE, w.LPCWSTR, w.UINT, ctypes.c_int, ctypes.c_int, w.UINT]
        u.CreatePopupMenu.restype = w.HMENU
        u.TrackPopupMenu.argtypes = [w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.LPVOID]
        u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        taskbar_created = u.RegisterWindowMessageW("TaskbarCreated")
        size = u.GetSystemMetrics(49) or 16
        icon = u.LoadImageW(None, self.icon_path, 1, size, size, 0x10)
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = icon
        nid.szTip = self.tip

        def add():
            nid.hWnd = self.hwnd
            return bool(s.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))

        def menu():
            m = u.CreatePopupMenu()
            u.AppendMenuW(m, 0, ID_OPEN, "Open Marchand Studio")
            u.AppendMenuW(m, 0, ID_COFFEE, "Buy me a coffee")
            u.AppendMenuW(m, 0x800, 0, None)
            u.AppendMenuW(m, 0, ID_QUIT, "Quit Marchand Studio")
            pt = w.POINT()
            u.GetCursorPos(ctypes.byref(pt))
            u.SetForegroundWindow(self.hwnd)
            u.TrackPopupMenu(m, 0x0002 | 0x0020, pt.x, pt.y, 0, self.hwnd, None)
            u.PostMessageW(self.hwnd, WM_NULL, 0, 0)
            u.DestroyMenu(m)

        def call(fn):
            threading.Thread(target=fn, daemon=True).start()

        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

        def proc(hwnd, msg, wp, lp):
            if msg == WM_TRAY:
                if lp in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    call(self.on_open)
                elif lp == WM_RBUTTONUP:
                    menu()
                return 0
            if msg == WM_COMMAND:
                cid = wp & 0xFFFF
                call({ID_OPEN: self.on_open, ID_COFFEE: self.on_coffee, ID_QUIT: self.on_quit}.get(cid, lambda: None))
                return 0
            if msg == taskbar_created:
                add()
                return 0
            if msg == WM_CLOSE:
                u.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                s.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                u.PostQuitMessage(0)
                return 0
            return u.DefWindowProcW(hwnd, msg, wp, lp)

        self._proc = WNDPROC(proc)

        class WNDCLASS(ctypes.Structure):
            _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE),
                        ("hIcon", w.HICON), ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH), ("lpszMenuName", w.LPCWSTR), ("lpszClassName", w.LPCWSTR)]
        wc = WNDCLASS()
        wc.lpfnWndProc = self._proc
        wc.lpszClassName = "MarchandStudioTray"
        wc.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        u.RegisterClassW(ctypes.byref(wc))
        self.hwnd = u.CreateWindowExW(0, wc.lpszClassName, "Marchand Studio", 0, 0, 0, 0, 0, None, None, wc.hInstance, None)
        self.ok = bool(self.hwnd) and add()
        self.ready.set()
        if not self.hwnd:
            return
        msg = w.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
