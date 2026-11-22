# -*- coding: utf-8 -*-
"""
VALO SETUP —— 无畏契约 4:3 拉伸 & 职业设置工具

入口：单实例检查 → 交给 valo_app 起界面。
模块：
    valo_core   显示核心（多显示器 / 模式枚举 / 安全切换）
    valo_game   游戏配置（多路径 / 原子写 / 校验 / 备份）
    valo_sys    系统优化项
    valo_state  配置持久化 / 日志 / 单实例 / 诊断
    valo_app    界面
"""
import ctypes
import sys
import traceback
from ctypes import wintypes


def _activate_existing(title):
    try:
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.FindWindowW.restype = wintypes.HWND
        u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        h = u.FindWindowW(None, title)
        if not h:
            return False
        u.ShowWindow(h, 9)          # SW_RESTORE
        u.SetForegroundWindow(h)
        return True
    except Exception:
        return False


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    try:
        import valo_state as state
    except Exception:
        # 连自己的模块都导入失败，说明包不完整
        try:
            ctypes.windll.user32.MessageBoxW(
                None, "程序文件不完整（缺少 valo_state）。\n请重新解压完整文件夹后再运行。",
                "VALO SETUP", 0x10)
        except Exception:
            pass
        return 2

    if not state.single_instance():
        try:
            import valo_app
            if not _activate_existing(valo_app.APP_TITLE):
                ctypes.windll.user32.MessageBoxW(
                    None, "程序已经在运行了（可能被最小化了），\n请到任务栏找一下窗口。",
                    "VALO SETUP", 0x40)
        except Exception:
            pass
        return 0

    try:
        import valo_app
        valo_app.run()
        return 0
    except Exception:
        text = traceback.format_exc()
        p = state.crash_dump(text)
        try:
            ctypes.windll.user32.MessageBoxW(
                None, "启动失败。\n\n日志已保存到：\n%s\n\n%s"
                      % (p or state.DATA_DIR, text.splitlines()[-1][:300]),
                "VALO SETUP", 0x10)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
