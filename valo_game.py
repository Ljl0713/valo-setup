# -*- coding: utf-8 -*-
"""
valo_game —— 无畏契约配置文件存取
多路径探测 / 多账号 / 原子写 / 写后校验 / 备份轮转 / 进程检测

配置位置（与游戏安装盘无关，固定在 %LOCALAPPDATA%）：
    ...\\Saved\\Config\\WindowsClient\\GameUserSettings.ini     显示相关
    ...\\Saved\\Config\\<账号>-ap\\Windows\\RiotUserSettings.ini  画质/灵敏度/准星
"""
import ctypes
import glob
import os
import shutil
import time
from ctypes import wintypes

# 可能出现的游戏进程名（国际服 / 国服 / 不同版本）
GAME_EXES = {
    "VALORANT-WIN64-SHIPPING.EXE",
    "VALORANT.EXE",
    "VALORANT-WIN64-SHIPPING-NE.exe",
}

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                 wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
_psapi = ctypes.WinDLL("psapi")


# ---------------------------------------------------------------- 进程

def game_pids():
    arr = (wintypes.DWORD * 4096)()
    got = wintypes.DWORD()
    if not _psapi.EnumProcesses(ctypes.byref(arr), ctypes.sizeof(arr), ctypes.byref(got)):
        return []
    res = []
    for i in range(got.value // 4):
        pid = arr[i]
        if not pid:
            continue
        h = _kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            continue
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                if os.path.basename(buf.value).upper() in GAME_EXES:
                    res.append(pid)
        finally:
            _kernel32.CloseHandle(h)
    return res


def game_running():
    return bool(game_pids())


# ---------------------------------------------------------------- 路径探测

def _bases():
    lad = os.environ.get("LOCALAPPDATA", "")
    if not lad:
        return []
    pats = [
        os.path.join(lad, "VALORANT", "Saved", "Config"),
        os.path.join(lad, "Riot Games", "VALORANT", "Saved", "Config"),
        os.path.join(lad, "Tencent", "VALORANT", "Saved", "Config"),
        os.path.join(lad, "无畏契约", "Saved", "Config"),
    ]
    return [p for p in pats if os.path.isdir(p)]


def discover():
    """
    返回 {
      game_ini: str|None,
      user_inis: [str],          # 多账号，按修改时间倒序
      base: str|None,
      error: str|None
    }
    """
    res = {"game_ini": None, "user_inis": [], "base": None, "error": None}
    bases = _bases()
    if not bases:
        res["error"] = "没找到无畏契约配置目录（%LOCALAPPDATA%\\VALORANT\\Saved\\Config）"
        return res
    for base in bases:
        gi = os.path.join(base, "WindowsClient", "GameUserSettings.ini")
        if os.path.isfile(gi):
            res["game_ini"] = gi
            res["base"] = base
            break
    if not res["base"]:
        res["base"] = bases[0]
    seen = set()
    for base in bases:
        for pat in ("*-ap", "*"):
            for p in glob.glob(os.path.join(base, pat, "Windows", "RiotUserSettings.ini")):
                if p not in seen:
                    seen.add(p)
                    res["user_inis"].append(p)
    res["user_inis"].sort(key=lambda p: os.path.getmtime(p), reverse=True)
    if not res["game_ini"]:
        res["error"] = "找到配置目录但缺少 GameUserSettings.ini，可能还没进过游戏"
    return res


def pick_user_ini(cands, saved=None):
    if saved and os.path.isfile(saved):
        return saved
    return cands[0] if cands else None


# ---------------------------------------------------------------- ini 读写

def read_ini(path):
    """返回 (dict, bom_flag)。保持 BOM 状态以便原样写回。"""
    if not path or not os.path.isfile(path):
        return {}, False
    with open(path, "rb") as f:
        raw = f.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig", errors="replace")
    data = {}
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith(";") or s.startswith("["):
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            data[k.strip()] = v.strip()
    return data, bom


def _read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig", errors="replace"), bom


def _write_text(path, text, bom):
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    tmp = path + ".valotmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_ini(path, kv, section=None):
    """
    就地替换已存在的键，缺的补到 section 末尾（无 section 参数则追加到文件尾）。
    原子写 + 保留 BOM。返回写入的键数。
    """
    text, bom = _read_text(path)
    lines = text.splitlines()
    left = dict(kv)
    out = []
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith(";") and not s.startswith("[") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in left:
                out.append("%s=%s" % (k, left.pop(k)))
                continue
        out.append(ln)
    if left:
        if section is None:
            out.extend("%s=%s" % (k, v) for k, v in left.items())
        else:
            head = None
            for i, ln in enumerate(out):
                if ln.strip() == "[%s]" % section:
                    head = i
                    break
            if head is None:
                out.append("")
                out.append("[%s]" % section)
                head = len(out) - 1
            end = len(out)
            for j in range(head + 1, len(out)):
                if out[j].strip().startswith("["):
                    end = j
                    break
            for k, v in left.items():
                out.insert(end, "%s=%s" % (k, v))
                end += 1
    _write_text(path, "\n".join(out) + "\n", bom)
    return len(kv)


def verify(path, expect):
    """写后回读校验，返回 (ok, 不一致的键列表)"""
    data, _ = read_ini(path)
    bad = [k for k, v in expect.items() if str(data.get(k, "")).strip().lower() != str(v).strip().lower()]
    return (not bad), bad


# ---------------------------------------------------------------- 备份

def backup(paths, root, keep=10):
    """备份若干文件到 root\\<时间戳>\\，只保留最近 keep 份。返回目录或 None。"""
    files = [p for p in paths if p and os.path.isfile(p)]
    if not files:
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(root, stamp)
    # 同一秒内多次备份时加序号，避免互相覆盖
    if os.path.exists(dest):
        i = 2
        while os.path.exists("%s-%d" % (dest, i)):
            i += 1
        dest = "%s-%d" % (dest, i)
    os.makedirs(dest, exist_ok=True)
    for p in files:
        shutil.copy2(p, os.path.join(dest, os.path.basename(p)))
    _rotate(root, keep)
    return dest


def _rotate(root, keep):
    if not os.path.isdir(root):
        return
    subs = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    for d in subs[:-keep] if len(subs) > keep else []:
        shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def list_backups(root):
    if not os.path.isdir(root):
        return []
    subs = sorted((d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))),
                  reverse=True)
    return [os.path.join(root, d) for d in subs]


def latest_backup(root):
    """返回最近一次的备份目录，没有就 None"""
    if not os.path.isdir(root):
        return None
    dirs = [os.path.join(root, d) for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))]
    if not dirs:
        return None
    dirs.sort(key=os.path.getmtime, reverse=True)
    return dirs[0]


def restore(backup_dir, game_ini, user_ini):
    n = 0
    for name, target in (("GameUserSettings.ini", game_ini),
                         ("RiotUserSettings.ini", user_ini)):
        src = os.path.join(backup_dir, name)
        if target and os.path.isfile(src):
            shutil.copy2(src, target)
            n += 1
    return n


# ---------------------------------------------------------------- 一键配置

SECTION_GAME = "/Script/ShooterGame.ShooterGameUserSettings"

# 画质档位：0 低 / 1 中 / 2 高 / 3 极高
# CORE：这几项在所有版本里都存在，直接写
QUALITY_CORE = {
    "EAresIntSettingName::DetailQuality": "0",
    "EAresIntSettingName::MaterialQuality": "0",
    "EAresIntSettingName::TextureQuality": "0",
    "EAresIntSettingName::AntiAliasing": "0",          # MSAA 关
    "EAresIntSettingName::AnisotropicFiltering": "1",  # 1x
    "EAresBoolSettingName::ShadowsEnabled": "False",
    "EAresBoolSettingName::ImproveClarity": "True",    # 改善清晰度
    "EAresIntSettingName::NvidiaReflexLowLatencySetting": "2",   # 开 + 加速
}

# EXTRA：默认值就是"关/开"的那些项。玩家没动过设置时 ini 里不会有这些键，
# 所以不能"存在才写"——必须主动补上，游戏就会按这里的值走。
QUALITY_EXTRA = {
    "EAresBoolSettingName::BloomEnabled": "False",           # 泛光：关，看清敌人
    "EAresBoolSettingName::DistortionEnabled": "False",      # 失真：关
    "EAresBoolSettingName::VignetteEnabled": "False",        # 暗角：关
    "EAresBoolSettingName::ExperimentalSharpening": "True",  # 实验性锐化：开
    "EAresFloatSettingName::ResolutionQuality": "100.000000",  # 渲染缩放 100%
}

QUALITY_PRO = dict(QUALITY_CORE, **QUALITY_EXTRA)

QUALITY_KEYS = [
    ("DetailQuality", "细节质量", ["低", "中", "高", "极高"]),
    ("MaterialQuality", "材质质量", ["低", "中", "高", "极高"]),
    ("TextureQuality", "贴图质量", ["低", "中", "高", "极高"]),
    ("AntiAliasing", "抗锯齿", ["关", "MSAA 2x", "MSAA 4x", "MSAA 8x"]),
    ("AnisotropicFiltering", "各向异性过滤", ["1x", "2x", "4x", "8x", "16x"]),
]


def quality_report(user_ini):
    """看这台机器的 ini 里到底有哪些画质键，用于「诊断」和写入前判断"""
    if not user_ini or not os.path.isfile(user_ini):
        return {"ok": False, "core": [], "extra": [], "missing": []}
    txt, _bom = _read_text(user_ini)
    core = [k for k in QUALITY_CORE if k in txt]
    extra = [k for k in QUALITY_EXTRA if k in txt]
    missing = [k for k in QUALITY_CORE if k not in txt]
    return {"ok": True, "core": core, "extra": extra, "missing": missing}


def apply_display(game_ini, w, h, fullscreen=True, no_vsync=True,
                  stretch=True, unlock_fps=True):
    kv = {
        "ResolutionSizeX": str(w),
        "ResolutionSizeY": str(h),
        "LastUserConfirmedResolutionSizeX": str(w),
        "LastUserConfirmedResolutionSizeY": str(h),
    }
    if fullscreen:
        kv["PreferredFullscreenMode"] = "0"
        kv["LastConfirmedFullscreenMode"] = "0"
    if no_vsync:
        kv["bUseVSync"] = "False"
    if stretch:
        kv["bShouldLetterbox"] = "False"
        kv["bLastConfirmedShouldLetterbox"] = "False"
    if unlock_fps:
        kv["FrameRateLimit"] = "0.000000"
    write_ini(game_ini, kv, SECTION_GAME)
    return kv


def apply_quality(user_ini, quality_pro=True, reflex=True):
    """
    写画质。CORE + EXTRA 全写——玩家没动过的项在 ini 里本来就没有，
    不主动补就等于不生效。键名不对时游戏会忽略，不会出问题。
    """
    kv = {}
    if reflex:
        kv["EAresIntSettingName::NvidiaReflexLowLatencySetting"] = "2"
    if quality_pro:
        kv.update(QUALITY_CORE)
        kv.update(QUALITY_EXTRA)
    write_ini(user_ini, kv, "Settings")
    return kv
