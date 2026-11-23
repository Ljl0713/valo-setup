# -*- coding: utf-8 -*-
"""
valo_core —— 显示核心
多显示器枚举 / 动态模式枚举 / 原生分辨率识别 / 安全切换（含刷新率降级回退）

对外接口：
    monitors()                  -> [Monitor]
    pick(saved_monitor_id)      -> Monitor | None
    refresh(m)                  -> 就地更新 m["current"]
    native_of(m)                -> (w, h)
    set_mode(m, w, h, hz, ...)  -> (ok, msg)
    describe_ratio(w, h)        -> "4:3" / "16:9" / ...
"""
import ctypes
import time
from ctypes import wintypes

# ---------------------------------------------------------------- Win32 常量

ENUM_CURRENT_SETTINGS = -1
EDS_RAWMODE = 0x00000002

DM_BITSPERPEL = 0x00040000
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_DISPLAYFREQUENCY = 0x00400000
DM_DISPLAYFIXEDOUTPUT = 0x20000000
DMDFO_STRETCH = 1

CDS_UPDATEREGISTRY = 0x00000001
CDS_TEST = 0x00000002

DISP_CHANGE = {
    0: "成功",
    1: "需要重启",
    -1: "驱动拒绝",
    -2: "该模式不被支持",
    -3: "未生效",
    -4: "参数非法",
    -5: "参数非法",
    -6: "多屏配置冲突",
    -7: "驱动内部错误",
}


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPositionX", wintypes.LONG),
        ("dmPositionY", wintypes.LONG),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.EnumDisplaySettingsExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                          ctypes.POINTER(DEVMODEW), wintypes.DWORD]
user32.EnumDisplaySettingsExW.restype = wintypes.BOOL
user32.ChangeDisplaySettingsExW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(DEVMODEW),
                                            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p]
user32.ChangeDisplaySettingsExW.restype = wintypes.LONG
user32.EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                        ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD]
user32.EnumDisplayDevicesW.restype = wintypes.BOOL

ATTACHED = 0x00000001
PRIMARY = 0x00000004


# ---------------------------------------------------------------- 基础查询

def _devmode(dev, which):
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    if user32.EnumDisplaySettingsExW(dev, which, ctypes.byref(dm), EDS_RAWMODE):
        return dm
    return None


def _current(dev):
    dm = _devmode(dev, ENUM_CURRENT_SETTINGS)
    if not dm:
        return None
    return {"w": dm.dmPelsWidth, "h": dm.dmPelsHeight,
            "hz": dm.dmDisplayFrequency, "x": dm.dmPositionX, "y": dm.dmPositionY,
            "bpp": dm.dmBitsPerPel}


def _modes(dev):
    out = {}
    i = 0
    while i < 4000:
        dm = _devmode(dev, i)
        if not dm:
            break
        key = (dm.dmPelsWidth, dm.dmPelsHeight)
        if dm.dmBitsPerPel >= 32:
            out.setdefault(key, set()).add(dm.dmDisplayFrequency)
        i += 1
    return {k: sorted(v) for k, v in out.items()}


def describe_ratio(w, h):
    if not h:
        return "?"
    r = w / h
    table = [(4 / 3, "4:3"), (16 / 9, "16:9"), (16 / 10, "16:10"),
             (21 / 9, "21:9"), (5 / 4, "5:4"), (3 / 2, "3:2"), (32 / 9, "32:9")]
    for val, name in table:
        if abs(r - val) < 0.015:
            return name
    return "%.2f:1" % r


def is_43(w, h):
    return abs(w / h - 4 / 3) < 0.012


# ---------------------------------------------------------------- 显示器

def monitors():
    """枚举所有已接入桌面的显示器，附带完整模式表。"""
    result = []
    for i in range(12):
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        if not (dd.StateFlags & ATTACHED):
            continue
        mon = DISPLAY_DEVICEW()
        mon.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        user32.EnumDisplayDevicesW(dd.DeviceName, 0, ctypes.byref(mon), 0)
        modes = _modes(dd.DeviceName)
        native = max(modes, key=lambda t: t[0] * t[1]) if modes else (0, 0)
        result.append({
            "device": dd.DeviceName,
            "adapter": dd.DeviceString,
            "monitor": mon.DeviceString or "显示器",
            "monitor_id": mon.DeviceID or dd.DeviceName,
            "primary": bool(dd.StateFlags & PRIMARY),
            "current": _current(dd.DeviceName),
            "modes": modes,
            "native": native,
            "native_hz": sorted(modes.get(native, [])),
        })
    # 主屏排前面
    result.sort(key=lambda m: (not m["primary"], m["device"]))
    return result


def pick(saved_id=None, all_mons=None):
    """按上次保存的显示器 ID 找；找不到退回主屏；再不行取第一个。"""
    mons = all_mons if all_mons is not None else monitors()
    if not mons:
        return None
    if saved_id:
        for m in mons:
            if m["monitor_id"] == saved_id or m["device"] == saved_id:
                return m
    for m in mons:
        if m["primary"]:
            return m
    return mons[0]


def refresh(m):
    if m:
        m["current"] = _current(m["device"])
    return m


def native_of(m):
    return m["native"] if m and m["native"] != (0, 0) else (1920, 1080)


def label(m):
    if not m:
        return "未检测到显示器"
    nw, nh = native_of(m)
    hz = m["current"]["hz"] if m["current"] else "?"
    return "%s · %d×%d@%sHz" % (m["monitor"], nw, nh, hz)


# ---------------------------------------------------------------- 切换

def _hz_candidates(modes, w, h, want):
    hs = modes.get((w, h)) or []
    if not hs:
        return []
    seq = []
    if want and want in hs:
        seq.append(want)
    if want:
        seq += sorted([x for x in hs if x < want], reverse=True)[:3]
    seq.append(max(hs))
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def set_mode(m, w, h, hz=None, stretch=True, persist=False, test_only=False):
    """
    切换分辨率。返回 (ok, msg)。
    - 自动处理刷新率降级（请求 210 但模式只有 144 时，退到 144 而不是失败）
    - 自动跳过面板原生分辨率的 fixed-output 参数（否则驱动回 BADMODE）
    - stretch=True 时优先尝试 DMDFO_STRETCH（让驱动拉满）
    - persist=False（默认）：不写入注册表，注销/重启自动回到系统默认分辨率。
      这样即使程序崩溃或忘记切回，也不会开机卡在 4:3。
    """
    if not m:
        return False, "没有可用显示器"
    modes = m["modes"]
    if (w, h) not in modes:
        return False, "驱动不提供 %d×%d。请先在显卡控制面板里添加这个分辨率" % (w, h)

    hzs = _hz_candidates(modes, w, h, hz)
    if not hzs:
        return False, "%d×%d 没有可用刷新率" % (w, h)

    panel = native_of(m)
    is_panel = (w, h) == panel
    variants = [True, False] if (stretch and not is_panel) else [False]

    last_rc = None
    for hzc in hzs:
        for st in variants:
            dm = _devmode(m["device"], ENUM_CURRENT_SETTINGS)
            if not dm:
                dm = DEVMODEW()
                dm.dmSize = ctypes.sizeof(DEVMODEW)
            dm.dmPelsWidth = w
            dm.dmPelsHeight = h
            dm.dmDisplayFrequency = hzc
            dm.dmBitsPerPel = 32
            fields = DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY | DM_BITSPERPEL
            if st:
                dm.dmDisplayFixedOutput = DMDFO_STRETCH
                fields |= DM_DISPLAYFIXEDOUTPUT
            dm.dmFields = fields
            flags = CDS_TEST if test_only else (CDS_UPDATEREGISTRY if persist else 0)
            rc = user32.ChangeDisplaySettingsExW(m["device"], ctypes.byref(dm),
                                                 None, flags, None)
            last_rc = rc
            if rc == 0:
                if not test_only:
                    time.sleep(0.28)
                    refresh(m)
                return True, "%d×%d @ %dHz" % (w, h, hzc)
    return False, "切换失败：%s（%d×%d 可用刷新率 %s）" % (
        DISP_CHANGE.get(last_rc, "错误码 %s" % last_rc), w, h,
        "/".join(str(x) for x in hzs))


def restore(m, mode):
    """把显示器恢复到指定模式（用于异常兜底）。"""
    if not m or not mode:
        return False, "无恢复目标"
    return set_mode(m, mode["w"], mode["h"], mode.get("hz"))


# ---------------------------------------------------------------- 缩放模式（黑边根因）

# Windows DisplayConfig：4:3 要铺满屏幕，除了游戏里关 letterbox，
# 还要让显卡把 1280×960 的输出拉伸到面板原生尺寸。

import ctypes as _ct
from ctypes import wintypes as _wt


class _LUID(_ct.Structure):
    _fields_ = [("LowPart", _wt.DWORD), ("HighPart", _wt.LONG)]


class _RATIONAL(_ct.Structure):
    _fields_ = [("Numerator", _wt.UINT), ("Denominator", _wt.UINT)]


class _SRCINFO(_ct.Structure):
    _fields_ = [("adapterId", _LUID), ("id", _wt.UINT),
                ("modeInfoIdx", _wt.UINT), ("statusFlags", _wt.UINT)]


class _TGTINFO(_ct.Structure):
    _fields_ = [("adapterId", _LUID), ("id", _wt.UINT),
                ("modeInfoIdx", _wt.UINT), ("outputTechnology", _wt.UINT),
                ("rotation", _wt.UINT), ("scaling", _wt.UINT),
                ("refreshRate", _RATIONAL), ("scanLineOrdering", _wt.UINT),
                ("targetAvailable", _wt.BOOL), ("statusFlags", _wt.UINT)]


class _PATHINFO(_ct.Structure):
    _fields_ = [("sourceInfo", _SRCINFO), ("targetInfo", _TGTINFO),
                ("flags", _wt.UINT)]


class _DIV_HEADER(_ct.Structure):
    _fields_ = [("type", _wt.UINT), ("size", _wt.UINT),
                ("adapterId", _LUID), ("id", _wt.UINT)]


class _SRC_DEVICE_NAME(_ct.Structure):
    _fields_ = [("header", _DIV_HEADER), ("viewGdiDeviceName", _wt.WCHAR * 32)]


DC_GET_SOURCE_NAME = 1


SCALING_NAMES = {0: "未知", 1: "不缩放", 2: "居中", 3: "拉伸填充",
                 4: "保持比例（会出黑边）", 5: "自定义", 128: "驱动默认"}
SC_IDENTITY, SC_CENTERED, SC_STRETCH, SC_ASPECT = 1, 2, 3, 4

_QDC_ACTIVE = 0x00000002
_SDC_APPLY = 0x00000080
_SDC_USE_SUPPLIED = 0x00000020
_SDC_SAVE = 0x00000200
_SDC_ALLOW_CHANGES = 0x00000400
_MODE_SZ = 256

user32.GetDisplayConfigBufferSizes.argtypes = [_wt.UINT, _ct.POINTER(_wt.UINT),
                                               _ct.POINTER(_wt.UINT)]
user32.GetDisplayConfigBufferSizes.restype = _wt.LONG
user32.QueryDisplayConfig.argtypes = [_wt.UINT, _ct.POINTER(_wt.UINT),
                                      _ct.POINTER(_PATHINFO), _ct.POINTER(_wt.UINT),
                                      _ct.c_void_p, _ct.c_void_p]
user32.QueryDisplayConfig.restype = _wt.LONG
user32.SetDisplayConfig.argtypes = [_wt.UINT, _ct.POINTER(_PATHINFO), _wt.UINT,
                                    _ct.c_void_p, _wt.UINT]
user32.SetDisplayConfig.restype = _wt.LONG
user32.DisplayConfigGetDeviceInfo.argtypes = [_ct.c_void_p]
user32.DisplayConfigGetDeviceInfo.restype = _wt.LONG


def _query_paths():
    n, m = _wt.UINT(), _wt.UINT()
    if user32.GetDisplayConfigBufferSizes(_QDC_ACTIVE, _ct.byref(n), _ct.byref(m)):
        return None
    paths = (_PATHINFO * n.value)()
    modes = (_ct.c_byte * (_MODE_SZ * m.value))()
    if user32.QueryDisplayConfig(_QDC_ACTIVE, _ct.byref(n), paths,
                                 _ct.byref(m), modes, None):
        return None
    return paths, n.value, modes, m.value


def _gdi_name_of(path):
    s = _SRC_DEVICE_NAME()
    s.header.type = DC_GET_SOURCE_NAME
    s.header.size = _ct.sizeof(_SRC_DEVICE_NAME)
    s.header.adapterId = path.sourceInfo.adapterId
    s.header.id = path.sourceInfo.id
    if user32.DisplayConfigGetDeviceInfo(_ct.byref(s)) != 0:
        return None
    return s.viewGdiDeviceName or None


def scaling_modes(device=None):
    """
    读缩放模式。device 传 "\\\\.\\DISPLAY1" 时只读那块屏。
    返回 [值,...]；读不到返回 None。
    """
    got = _query_paths()
    if not got:
        return None
    paths, n, _modes, _m = got
    out = []
    for i in range(n):
        if device:
            name = _gdi_name_of(paths[i])
            if name and name.upper() != device.upper():
                continue
        out.append(paths[i].targetInfo.scaling)
    return out


def scaling_summary(device=None):
    got = scaling_modes(device)
    if got is None:
        return "读不到"
    if not got:
        return "该显示器无活动路径"
    return " / ".join(SCALING_NAMES.get(v, str(v)) for v in got)


def set_scaling(stretch=True, persist=False, device=None):
    """
    设置缩放模式：True=拉伸填充（去黑边），False=不缩放。
    device 指定 "\\\\.\\DISPLAY1" 时**只改那一块屏**——多显示器必须这样，
    否则会把副屏一起改掉。
    返回 (ok, msg)。
    """
    got = _query_paths()
    if not got:
        return False, "读不到显示配置"
    paths, n, modes, m = got
    want = SC_STRETCH if stretch else SC_IDENTITY
    need, hit = 0, 0
    for i in range(n):
        if device:
            name = _gdi_name_of(paths[i])
            if not name or name.upper() != device.upper():
                continue
        hit += 1
        if paths[i].targetInfo.scaling != want:
            paths[i].targetInfo.scaling = want
            need += 1
    if not hit and n == 1:
        # 老系统上取不到设备名时兜底：只有一条显示路径就直接改它
        hit = 1
        if paths[0].targetInfo.scaling != want:
            paths[0].targetInfo.scaling = want
            need = 1
    if not hit:
        return False, "找不到目标显示器（%s）的显示路径" % (device or "全部")
    if not need:
        return True, "已经是目标缩放（%s）" % SCALING_NAMES.get(want)
    flags = _SDC_APPLY | _SDC_USE_SUPPLIED | _SDC_ALLOW_CHANGES
    if persist:
        flags |= _SDC_SAVE
    rc = user32.SetDisplayConfig(n, paths, m, modes, flags)
    if rc != 0:
        return False, "系统拒绝了缩放变更（代码 %d）" % rc
    after = scaling_modes(device) or []
    if want in after:
        return True, "缩放已设为%s" % SCALING_NAMES.get(want)
    return False, "已提交但未生效（当前：%s），可能被显卡驱动接管" % scaling_summary(device)


def gpu_vendor(m):
    """判断显卡厂商，用来给不同的手动操作指引"""
    a = ((m or {}).get("adapter") or "").lower()
    for key, name in (("nvidia", "nvidia"), ("geforce", "nvidia"),
                      ("radeon", "amd"), ("amd", "amd"), ("ati ", "amd"),
                      ("intel", "intel"), ("arc", "intel")):
        if key in a:
            return name
    return "unknown"


def resolve_mode(m, w, h):
    """
    把「用户要求的 4:3」落到这台机器真的支持的档位上。
    1280×960 在别人的驱动里可能不存在，这里退到最接近的可用 4:3。
    返回 (w, h, 是否原样)。
    """
    if not m:
        return w, h, True
    modes = m["modes"]
    if (w, h) in modes:
        return w, h, True
    want_area = w * h
    best = None
    for (mw, mh) in modes:
        if is_43(mw, mh) and mw >= 1024:
            if best is None or abs(mw * mh - want_area) < abs(best[0] * best[1] - want_area):
                best = (mw, mh)
    if best:
        return best[0], best[1], False
    return w, h, True


def fix_letterbox(m, w, h, hz=None, persist=False):
    """一键去黑边：切到可用 4:3 + 把缩放设成拉伸填充（只动这块屏）"""
    rw, rh, exact = resolve_mode(m, w, h)
    ok, msg = set_mode(m, rw, rh, hz, persist=persist)
    if not ok:
        return False, msg, (rw, rh)
    sok, smsg = set_scaling(True, persist=False, device=m.get("device"))
    note = "" if exact else "（%d×%d 你的驱动没有，已换成 %d×%d）" % (w, h, rw, rh)
    return True, "%s；%s%s" % (msg, smsg, note), (rw, rh)
