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


# ---------------------------------------------------------------- 全屏独占

FSE_KEY = r"System\GameConfigStore"


def fse_optimized():
    """已关掉 Windows 的全屏优化（真独占）"""
    return _as_int(reg_get(FSE_KEY, "GameDVR_DXGIHonorFSEWindowsCompatible"), 0) == 1


def set_fse_optimized(on):
    """关掉「全屏优化」：游戏走真独占，少一层 DWM 合成，输入延迟低一档"""
    reg_set(FSE_KEY, "GameDVR_DXGIHonorFSEWindowsCompatible",
            1 if on else 0, winreg.REG_DWORD)
    reg_set(FSE_KEY, "GameDVR_FSEBehaviorMode", 2 if on else 0, winreg.REG_DWORD)


# ---------------------------------------------------------------- Xbox Game Bar

def gamebar_clean():
    """Xbox Game Bar 的启动面板 / Nexus 已关闭"""
    return _as_int(reg_get(GAMEBAR, "ShowStartupPanel"), 1) == 0


def set_gamebar_clean(on):
    v = 0 if on else 1
    reg_set(GAMEBAR, "ShowStartupPanel", v, winreg.REG_DWORD)
    reg_set(GAMEBAR, "UseNexusForGameBarEnabled", 1 - v, winreg.REG_DWORD)


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


# ---------------------------------------------------------------- GPU 缩放（禁用显示器缩放）

_target_dev = [None]      # 当前操作的显示器（\Device\DISPLAYx），由 UI 设置


def set_target_device(device_name):
    """UI 切换显示器时调用，让 gpu_scale 知道作用于哪块屏"""
    _target_dev[0] = device_name


def gpu_scaling_on():
    """缩放是否由 GPU 执行（=「拉伸填充」生效且未被驱动接管）"""
    import valo_core as core
    m = core.scaling_modes(_target_dev[0] or None)
    if not m:
        return False
    return core.SC_STRETCH in m


def set_gpu_scaling(on):
    import valo_core as core
    ok, msg = core.set_scaling(bool(on), persist=False, device=_target_dev[0] or None)
    if ok:
        return True, msg
    if on:
        # 驱动会拒绝「不缩放 → 拉伸」的直改；重新提交当前分辨率可触发默认拉伸
        try:
            m = core.pick(None, core.monitors())
            cur = m["current"] or {}
            core.set_mode(m, cur.get("w"), cur.get("h"), cur.get("hz"))
            after = core.scaling_modes(_target_dev[0] or None) or []
            if core.SC_STRETCH in after:
                return True, "已恢复拉伸填充（重新应用分辨率）"
        except Exception:
            pass
    return False, msg


# ---------------------------------------------------------------- 监视器设备禁用/启用
# 教程里「禁用监视器」指在设备管理器禁用「通用即插即用监视器」设备：
# 让 Windows 不再让显示器自己处理缩放，交给 GPU。需要管理员权限（UAC）。

import base64 as _b64
import json as _json

PROBLEM_DISABLED = 22      # CM_PROB_DISABLED


def _ps(script, timeout=40):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, timeout=timeout,
                       creationflags=NO_WINDOW)
    return r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def monitor_device_info():
    """返回 (friendly_name, instance_id, disabled)；读不到返回 None"""
    try:
        out, err = _ps("Get-PnpDevice -Class Monitor | Where-Object Present | "
                       "ConvertTo-Json -Compress")
        data = _json.loads(out) if out.strip() else None
        if isinstance(data, dict):
            data = [data]
        if not data:
            return None
        # 优先取状态非 Error 的；禁用设备 Status=Error/Problem=22
        pick = None
        for d in data:
            if d.get("Problem") == PROBLEM_DISABLED:
                pick = d
                break
        if pick is None:
            pick = data[0]
        return (pick.get("FriendlyName") or "监视器",
                pick.get("InstanceId"), pick.get("Problem") == PROBLEM_DISABLED)
    except Exception:
        return None


def set_monitor_disabled(disable, instance_id):
    """
    禁用/启用监视器设备。必须走 UAC 提权（用户点「是」），
    用 EncodedCommand 避免引号嵌套。返回 (ok, msg)
    """
    verb = "Disable-PnpDevice" if disable else "Enable-PnpDevice"
    inner = '%s -InstanceId "%s" -Confirm:$false' % (verb, instance_id)
    enc = _b64.b64encode(inner.encode("utf-16-le")).decode("ascii")
    outer = ('Start-Process powershell -Verb runas -Wait -WindowStyle Hidden '
             '-ArgumentList \'-NoProfile -EncodedCommand %s\'' % enc)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            outer], capture_output=True, timeout=120,
                           creationflags=NO_WINDOW)
    except Exception as e:      # noqa: BLE001
        return False, repr(e)
    # 验证实际状态
    info = monitor_device_info()
    if info and info[2] == disable:
        return True, ("已禁用" if disable else "已启用")
    return False, ("用户取消了 UAC 或系统拒绝" if r.returncode != 0 else "提交了但状态未变化")


# ---------------------------------------------------------------- 结构化条目

def _item(key, label, hint, getter, setter, note=""):
    return {"key": key, "label": label, "hint": hint,
            "get": getter, "set": setter, "note": note}


def items():
    """系统优化项：UI 渲染成开关。set 接受 bool（True=优化态），flip 会传反向值"""
    return [
        _item("mouse", "关闭鼠标加速",
              "指针移动与手感线性对应，FPS 必做",
              lambda: not mouse_accel_on(), lambda on: set_mouse_accel(on)),
        _item("sticky", "关闭粘滞键/切换键快捷键",
              "连按 Shift 五下不再弹窗打断游戏",
              lambda: not sticky_hotkeys_on(),
              lambda on: set_sticky_hotkeys(on), note="注销后生效"),
        _item("fse", "关闭全屏优化（真独占）",
              "少一层桌面合成，输入延迟低一档",
              fse_optimized, lambda on: set_fse_optimized(on)),
        _item("gamebar", "关掉 Xbox Game Bar 弹窗",
              "Win+G / 手柄 Home 键不再跳出来",
              gamebar_clean, lambda on: set_gamebar_clean(on)),
        _item("gpu_scale", "禁用监视器（缩放交给 GPU）",
              "教程里的「全屏 + GPU / 禁用监视器缩放」：\n"
              "4:3 由显卡拉伸而不是显示器，更快更稳。\n"
              "切到 4:3 后开关才真正生效；在原生分辨率下显卡不参与缩放，点了不会有变化",
              gpu_scaling_on, lambda on: set_gpu_scaling(on)),
        _item("gamemode", "Windows 游戏模式",
              "建议开启，让前台游戏优先占用资源",
              gamemode_on, lambda on: set_gamemode(on)),
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
            it["set"](True)
            ok += 1
        except Exception as e:
            detail.append("%s: %r" % (it["label"], e))
    plan = best_power_plan()
    if plan:
        good, msg = set_power_plan(plan)
        detail.append("电源计划 → %s" % (msg if good else "失败 " + str(msg)))
    return ok, detail


# ---------------------------------------------------------------- 还原

BALANCED_GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"   # Windows 默认「平衡」


def set_power_plan_guid(guid, name=""):
    try:
        r = subprocess.run(["powercfg", "/setactive", guid], capture_output=True,
                           creationflags=NO_WINDOW, timeout=8)
        return r.returncode == 0, (name or guid)
    except Exception as e:
        return False, repr(e)


def snapshot():
    """
    记录「用户原来的样子」。真正的恢复默认应该回到用户自己的原值，
    而不是微软出厂值——第一次优化前存一份，以后一直用它还原。
    """
    try:
        return {"mouse_accel": mouse_accel_on(),
                "sticky_hotkeys": sticky_hotkeys_on(),
                "gamedvr": gamedvr_on(),
                "fse": fse_optimized(),
                "gamebar": gamebar_clean(),
                "gamemode": gamemode_on(),
                "power": current_power()}
    except Exception:
        return {}


def apply_snapshot(snap=None):
    """按快照还原；没有快照时退回 Windows 出厂默认。返回 (成功数, 明细)"""
    snap = snap or {}
    ok, detail = 0, []

    def _try(label, fn):
        nonlocal ok
        try:
            fn()
            ok += 1
        except Exception as e:      # noqa: BLE001
            detail.append("%s 失败: %r" % (label, e))

    _try("鼠标加速", lambda: set_mouse_accel(not snap.get("mouse_accel", True)))
    _try("粘滞键快捷键", lambda: set_sticky_hotkeys(not snap.get("sticky_hotkeys", True)))
    _try("GameDVR", lambda: set_gamedvr(not snap.get("gamedvr", True)))
    _try("全屏优化", lambda: set_fse_optimized(bool(snap.get("fse", False))))
    _try("GameBar", lambda: set_gamebar_clean(bool(snap.get("gamebar", False))))
    _try("游戏模式", lambda: set_gamemode(bool(snap.get("gamemode", True))))

    plan = snap.get("power")
    if plan and plan not in ("未知", ""):
        good, msg = set_power_plan(plan)
        if not good:
            good, msg = set_power_plan_guid(BALANCED_GUID, "平衡")
        detail.append("电源计划 → %s" % (msg if good else "失败"))
    else:
        good, msg = set_power_plan_guid(BALANCED_GUID, "平衡")
        if not good:
            good, msg = set_power_plan("平衡")
        detail.append("电源计划 → %s" % (msg if good else "失败"))
    return ok, detail
