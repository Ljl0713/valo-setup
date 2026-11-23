# -*- coding: utf-8 -*-
"""
valo_state —— 配置持久化 / 日志 / 单实例 / 诊断导出
配置带 schema 版本，旧版自动迁移；文件损坏自动重建；日志超限自动轮转。
"""
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from ctypes import wintypes

SCHEMA = 2
LOG_MAX = 512 * 1024

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)


def data_dir():
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, "ValoSetup")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.dirname(os.path.abspath(__file__))
    return d


DATA_DIR = data_dir()
CONF_PATH = os.path.join(DATA_DIR, "config.json")
LOG_PATH = os.path.join(DATA_DIR, "valosetup.log")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")

DEFAULTS = {
    "schema": SCHEMA,
    "monitor_id": None,
    "game": {"w": 1280, "h": 960, "hz": None},
    "native": None,
    "auto": True,
    "topmost": False,
    "guide_done": False,
    "user_ini": None,
    "backup_keep": 10,
}


# ---------------------------------------------------------------- 日志

def log(msg):
    line = "%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        if os.path.isfile(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX:
            old = LOG_PATH + ".1"
            if os.path.exists(old):
                os.remove(old)
            os.replace(LOG_PATH, old)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def log_tail(n=80):
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except OSError:
        return ""


# ---------------------------------------------------------------- 配置

def fresh():
    """深拷贝一份默认配置——浅拷贝会让 DEFAULTS 被就地改掉"""
    return json.loads(json.dumps(DEFAULTS))


def _migrate(d):
    """v1 没有 schema 字段，结构基本兼容，补齐默认值即可。"""
    out = fresh()
    out.update(d or {})
    out["schema"] = SCHEMA
    g = out.get("game") or {}
    if not g.get("w") or not g.get("h"):
        out["game"] = dict(DEFAULTS["game"])
    else:
        out["game"] = {"w": int(g["w"]), "h": int(g["h"]), "hz": g.get("hz")}
    if out.get("native"):
        n = out["native"]
        out["native"] = {"w": int(n["w"]), "h": int(n["h"]), "hz": n.get("hz")}
    return out


def load():
    if not os.path.isfile(CONF_PATH):
        return fresh()
    try:
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        need_save = (not isinstance(raw, dict)) or raw.get("schema") != SCHEMA
        conf = _migrate(raw)
        if need_save:
            # 旧版配置补齐字段后立刻落盘，避免每次启动都重新迁移
            save(conf)
        return conf
    except (OSError, ValueError, KeyError, TypeError) as e:
        bad = CONF_PATH + ".bad"
        try:
            shutil.copy2(CONF_PATH, bad)
        except OSError:
            pass
        log("配置读取失败，已重建：%r（备份 %s）" % (e, bad))
        conf = fresh()
        save(conf)
        return conf


def save(conf):
    conf["schema"] = SCHEMA
    tmp = CONF_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONF_PATH)
        return True
    except OSError as e:
        log("配置保存失败：%r" % (e,))
        return False


# ---------------------------------------------------------------- 单实例

_MUTEX = None


def single_instance(name="Local\\ValoSetup_single"):
    """返回 True 表示是唯一实例；False 表示已有实例在跑。"""
    global _MUTEX
    ctypes.set_last_error(0)
    _MUTEX = _k32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


# ---------------------------------------------------------------- 诊断

def diagnose(monitor=None, extra=None):
    lines = []
    lines.append("== VALO SETUP 诊断 ==")
    lines.append("时间: %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("系统: %s %s (%s)" % (platform.system(), platform.release(),
                                      platform.version()))
    lines.append("Python: %s" % sys.version.replace("\n", " "))
    lines.append("打包: %s" % getattr(sys, "frozen", False))
    lines.append("程序目录: %s" % os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                                              else os.path.abspath(__file__)))
    lines.append("数据目录: %s" % DATA_DIR)
    try:
        u = ctypes.WinDLL("user32")
        lines.append("系统 DPI: %s" % u.GetDpiForSystem())
        lines.append("屏幕: %d×%d" % (u.GetSystemMetrics(0), u.GetSystemMetrics(1)))
    except Exception:
        pass
    try:
        lines.append("管理员: %s" % bool(ctypes.windll.shell32.IsUserAnAdmin()))
    except Exception:
        pass
    if monitor:
        lines.append("显示器: %s (%s)" % (monitor.get("monitor"), monitor.get("device")))
        lines.append("显示器ID: %s" % monitor.get("monitor_id"))
        lines.append("原生: %s" % (monitor.get("native"),))
        c = monitor.get("current")
        lines.append("当前: %s" % (c,))
        lines.append("模式数: %d" % len(monitor.get("modes") or {}))
    if extra:
        for k, v in extra.items():
            lines.append("%s: %s" % (k, v))
    lines.append("")
    lines.append("== 最近日志 ==")
    lines.append(log_tail(60))
    return "\n".join(lines)


def write_diagnose(text):
    p = os.path.join(DATA_DIR, "diagnose-%s.txt" % time.strftime("%Y%m%d-%H%M%S"))
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p
    except OSError:
        return None


def copy_clipboard(text):
    try:
        p = subprocess.run(["clip"], input=text.encode("gbk", "replace"),
                           creationflags=0x08000000, timeout=8)
        return p.returncode == 0
    except Exception:
        return False


def crash_dump(exc_text):
    p = os.path.join(DATA_DIR, "crash-%s.log" % time.strftime("%Y%m%d-%H%M%S"))
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(exc_text)
        log("崩溃：%s" % p)
        return p
    except OSError:
        return None
