# -*- coding: utf-8 -*-
"""
valo_tray —— 纯 ctypes 系统托盘图标（零依赖）
- start(icon_path, tip)：创建托盘图标，隐藏窗口到托盘用
- 左键单击 → on_left（恢复窗口）
- 右键单击 → on_right（弹菜单）
- 动作通过 pop_action() 由 UI 主线程轮询，不跨线程碰 tkinter
"""
import ctypes
import threading
from ctypes import wintypes

WM_TRAY = 0x8000            # WM_USER
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x1, 0x2, 0x4
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x10
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_DESTROY = 0x0002


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_ubyte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.WINFUNCTYPE(wintypes.LONG, wintypes.HWND,
                                           wintypes.UINT, wintypes.WPARAM,
                                           wintypes.LPARAM)),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD,
                                      ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
user32.LoadImageW.restype = wintypes.HICON
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                              wintypes.UINT, ctypes.c_int, ctypes.c_int,
                              wintypes.UINT]


class Tray:
    """线程里跑消息窗口；动作塞进 self.action，由主线程 tick() 轮询"""

    def __init__(self, icon_path, tip):
        self.icon_path = icon_path
        self.tip = tip
        self.action = None       # "left" / "right"
        self.menu_x = 0
        self.menu_y = 0
        self._tid = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        cls_name = "ValoSetupTrayWnd"
        self._proc = ctypes.WINFUNCTYPE(wintypes.LONG, wintypes.HWND,
                                        wintypes.UINT, wintypes.WPARAM,
                                        wintypes.LPARAM)(self._wndproc)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._proc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = cls_name
        if not user32.RegisterClassW(ctypes.byref(wc)):
            return
        self.hwnd = user32.CreateWindowExW(
            0, cls_name, "VALO SETUP tray", 0,
            0, 0, 0, 0, None, None, wc.hInstance, None)
        if not self.hwnd:
            return
        hicon = user32.LoadImageW(None, self.icon_path, IMAGE_ICON,
                                  0, 0, LR_LOADFROMFILE)
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = hicon
        nid.szTip = self.tip[:127]
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _wndproc(self, hwnd, msg, wp, lp):
        if msg == WM_TRAY:
            if lp == WM_LBUTTONUP or lp == WM_LBUTTONDBLCLK:
                self.action = "left"
            elif lp == WM_RBUTTONUP:
                self.action = "right"
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                self.menu_x, self.menu_y = pt.x, pt.y
            return 0
        if msg == WM_DESTROY:
            self._remove()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    def _remove(self):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

    def pop_action(self):
        a = self.action
        self.action = None
        return a

    def stop(self):
        try:
            if self.hwnd:
                user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
                self._remove()
        except Exception:
            pass
