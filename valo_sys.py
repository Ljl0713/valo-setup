# -*- coding: utf-8 -*-
"""
valo_sys —— 系统层面优化项
每个优化项都是「可读当前状态 + 可一键设置」的结构化条目，UI 直接遍历渲染。
"""
import ctypes
import os
import re
import subprocess
import winreg
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
HKCU = winreg.HKEY_CURRENT_USER
NO_WINDOW = 0x08000000

MOUSE_KEY = r"Control Panel\Mouse"
STICKY = r"Control Panel\Accessibility\StickyKeys"
TOGGLE = r"Control Panel\Accessibility\ToggleKeys"
FILTER = r"Control Panel\Accessibility\Keyboard Response"
DVR_KEY = r"Software\Microsoft\Windows\CurrentVersion\GameDVR"
GCS_KEY = r"System\GameConfigStore"
GAMEBAR = r"Software\Microsoft\GameBar"


# ---------------------------------------------------------------- 注册表helpers

def reg_get(path, name, root=HKCU):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def reg_set(path, name, value, kind=winreg.REG_SZ, root=HKCU):
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, kind, value)


def _as_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- 鼠标加速

def mouse_accel_on():
    return _as_int(reg_get(MOUSE_KEY, "MouseSpeed"), 0) != 0


def set_mouse_accel(off):
    if off:
        reg_set(MOUSE_KEY, "MouseSpeed", "0")
        reg_set(MOUSE_KEY, "MouseThreshold1", "0")
        reg_set(MOUSE_KEY, "MouseThreshold2", "0")
        arr = (ctypes.c_int * 3)(0, 0, 0)
    else:
        reg_set(MOUSE_KEY, "MouseSpeed", "1")
        reg_set(MOUSE_KEY, "MouseThreshold1", "6")
        reg_set(MOUSE_KEY, "MouseThreshold2", "10")
        arr = (ctypes.c_int * 3)(6, 10, 1)
    try:
        user32.SystemParametersInfoW(0x0004, 0, ctypes.byref(arr), 0x01)
    except Exception:
        pass


# ---------------------------------------------------------------- 粘滞键等快捷键

def sticky_hotkeys_on():
    return bool(_as_int(reg_get(STICKY, "Flags"), 510) & 0x4)


def set_sticky_hotkeys(off):
    for path, dflt in ((STICKY, 510), (TOGGLE, 62), (FILTER, 126)):
        cur = _as_int(reg_get(path, "Flags"), dflt)
        newv = (cur & ~0x4) if off else (cur | 0x4)
        reg_set(path, "Flags", str(newv))


# ---------------------------------------------------------------- GameDVR

def gamedvr_on():
    return _as_int(reg_get(DVR_KEY, "AppCaptureEnabled"), 0) == 1


def set_gamedvr(off):
    v = 0 if off else 1
    reg_set(DVR_KEY, "AppCaptureEnabled", v, winreg.REG_DWORD)
    reg_set(GCS_KEY, "GameDVR_Enabled", v, winreg.REG_DWORD)


# ---------------------------------------------------------------- 游戏模式

def gamemode_on():
    return _as_int(reg_get(GAMEBAR, "AutoGameModeEnabled"), 1) == 1


def set_gamemode(on):
    reg_set(GAMEBAR, "AutoGameModeEnabled", 1 if on else 0, winreg.REG_DWORD)


# ---------------------------------------------------------------- 电源计划

def current_power():
    try:
        r = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True,
                           creationflags=NO_WINDOW, timeout=8)
        out = (r.stdout or b"").decode("gbk", "replace")
        m = re.search(r"\((.+?)\)", out)
        return m.group(1) if m else out.strip() or "未知"
    except Exception:
        return "未知"


def power_plans():
    """返回 {名称: GUID}"""
    res = {}
    try:
        r = subprocess.run(["powercfg", "/list"], capture_output=True,
                           creationflags=NO_WINDOW, timeout=8)
        out = (r.stdout or b"").decode("gbk", "replace")
        for line in out.splitlines():
            m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s+\((.+?)\)", line)
            if m:
                res[m.group(2)] = m.group(1)
    except Exception:
        pass
    return res


def set_power_plan(name):
    plans = power_plans()
    for k, guid in plans.items():
        if name in k:
            try:
                r = subprocess.run(["powercfg", "/setactive", guid], capture_output=True,
                                   creationflags=NO_WINDOW, timeout=8)
                return r.returncode == 0, k
            except Exception as e:
                return False, repr(e)
    return False, "没找到「%s」电源计划" % name


def best_power_plan():
    """优先卓越性能，其次高性能"""
    plans = power_plans()
    for want in ("卓越性能", "高性能"):
        for k in plans:
            if want in k:
                return want
    return None


# ---------------------------------------------------------------- NVIDIA 面板

def open_nvidia_panel():
    """打开 NVIDIA 控制面板（找不到就打开 NVIDIA App）"""
    cands = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "NVIDIA Corporation", "Control Panel Client", "nvcplui.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "NVIDIA Corporation", "NVIDIA app", "CEF", "NVIDIA app.exe"),
    ]
    for p in cands:
        if os.path.isfile(p):
            try:
                os.startfile(p)
                return True
            except OSError:
                pass
    try:
        os.startfile("ms-settings:display")
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- 结构化条目

def _item(key, label, hint, getter, setter, note=""):
    return {"key": key, "label": label, "hint": hint,
            "get": getter, "set": setter, "note": note}


def items():
    return [
        _item("mouse", "关闭鼠标加速",
              "指针移动与手感线性对应，FPS 必做",
              lambda: not mouse_accel_on(), lambda: set_mouse_accel(True)),
        _item("sticky", "关闭粘滞键/切换键快捷键",
              "连按 Shift 五下不再弹窗打断游戏",
              lambda: not sticky_hotkeys_on(),
              lambda: set_sticky_hotkeys(True), note="注销后生效"),
        _item("dvr", "关闭后台录制 GameDVR",
              "省 CPU / GPU，避免录制抢占",
              lambda: not gamedvr_on(), lambda: set_gamedvr(True)),
        _item("gamemode", "Windows 游戏模式",
              "建议开启，让前台游戏优先占用资源",
              gamemode_on, lambda: set_gamemode(True)),
    ]


def state():
    st = {}
    for it in items():
        try:
            st[it["key"]] = bool(it["get"]())
        except Exception:
            st[it["key"]] = False
    st["_power"] = current_power()
    return st


def optimize_all():
    """一键把所有项设为最优，返回 (成功数, 明细)"""
    ok, detail = 0, []
    for it in items():
        try:
            it["set"]()
            ok += 1
        except Exception as e:
            detail.append("%s: %r" % (it["label"], e))
    plan = best_power_plan()
    if plan:
        good, msg = set_power_plan(plan)
        detail.append("电源计划 → %s" % (msg if good else "失败 " + str(msg)))
    return ok, detail
