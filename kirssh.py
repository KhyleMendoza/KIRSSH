"""
KIRSSH - open, upload and download files on your other computer.

Sign in once with the other computer's address, username and password.
KIRSSH remembers it (the password is encrypted with your Windows account)
and connects by itself next time.

Addresses can be typed the way you would in File Explorer:
    192.168.203.6
    \\\\192.168.203.6
    \\\\192.168.203.6\\Users\\Khyle\\Documents      (opens that folder)
    \\\\LK105\\D$\\Shared

Requires:  pip install paramiko tkinterdnd2
(tkinterdnd2 is optional - it enables dragging files in from File Explorer)
"""

import base64
import ctypes
import datetime
import getpass
import hashlib
import json
import math
import random
import os
import posixpath
import queue
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter import font as tkfont

try:
    import paramiko
except ImportError:
    _r = tk.Tk()
    _r.withdraw()
    from tkinter import messagebox
    messagebox.showerror("KIRSSH", "KIRSSH needs one more component.\n\nOpen Command Prompt and run:\n\n"
                                   "    pip install paramiko")
    raise SystemExit(1)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BaseTk = TkinterDnD.Tk
except Exception:
    DND_FILES = None
    BaseTk = tk.Tk

APP = "KIRSSH"
VERSION = "1.0.0"
MONO = "Consolas"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP)
OLD_CONFIG_DIR = os.path.join(os.path.dirname(CONFIG_DIR), "KIRSHH")
CONFIG_FILE = os.path.join(CONFIG_DIR, "kirssh_config.json")
KNOWN_HOSTS = os.path.join(CONFIG_DIR, "known_hosts")
IS_WINDOWS = os.name == "nt"
FONT = "Segoe UI"
PART_SUFFIX = ".kirssh-part"
OLD_SUFFIX = ".kirssh-old"

C = {
    "bg": "#f5f6f8",
    "surface": "#ffffff",
    "sidebar": "#f5f6f8",
    "border": "#e1e4e9",
    "text": "#1d2633",
    "muted": "#667080",
    "subtle": "#a0a7b2",
    "primary": "#0f766e",
    "primary_hover": "#0b5f58",
    "primary_soft": "#e7f4f1",
    "brand": "#0f2420",
    "brand_line": "#2a5c4f",
    "brand_text": "#a8c9bf",
    "accent_light": "#fbbf24",
    "hover": "#eef0f3",
    "danger": "#c53030",
    "danger_soft": "#fdeeee",
    "success": "#16794a",
    "success_soft": "#e8f5ee",
    "warn": "#8a5a00",
    "warn_soft": "#fff5dc",
    "folder": "#e8a93a",
    "folder_fill": "#f8d67e",
}

ICON_PATHS = {
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    "folder-open": '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    "folder-plus": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/><path d="M12 10v6M9 13h6"/>',
    "folder-up": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/><path d="M12 17v-6M9 14l3-3 3 3"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "file-text": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 13h8M8 17h8M8 9h2"/>',
    "file-sheet": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 12h8v6H8zM12 12v6M8 15h8"/>',
    "file-image": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><circle cx="10" cy="12" r="2"/><path d="m20 17-2-2a2 2 0 0 0-2.8 0L9 21"/>',
    "file-zip": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 6h2M10 10h2M10 14h2M10 18h2"/>',
    "file-code": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m10 13-2 2 2 2M14 17l2-2-2-2"/>',
    "file-media": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m10 11 5 3-5 3z"/>',
    "home": '<path d="M3 10l9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "pencil": '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "arrow-left": '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    "drive": '<rect x="2" y="13" width="20" height="8" rx="2"/><path d="M5.5 13 8 4h8l2.5 9"/><path d="M6 17h.01M10 17h.01"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    "settings": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M9.9 4.24A9 9 0 0 1 12 4c6.5 0 10 7 10 7a18 18 0 0 1-2.16 3.19M6.6 6.6A18 18 0 0 0 2 12s3.5 7 10 7a9 9 0 0 0 5.4-1.6M2 2l20 20"/>',
}

FILE_KINDS = {
    "sheet": ("file-sheet", "#1e7e45", "#e6f4ea"),
    "doc": ("file-text", "#2b5fc4", "#e8effc"),
    "pdf": ("file-text", "#c53030", "#fdecec"),
    "image": ("file-image", "#7c4dbd", "#f1eafb"),
    "zip": ("file-zip", "#8a6a2d", "#f7f0e1"),
    "code": ("file-code", "#475569", "#eef1f5"),
    "media": ("file-media", "#c2410c", "#fdf0e8"),
    "slides": ("file-text", "#c2410c", "#fdf0e8"),
    "other": ("file", "#6b7280", "#f3f4f6"),
}
EXTENSIONS = {
    ".xlsx": ("sheet", "Excel workbook"), ".xls": ("sheet", "Excel workbook"), ".xlsm": ("sheet", "Excel workbook"),
    ".csv": ("sheet", "CSV file"), ".docx": ("doc", "Word document"), ".doc": ("doc", "Word document"),
    ".txt": ("doc", "Text document"), ".rtf": ("doc", "Rich text document"), ".md": ("doc", "Text document"),
    ".log": ("doc", "Log file"), ".pdf": ("pdf", "PDF document"), ".pptx": ("slides", "PowerPoint presentation"),
    ".ppt": ("slides", "PowerPoint presentation"), ".png": ("image", "PNG image"), ".jpg": ("image", "JPEG image"),
    ".jpeg": ("image", "JPEG image"), ".gif": ("image", "GIF image"), ".bmp": ("image", "Bitmap image"),
    ".webp": ("image", "WebP image"), ".svg": ("image", "SVG image"), ".ico": ("image", "Icon"),
    ".zip": ("zip", "ZIP archive"), ".rar": ("zip", "RAR archive"), ".7z": ("zip", "7-Zip archive"),
    ".gz": ("zip", "Compressed file"), ".tar": ("zip", "Archive"), ".py": ("code", "Python file"),
    ".js": ("code", "JavaScript file"), ".html": ("code", "Web page"), ".css": ("code", "Style sheet"),
    ".json": ("code", "JSON file"), ".xml": ("code", "XML file"), ".bat": ("code", "Batch file"),
    ".ps1": ("code", "PowerShell script"), ".sql": ("code", "SQL file"), ".ini": ("code", "Settings file"),
    ".exe": ("code", "Application"), ".msi": ("code", "Installer"), ".dll": ("code", "System file"),
    ".mp3": ("media", "Audio"), ".wav": ("media", "Audio"), ".m4a": ("media", "Audio"),
    ".mp4": ("media", "Video"), ".mkv": ("media", "Video"), ".avi": ("media", "Video"), ".mov": ("media", "Video"),
}


class IconSet:
    def __init__(self, root, scale):
        self.root = root
        self.scale = scale
        self.cache = {}

    def _make(self, key, svg):
        if key not in self.cache:
            try:
                self.cache[key] = tk.PhotoImage(master=self.root, data=svg, format="svg")
            except tk.TclError:
                self.cache[key] = ""
        return self.cache[key]

    def get(self, name, color, size=16, fill="none", width=2):
        px = max(8, round(size * self.scale))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 24 24">'
               f'<g fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
               f'stroke-linejoin="round">{ICON_PATHS[name]}</g></svg>')
        return self._make((name, color, px, fill, width), svg)

    LOGO_MARK = ('<path d="M8 6v12"/><path d="M8.6 12.4 16.6 6"/><path d="M12.8 5.9h3.9v3.9"/>'
                 '<path d="M10.6 10.9 16.4 18"/>')

    def logo(self, size=40):
        """The KIRSSH mark: a K whose arm is an arrow (sending files)."""
        px = max(16, round(size * self.scale))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 24 24">'
               f'<rect x="0.5" y="0.5" width="23" height="23" rx="6" fill="{C["primary"]}"/>'
               f'<g fill="none" stroke="#ffffff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">'
               f'{self.LOGO_MARK}</g></svg>')
        return self._make(("logo", px), svg)

    def logo_light(self, size=56):
        """White version of the mark for use on the brand gradient."""
        px = max(16, round(size * self.scale))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 24 24">'
               f'<rect x="0.5" y="0.5" width="23" height="23" rx="6.5" fill="#ffffff" fill-opacity="0.16"/>'
               f'<g fill="none" stroke="#ffffff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">'
               f'{self.LOGO_MARK}</g></svg>')
        return self._make(("logo_light", px), svg)


icons = None


def human_size(n):
    if n is None:
        return ""
    n = float(n)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_date(t):
    if not t:
        return ""
    try:
        dt = datetime.datetime.fromtimestamp(t)
    except (OSError, OverflowError, ValueError):
        return ""
    clock = dt.strftime("%I:%M %p").lstrip("0")
    today = datetime.date.today()
    if dt.date() == today:
        return f"Today, {clock}"
    if dt.date() == today - datetime.timedelta(days=1):
        return f"Yesterday, {clock}"
    if dt.year == today.year:
        return f"{dt.strftime('%b')} {dt.day}, {clock}"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def fmt_duration(seconds):
    seconds = max(int(round(seconds)), 1)
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = round(seconds / 60)
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def file_kind(name, is_dir, drive=False):
    """Returns (icon image, type name)."""
    if drive:
        return icons.get("drive", C["muted"], 18), "Local disk"
    if is_dir:
        return icons.get("folder", C["folder"], 18, fill=C["folder_fill"], width=1.6), "Folder"
    ext = os.path.splitext(name)[1].lower()
    kind, type_name = EXTENSIONS.get(ext, ("other", f"{ext[1:].upper()} file" if ext else "File"))
    icon, stroke, fill = FILE_KINDS[kind]
    return icons.get(icon, stroke, 18, fill=fill, width=1.6), type_name


def drive_label(d):
    return f"Local Disk ({d})"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def migrate_old_settings():
    if os.path.isdir(CONFIG_DIR) or not os.path.isdir(OLD_CONFIG_DIR):
        return
    try:
        shutil.copytree(OLD_CONFIG_DIR, CONFIG_DIR)
        old_file = os.path.join(CONFIG_DIR, "kirshh_config.json")
        if os.path.exists(old_file) and not os.path.exists(CONFIG_FILE):
            os.replace(old_file, CONFIG_FILE)
    except OSError:
        pass


def load_config():
    migrate_old_settings()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault("pcs", {})
    cfg.setdefault("auto_connect", True)
    cfg.setdefault("show_hidden", False)
    return cfg


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


def parse_address(text):
    r"""Understands every way people usually write a computer address:

        192.168.203.6        LK105          192.168.203.6:2222
        \\192.168.203.6      \\LK105        khyle@192.168.203.6
        \\192.168.203.6\Users\Khyle\Documents   -> opens C:\Users\Khyle\Documents
        \\LK105\D$\Shared                       -> opens D:\Shared
        ssh://khyle@192.168.203.6/C:/Users

    Returns (host, port, username or None, start folder or None).
    """
    t = text.strip().strip('"').strip()
    low = t.lower()
    for prefix in ("ssh://", "sftp://", "file://"):
        if low.startswith(prefix):
            t = t[len(prefix):]
            break
    t = t.replace("\\", "/").lstrip("/")
    hostpart, _, rest = t.partition("/")
    user = None
    if "@" in hostpart:
        user, hostpart = hostpart.rsplit("@", 1)
    port = 22
    if hostpart.count(":") == 1:
        h, p = hostpart.split(":")
        if p.isdigit():
            hostpart, port = h, int(p)
    path = None
    segs = [s for s in rest.split("/") if s]
    if segs:
        if re.fullmatch(r"[A-Za-z][$:]", segs[0]):
            drive, segs = segs[0][0].upper() + ":", segs[1:]
        else:
            drive = "C:"
        path = "/" + "/".join([drive] + segs)
    return hostpart.strip(), port, (user or None), path


def unc_parts(text):
    r"""For  \\nas05\Public\Reports  -> (True, "/Public/Reports");  \\nas05 -> (True, None);
    plain names/IPs -> (False, None)."""
    t = text.strip().strip('"').strip()
    if not t.startswith(("\\\\", "//")):
        return False, None
    segs = [s for s in t.replace("\\", "/").split("/") if s][1:]
    return True, ("/" + "/".join(segs)) if segs else None


def friendly_error(err):
    msg = str(err) or err.__class__.__name__
    low = msg.lower()
    if isinstance(err, PermissionError) or "denied" in low or "permission" in low:
        return "Windows didn't allow this. The file may be open in another program, or you may not have access to it."
    if isinstance(err, FileNotFoundError) or "no such file" in low:
        return "That file or folder couldn't be found. It may have been moved or deleted."
    if isinstance(err, FileExistsError) or "exists" in low:
        return "Something with that name already exists here."
    if isinstance(err, (socket.timeout, TimeoutError, EOFError)) or "timed out" in low:
        return "The other computer stopped responding."
    return msg


if IS_WINDOWS:
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _dpapi(data, encrypt):
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = _BLOB()
        fn = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
        if not fn(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)):
            raise OSError("DPAPI failed")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))


def encrypt_password(pw):
    if not pw or not IS_WINDOWS:
        return None
    try:
        return base64.b64encode(_dpapi(pw.encode("utf-8"), True)).decode("ascii")
    except Exception:
        return None


def decrypt_password(token):
    if not token or not IS_WINDOWS:
        return ""
    try:
        return _dpapi(base64.b64decode(token), False).decode("utf-8")
    except Exception:
        return ""


_host_keys_lock = threading.Lock()


class _RememberHostKey(paramiko.MissingHostKeyPolicy):
    """First connection to a computer: trust it and remember its key."""

    def missing_host_key(self, client, hostname, key):
        client.get_host_keys().add(hostname, key.get_name(), key)
        with _host_keys_lock:
            try:
                keys = paramiko.HostKeys()
                if os.path.exists(KNOWN_HOSTS):
                    keys.load(KNOWN_HOSTS)
                keys.add(hostname, key.get_name(), key)
                keys.save(KNOWN_HOSTS)
            except (OSError, paramiko.SSHException):
                pass


def forget_host_key(host, port=22):
    hostname = host if port == 22 else f"[{host}]:{port}"
    with _host_keys_lock:
        try:
            keys = paramiko.HostKeys(KNOWN_HOSTS)
            if hostname in keys:
                del keys[hostname]
                keys.save(KNOWN_HOSTS)
        except (OSError, paramiko.SSHException):
            pass


def fingerprint(key):
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode("ascii").rstrip("=")


def unique_name(name, exists):
    base, ext = os.path.splitext(name)
    n = 2
    while True:
        candidate = f"{base} ({n}){ext}"
        if not exists(candidate):
            return candidate
        n += 1


class Cancelled(Exception):
    pass


class RemoteFS:
    """Files on the other computer over SFTP (paths look like /C:/Users/Khyle)."""

    kind = "ssh"

    def __init__(self, sftp, home, drives, transport=None):
        self.sftp = sftp
        self.home = home
        self.drives = drives
        self.transport = transport

    def mkdir(self, p):
        self.sftp.mkdir(p)

    def rename(self, a, b):
        self.sftp.rename(a, b)

    def download_file(self, remote, local):
        self.sftp.get(remote, local)

    def signature(self, p):
        """(size, modified time) - used to notice when someone else changed a file."""
        a = self.sftp.stat(p)
        return a.st_size or 0, a.st_mtime

    def open_transfer(self):
        return SftpTransfer(self.transport)

    def special(self, key):
        if not key:
            return self.home
        for c in (posixpath.join(self.home, key), posixpath.join(self.home, "OneDrive", key)):
            try:
                if stat.S_ISDIR(self.sftp.stat(c).st_mode or 0):
                    return c
            except IOError:
                pass
        return None

    def normalize(self, p):
        p = p.strip().strip('"').replace("\\", "/")
        if not p:
            return self.home
        if len(p) >= 2 and p[1] == ":" and not p.startswith("/"):
            p = "/" + p
        if p == "/":
            return "/"
        try:
            return self.sftp.normalize(p)
        except IOError:
            return p

    @staticmethod
    def join(a, b):
        return posixpath.join(a, b)

    @staticmethod
    def parent(p):
        s = p.rstrip("/")
        if not s:
            return "/"
        return posixpath.dirname(s) or "/"

    def listdir(self, p):
        if p == "/" and self.drives:
            return [{"name": d, "is_dir": True, "size": None, "mtime": None, "drive": True} for d in self.drives]
        items = []
        for a in self.sftp.listdir_attr(p):
            is_dir = stat.S_ISDIR(a.st_mode or 0)
            items.append({"name": a.filename, "is_dir": is_dir,
                          "size": None if is_dir else a.st_size, "mtime": a.st_mtime})
        return items

    def exists(self, p):
        try:
            self.sftp.stat(p)
            return True
        except IOError:
            return False

    def delete(self, p, is_dir):
        if is_dir:
            for a in self.sftp.listdir_attr(p):
                self.delete(posixpath.join(p, a.filename), stat.S_ISDIR(a.st_mode or 0))
            self.sftp.rmdir(p)
        else:
            self.sftp.remove(p)


class SftpTransfer:
    """File copying over its own SFTP channel, so browsing stays smooth during a transfer."""

    def __init__(self, transport):
        self.sftp = transport.open_sftp_client()

    def listdir(self, p):
        return [(a.filename, stat.S_ISDIR(a.st_mode or 0), a.st_size or 0, a.st_atime, a.st_mtime)
                for a in self.sftp.listdir_attr(p)]

    def stat(self, p):
        a = self.sftp.stat(p)
        return a.st_size or 0, a.st_atime, a.st_mtime

    def exists(self, p):
        try:
            self.sftp.stat(p)
            return True
        except IOError:
            return False

    def mkdir(self, p):
        self.sftp.mkdir(p)

    def put(self, src, dst, cb):
        self.sftp.put(src, dst, callback=cb)

    def get(self, src, dst, cb):
        self.sftp.get(src, dst, callback=cb)

    def utime(self, p, times):
        self.sftp.utime(p, times)

    def remove(self, p):
        self.sftp.remove(p)

    def replace(self, tmp, dst):
        """Move a finished copy over dst. The old file stays until the new one is in place."""
        try:
            self.sftp.posix_rename(tmp, dst)
            return
        except IOError:
            pass
        if not self.exists(dst):
            self.sftp.rename(tmp, dst)
            return
        old = dst + OLD_SUFFIX
        if self.exists(old):
            self.sftp.remove(old)
        self.sftp.rename(dst, old)
        try:
            self.sftp.rename(tmp, dst)
        except Exception:
            self.sftp.rename(old, dst)
            raise
        try:
            self.sftp.remove(old)
        except IOError:
            pass

    def close(self):
        self.sftp.close()


def list_shares(server):
    """Names of the shared folders on a computer or NAS (hidden admin shares like C$ are left out)."""
    from ctypes import wintypes as wt

    class SHARE_INFO_1(ctypes.Structure):
        _fields_ = [("netname", wt.LPWSTR), ("type", wt.DWORD), ("remark", wt.LPWSTR)]

    buf = ctypes.c_void_p()
    read, total, resume = wt.DWORD(), wt.DWORD(), wt.DWORD(0)
    res = ctypes.windll.netapi32.NetShareEnum(ctypes.c_wchar_p("\\\\" + server), 1, ctypes.byref(buf),
                                              wt.DWORD(0xFFFFFFFF), ctypes.byref(read), ctypes.byref(total),
                                              ctypes.byref(resume))
    if res not in (0, 234):
        raise OSError(res, ctypes.FormatError(res).strip())
    try:
        if not buf.value or not read.value:
            return []
        arr = ctypes.cast(buf, ctypes.POINTER(SHARE_INFO_1 * read.value)).contents
        return sorted((s.netname for s in arr if (s.type & 0xFF) == 0 and not s.netname.endswith("$")),
                      key=str.lower)
    finally:
        if buf.value:
            ctypes.windll.netapi32.NetApiBufferFree(buf)


def smb_login(server, user, pw):
    """Sign in to \\\\server with a username/password (only needed when one was typed)."""
    from ctypes import wintypes as wt

    class NETRESOURCEW(ctypes.Structure):
        _fields_ = [("dwScope", wt.DWORD), ("dwType", wt.DWORD), ("dwDisplayType", wt.DWORD),
                    ("dwUsage", wt.DWORD), ("lpLocalName", wt.LPWSTR), ("lpRemoteName", wt.LPWSTR),
                    ("lpComment", wt.LPWSTR), ("lpProvider", wt.LPWSTR)]

    remote = f"\\\\{server}\\IPC$"
    nr = NETRESOURCEW(0, 0, 0, 0, None, remote, None, None)
    res = ctypes.windll.mpr.WNetAddConnection2W(ctypes.byref(nr), pw or None, user or None, 0)
    if res == 1219:
        return None
    if res != 0:
        raise OSError(res, ctypes.FormatError(res).strip())
    return remote


def smb_logout(remote):
    if remote:
        try:
            ctypes.windll.mpr.WNetCancelConnection2W(remote, 0, True)
        except Exception:
            pass


def copy_with_progress(src, dst, cb):
    total = os.path.getsize(src)
    done = 0
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            chunk = fi.read(1024 * 1024)
            if not chunk:
                break
            fo.write(chunk)
            done += len(chunk)
            cb(done, total)
    if total == 0:
        cb(0, 0)


class ShareFS(RemoteFS):
    """A computer or NAS reached through Windows file sharing.
    Paths look like /Public/Reports  (= \\\\nas05\\Public\\Reports); "/" lists the shared folders."""

    kind = "smb"

    def __init__(self, server, shares, home):
        self.server = server
        self.drives = shares
        self.home = home
        self.sftp = self.transport = None

    def unc(self, p):
        segs = [s for s in p.split("/") if s]
        return "\\\\" + self.server + ("\\" + "\\".join(segs) if segs else "")

    def special(self, key):
        return self.home if not key else None

    def normalize(self, p):
        p = p.strip().strip('"').replace("\\", "/")
        if not p:
            return self.home
        if p.startswith("//"):
            parts = [s for s in p.split("/") if s]
            p = "/" + "/".join(parts[1:]) if parts and parts[0].lower() == self.server.lower() else p
        if not p.startswith("/"):
            p = "/" + p
        return posixpath.normpath(p) if p != "/" else "/"

    def listdir(self, p):
        if p == "/":
            self.drives = list_shares(self.server)
            return [{"name": d, "is_dir": True, "size": None, "mtime": None, "drive": True} for d in self.drives]
        items = []
        with os.scandir(self.unc(p)) as it:
            for e in it:
                try:
                    st = e.stat()
                    is_dir = e.is_dir()
                    hidden = bool(getattr(st, "st_file_attributes", 0) & 0x6)
                    if hidden:
                        continue
                    items.append({"name": e.name, "is_dir": is_dir,
                                  "size": None if is_dir else st.st_size, "mtime": st.st_mtime})
                except OSError:
                    continue
        return items

    def exists(self, p):
        return os.path.exists(self.unc(p))

    def mkdir(self, p):
        os.mkdir(self.unc(p))

    def rename(self, a, b):
        os.rename(self.unc(a), self.unc(b))

    def delete(self, p, is_dir):
        if is_dir:
            shutil.rmtree(self.unc(p))
        else:
            os.remove(self.unc(p))

    def download_file(self, remote, local):
        shutil.copyfile(self.unc(remote), local)

    def open_transfer(self):
        return ShareTransfer(self)


class ShareTransfer:
    def __init__(self, fs):
        self.fs = fs

    def listdir(self, p):
        out = []
        with os.scandir(self.fs.unc(p)) as it:
            for e in it:
                st = e.stat()
                out.append((e.name, e.is_dir(), st.st_size, st.st_atime, st.st_mtime))
        return out

    def stat(self, p):
        st = os.stat(self.fs.unc(p))
        return st.st_size, st.st_atime, st.st_mtime

    def exists(self, p):
        return os.path.exists(self.fs.unc(p))

    def mkdir(self, p):
        os.mkdir(self.fs.unc(p))

    def put(self, src, dst, cb):
        copy_with_progress(src, self.fs.unc(dst), cb)

    def get(self, src, dst, cb):
        copy_with_progress(self.fs.unc(src), dst, cb)

    def utime(self, p, times):
        os.utime(self.fs.unc(p), times)

    def remove(self, p):
        os.remove(self.fs.unc(p))

    def replace(self, tmp, dst):
        os.replace(self.fs.unc(tmp), self.fs.unc(dst))

    def close(self):
        pass


class Btn(tk.Label):
    """Flat button with an optional icon. kind: primary, secondary, ghost, danger, link."""

    def __init__(self, master, text="", icon=None, command=None, kind="secondary", size=10,
                 padx=14, pady=7, icon_size=16, bold=None, family=None):
        self.kind, self.command, self.icon_name, self.icon_size = kind, command, icon, icon_size
        self.size = size
        self.family = family or FONT
        self.enabled = True
        weight = "bold" if (kind == "primary" if bold is None else bold) else "normal"
        self.weight = weight
        super().__init__(master, text=(" " + text) if (icon and text) else text, font=(self.family, size, weight),
                         padx=padx, pady=pady, bd=0, compound="left")
        self._paint(False)
        self.bind("<Enter>", lambda e: self._paint(True))
        self.bind("<Leave>", lambda e: self._paint(False))
        self.bind("<ButtonRelease-1>", self._click)

    def _palette(self):
        pbg = self.master.cget("bg")
        return {
            "primary": (C["primary"], "#ffffff", C["primary_hover"], None, "#ffffff"),
            "secondary": (C["surface"], C["text"], C["hover"], C["border"], C["muted"]),
            "ghost": (pbg, C["text"], C["hover"], None, C["muted"]),
            "danger": (pbg, C["danger"], C["danger_soft"], None, C["danger"]),
            "link": (pbg, C["primary"], pbg, None, C["primary"]),
        }[self.kind]

    def _paint(self, hover):
        bg, fg, hbg, border, icol = self._palette()
        if not self.enabled:
            hover = False
            fg = icol = C["subtle"]
            if self.kind == "primary":
                bg, fg, icol = "#9fcbc4", "#ffffff", "#ffffff"
        b = hbg if hover else bg
        self.configure(bg=b, fg=fg, cursor="hand2" if self.enabled else "arrow",
                       highlightthickness=1 if border else 0,
                       highlightbackground=border or b, highlightcolor=border or b)
        if self.kind == "link":
            self.configure(font=(self.family, self.size, f"{self.weight} underline" if hover else self.weight))
        if self.icon_name:
            self.configure(image=icons.get(self.icon_name, icol, self.icon_size))

    def _click(self, e):
        if self.enabled and self.command and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self.command()

    def set_enabled(self, flag):
        if flag != self.enabled:
            self.enabled = flag
            self._paint(False)

    def set_text(self, text):
        self.configure(text=(" " + text) if (self.icon_name and text) else text)


def make_entry(parent, show="", width=34):
    return tk.Entry(parent, font=(FONT, 11), relief="flat", bd=0, bg="#ffffff", fg=C["text"],
                    insertbackground=C["text"], highlightthickness=1, highlightbackground=C["border"],
                    highlightcolor=C["primary"], show=show, width=width)


def make_check(parent, text, var, command=None):
    bg = parent.cget("bg")
    return tk.Checkbutton(parent, text=" " + text, variable=var, command=command, bg=bg, activebackground=bg,
                          fg=C["text"], activeforeground=C["text"], font=(FONT, 10), bd=0,
                          highlightthickness=0, selectcolor="#ffffff", cursor="hand2", anchor="w")


def label(parent, text="", size=10, color="text", bold=False, **kw):
    return tk.Label(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                    fg=C.get(color, color), bg=kw.pop("bg", parent.cget("bg")), **kw)


def hline(parent, color=None):
    return tk.Frame(parent, height=1, bg=color or C["border"])


class SearchBox(tk.Frame):
    def __init__(self, parent, placeholder, on_change):
        super().__init__(parent, bg="#ffffff", highlightthickness=1, highlightbackground=C["border"],
                         highlightcolor=C["primary"])
        self.placeholder = placeholder
        self.on_change = on_change
        tk.Label(self, image=icons.get("search", C["subtle"], 15), bg="#ffffff").pack(side="left", padx=(9, 4))
        self.var = tk.StringVar()
        self.entry = tk.Entry(self, textvariable=self.var, font=(FONT, 10), relief="flat", bd=0, bg="#ffffff",
                              fg=C["subtle"], insertbackground=C["text"], width=24)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._ph = True
        self.var.set(placeholder)
        self.entry.bind("<FocusIn>", self._in)
        self.entry.bind("<FocusOut>", self._out)
        self.entry.bind("<Escape>", lambda e: self.clear())
        self.var.trace_add("write", lambda *a: None if self._ph else self.on_change(self.get()))

    def _in(self, _e):
        if self._ph:
            self._ph = False
            self.var.set("")
            self.entry.configure(fg=C["text"])

    def _out(self, _e):
        if not self.var.get():
            self._ph = True
            self.var.set(self.placeholder)
            self.entry.configure(fg=C["subtle"])

    def get(self):
        return "" if self._ph else self.var.get().strip()

    def clear(self):
        if not self._ph:
            self.var.set("")
            if self.focus_get() is not self.entry:
                self._out(None)


class Dialog(tk.Toplevel):
    def __init__(self, app, title, message=None, icon=None, icon_color=None, width=420):
        super().__init__(app)
        self.app = app
        self.result = None
        self.withdraw()
        self.title(title)
        self.configure(bg=C["surface"])
        self.resizable(False, False)
        self.transient(app)
        body = tk.Frame(self, bg=C["surface"], padx=24, pady=22)
        body.pack(fill="both", expand=True)
        head = tk.Frame(body, bg=C["surface"])
        head.pack(fill="x")
        if icon:
            tk.Label(head, image=icons.get(icon, icon_color or C["primary"], 22), bg=C["surface"]).pack(
                side="left", padx=(0, 10))
        label(head, title, 13, bold=True).pack(side="left")
        if message:
            label(body, message, 10, "muted", justify="left", wraplength=width - 48, anchor="w").pack(
                fill="x", pady=(10, 0))
        self.content = tk.Frame(body, bg=C["surface"])
        self.content.pack(fill="both", expand=True)
        hline(self).pack(fill="x")
        self.buttons = tk.Frame(self, bg=C["bg"], padx=24, pady=14)
        self.buttons.pack(fill="x")
        self.minwidth = width
        self.bind("<Escape>", lambda e: self.close(None))
        self.protocol("WM_DELETE_WINDOW", lambda: self.close(None))

    def add_button(self, text, value, kind="secondary", default=False):
        b = Btn(self.buttons, text, command=lambda: self.close(value), kind=kind)
        b.pack(side="right", padx=(8, 0))
        if default:
            self.bind("<Return>", lambda e: self.close(value))
        return b

    def show(self, focus=None):
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), round(self.minwidth * icons.scale))
        h = self.winfo_reqheight()
        x = self.app.winfo_rootx() + (self.app.winfo_width() - w) // 2
        y = self.app.winfo_rooty() + max(40, (self.app.winfo_height() - h) // 3)
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.grab_set()
        (focus or self).focus_set()
        self.wait_window()
        return self.result

    def close(self, value):
        self.result = value
        self.grab_release()
        self.destroy()


def ask_text(app, title, prompt, initial="", ok="Save", select_stem=False):
    d = Dialog(app, title, prompt)
    entry = make_entry(d.content, width=38)
    entry.pack(fill="x", ipady=7, pady=(12, 0))
    entry.insert(0, initial)
    stem = os.path.splitext(initial)[0] if select_stem else initial
    entry.select_range(0, len(stem))
    entry.icursor(len(stem))
    value = {}

    def submit():
        value["v"] = entry.get().strip()
        d.close("ok")

    Btn(d.buttons, ok, command=submit, kind="primary").pack(side="right", padx=(8, 0))
    d.add_button("Cancel", None)
    entry.bind("<Return>", lambda e: submit())
    return value.get("v") if d.show(entry) == "ok" and value.get("v") else None


def confirm(app, title, message, ok="OK", danger=False, icon="alert"):
    d = Dialog(app, title, message, icon=icon, icon_color=C["danger"] if danger else C["primary"])
    b = Btn(d.buttons, ok, command=lambda: d.close(True), kind="primary")
    if danger:
        b.configure(bg=C["danger"])
        b._palette = lambda: (C["danger"], "#ffffff", "#a82828", None, "#ffffff")
        b._paint(False)
    b.pack(side="right", padx=(8, 0))
    d.add_button("Cancel", False)
    return bool(d.show())


def choose(app, title, message, options, icon="alert"):
    """options: list of (text, value, kind) shown right-to-left as given (first = rightmost)."""
    d = Dialog(app, title, message, icon=icon)
    for text, value, kind in options:
        d.add_button(text, value, kind)
    return d.show()


def show_message(app, title, message, kind="error"):
    icon, color = {"error": ("alert", C["danger"]), "info": ("help", C["primary"]),
                   "ok": ("check", C["success"])}[kind]
    d = Dialog(app, title, message, icon=icon, icon_color=color)
    d.add_button("OK", None, "primary", default=True)
    d.show()


class BrandPanel(tk.Canvas):
    """Left half of the sign-in screen: a flat illustration of a server room.

    Moving parts: server lights blink, the desk computer types SSH commands and shows
    transfer progress, data packets travel along the network cable, and the clock ticks.
    """

    BG = "#0f2420"
    RACK = "#143029"
    RACK_EDGE = "#1f4a3f"
    UNIT = "#183a32"
    CONE = "#163a32"
    FLOOR = "#122a24"
    BAR = "#0a1a17"
    LED_ON = ("#4ade80", "#4ade80", "#a7f3d0", "#fbbf24")
    LED_OFF = "#1d4238"
    SCRIPT = (("cmd", "ssh khyle@192.168.203.6"), ("out", "Connected to LK105"),
              ("cmd", "put report.xlsx"), ("bar", ""),
              ("cmd", "get NOVEMBER_DELIVERY.xlsx"), ("bar", ""),
              ("out", "2 files transferred"))

    def __init__(self, parent, app):
        super().__init__(parent, highlightthickness=0, bd=0, bg=self.BG)
        self.app = app
        self.s = app.scale
        self._job = None
        self._anim = None
        self._t0 = time.time()
        self._ready = False
        self._last_led = 0.0
        self._last_clock = ""
        self._term_cache = []
        self.timeline, start = [], 0.0
        for kind, text in self.SCRIPT:
            dur = {"cmd": len(text) * 0.055 + 0.6, "type": len(text) * 0.05 + 0.6, "out": 0.7, "bar": 1.6}[kind]
            self.timeline.append((kind, text, start, dur))
            start += dur
        self.loop_len = start + 2.6
        self.bind("<Configure>", self._schedule)
        self.bind("<Map>", lambda e: self._start())
        self.bind("<Unmap>", lambda e: self._stop())

    def _schedule(self, _e=None):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(30, self._draw)

    def _draw(self):
        self._job = None
        s = self.s
        w, h = max(self.winfo_width(), 2), max(self.winfo_height(), 2)
        S = lambda v: round(v * s)
        self.delete("all")
        rnd = random.Random(7)
        bar_h = S(34)
        fy = h - bar_h - S(26)
        ry0 = round(h * 0.33)

        for lx in (w * 0.30, w * 0.74):
            self.create_polygon(lx - S(15), S(92), lx + S(15), S(92), lx + S(120), fy, lx - S(120), fy,
                                fill=self.CONE, outline="")
            self.create_line(lx, 0, lx, S(84), fill=self.RACK_EDGE, width=max(1, S(2)))
            self.create_rectangle(lx - S(18), S(84), lx + S(18), S(92), fill="#2f6b5c", outline="")
            self.create_rectangle(lx - S(14), S(92), lx + S(14), S(94), fill="#fde9b8", outline="")

        self.leds = []
        cw, gap = S(84), S(24)
        text_right, text_bottom = round(w * 0.56), round(h * 0.25) + S(200)
        x = -S(30)
        while x < w:
            self.create_rectangle(x, ry0, x + cw, fy, fill=self.RACK, outline=self.RACK_EDGE)
            self.create_rectangle(x + S(4), ry0 - S(6), x + cw - S(4), ry0, fill=self.RACK_EDGE, outline="")
            uy = ry0 + S(10)
            while uy + S(12) < fy - S(8):
                quiet = x < text_right and uy < text_bottom
                self.create_rectangle(x + S(8), uy, x + cw - S(8), uy + S(11),
                                      fill="#152f28" if quiet else self.UNIT, outline="")
                if quiet:
                    uy += S(17)
                    continue
                for k in range(3):
                    lx0 = x + S(14) + k * S(8)
                    color = rnd.choice(self.LED_ON)
                    on = rnd.random() < 0.7
                    led = self.create_rectangle(lx0, uy + S(4), lx0 + S(4), uy + S(7),
                                                fill=color if on else self.LED_OFF, outline="")
                    self.leds.append((led, color))
                self.create_line(x + cw - S(30), uy + S(5), x + cw - S(14), uy + S(5), fill="#20463c")
                uy += S(17)
            x += cw + gap

        self.create_rectangle(0, fy, w, h - bar_h, fill=self.FLOOR, outline="")
        self.create_line(0, fy, w, fy, fill=self.RACK_EDGE)

        dx0, dx1 = round(w * 0.53), w - S(26)
        dy = fy - S(88)
        self.create_rectangle(dx0 + S(14), dy + S(10), dx1 - S(14), fy, fill="#173a32", outline="#24504a")
        self.create_rectangle(dx0, dy, dx1, dy + S(10), fill="#22493f", outline="")
        mid = (dx0 + dx1) / 2
        self.create_line(mid, dy + S(20), mid, fy - S(8), fill="#24504a")
        for yy in (dy + S(34), dy + S(56)):
            self.create_line(dx0 + S(34), yy, mid - S(20), yy, fill="#2c5d50", width=max(1, S(2)))
        self.create_oval(dx1 - S(40), dy + S(24), dx1 - S(34), dy + S(30), fill="#4ade80", outline="")
        self.create_oval(dx1 - S(28), dy + S(24), dx1 - S(22), dy + S(30), fill="#fbbf24", outline="")

        mw = (dx1 - dx0) * 0.80
        mh = mw * 0.60
        mx0, mx1 = mid - mw / 2, mid + mw / 2
        my1 = dy - S(24)
        my0 = my1 - mh
        self.create_rectangle(mid - S(7), my1, mid + S(7), dy, fill="#1f463c", outline="")
        self.create_rectangle(mid - S(36), dy - S(5), mid + S(36), dy, fill="#1f463c", outline="")
        self.create_rectangle(mx0, my0, mx1, my1, fill="#1f463c", outline="")
        sx0, sy0, sx1, sy1 = mx0 + S(7), my0 + S(7), mx1 - S(7), my1 - S(7)
        self.create_rectangle(sx0, sy0, sx1, sy1, fill="#081613", outline="")
        self.create_rectangle(sx0, sy0, sx1, sy0 + S(14), fill="#0e211c", outline="")
        for k, col in enumerate(("#f26b5b", "#f5b942", "#4ade80")):
            cx = sx0 + S(8) + k * S(10)
            self.create_oval(cx, sy0 + S(4), cx + S(6), sy0 + S(10), fill=col, outline="")
        self.create_text(sx1 - S(6), sy0 + S(7), text="ssh", fill="#6b9a8c", font=(MONO, 7), anchor="e")
        line_h = S(14)
        n_lines = max(3, int((sy1 - sy0 - S(22)) // line_h))
        self.term = [self.create_text(sx0 + S(8), sy0 + S(20) + i * line_h, text="", anchor="nw",
                                      fill="#e6f2ee", font=(MONO, 8)) for i in range(n_lines)]
        self._term_cache = [None] * n_lines

        cx_rack = round(w * 0.16)
        cable_y = fy + S(12)
        self.cable = [(dx0 + S(22), fy), (dx0 + S(22), cable_y), (cx_rack, cable_y), (cx_rack, fy - S(34))]
        self.create_line(*[c for p in self.cable for c in p], fill="#2a5c4f", width=max(2, S(3)),
                         joinstyle="round")
        self.create_rectangle(cx_rack - S(6), fy - S(40), cx_rack + S(6), fy - S(32), fill="#2f6b5c", outline="")
        seg = [math.dist(self.cable[i], self.cable[i + 1]) for i in range(len(self.cable) - 1)]
        self.cable_len, self.cable_seg = sum(seg), seg
        self.packets = [self.create_rectangle(0, 0, 0, 0, fill="#fbbf24", outline="") for _ in range(3)]

        tx = S(56)
        ty = round(h * 0.25)
        self.create_rectangle(tx, ty, tx + S(46), ty + S(3), fill="#e8a33d", outline="")
        self.create_text(tx, ty + S(30), text="SECURE FILE TRANSFER", fill="#7dd3c0", font=(MONO, 9, "bold"),
                         anchor="nw")
        self.create_text(tx, ty + S(52), text=APP, fill="#ffffff", font=(MONO, 38, "bold"), anchor="nw")
        self.create_text(tx, ty + S(124), text="Open, upload and download files on your other office "
                                               "computers - over SSH, no USB needed.",
                         fill="#d8ebe5", font=(FONT, 11), anchor="nw", width=max(S(200), round(w * 0.44)))

        self.create_rectangle(0, h - bar_h, w, h, fill=self.BAR, outline="")
        self.clock = self.create_text(tx, h - bar_h / 2, text="", fill="#ffffff", font=(MONO, 10, "bold"),
                                      anchor="w")
        self.clock_info = self.create_text(tx, h - bar_h / 2, text="", fill="#8fb5a9", font=(MONO, 9),
                                           anchor="w")
        self._last_clock = ""
        self._ready = True
        self._tick(force=True)
        self._start()

    def _start(self):
        if self._anim is None and self._ready and self.winfo_ismapped():
            self._anim = self.after(33, self._tick)

    def _stop(self):
        if self._anim is not None:
            self.after_cancel(self._anim)
            self._anim = None

    def _point_on_cable(self, d):
        for (x0, y0), (x1, y1), L in zip(self.cable, self.cable[1:], self.cable_seg):
            if d <= L:
                f = d / L if L else 0
                return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            d -= L
        return self.cable[-1]

    def _terminal_lines(self, t):
        lines = []
        typing = False
        for kind, text, start, dur in self.timeline:
            if t < start:
                break
            p = min(1.0, (t - start) / dur)
            if kind in ("cmd", "type"):
                n = int(len(text) * min(1.0, p / 0.85))
                typing = n < len(text)
                prompt = "$ " if kind == "cmd" else ""
                lines.append((f"{prompt}{text[:n]}", "#e6f2ee"))
            elif kind == "out":
                lines.append((f"  {text}", "#4ade80"))
            else:
                filled = int(16 * p)
                lines.append((f"  {'█' * filled}{'░' * (16 - filled)} {int(p * 100):3d}%", "#fbbf24"))
        if not typing and (t - self.timeline[-1][2]) < self.timeline[-1][3] + 2.6:
            lines.append(("$ ", "#e6f2ee"))
        if lines and int(t * 2.2) % 2 == 0:
            text, color = lines[-1]
            lines[-1] = (text + "▌", color)
        return lines[-len(self.term):]

    def _tick(self, force=False):
        self._anim = None
        if not self._ready or (not force and not self.winfo_ismapped()):
            return
        s = self.s
        now = time.time()
        t = now - self._t0

        if now - self._last_led > 0.22:
            self._last_led = now
            for led, color in random.sample(self.leds, min(6, len(self.leds))):
                on = self.itemcget(led, "fill") != self.LED_OFF
                self.itemconfigure(led, fill=self.LED_OFF if on else color)

        lines = self._terminal_lines(t % self.loop_len)
        lines += [("", "#e6f2ee")] * (len(self.term) - len(lines))
        for i, (item, line) in enumerate(zip(self.term, lines)):
            if self._term_cache[i] != line:
                self._term_cache[i] = line
                self.itemconfigure(item, text=line[0], fill=line[1])

        for k, pkt in enumerate(self.packets):
            d = ((t * 70 * s) + k * self.cable_len / len(self.packets)) % self.cable_len
            px, py = self._point_on_cable(d)
            self.coords(pkt, px - 3 * s, py - 3 * s, px + 3 * s, py + 3 * s)

        stamp = time.strftime("%I:%M %p").lstrip("0")
        if stamp != self._last_clock:
            self._last_clock = stamp
            info = time.strftime("%a, %b %d").upper()
            self.itemconfigure(self.clock, text=stamp)
            x1 = self.bbox(self.clock)[2]
            self.itemconfigure(self.clock_info, text=f"{info}   ·   {APP} / SSH / {VERSION}")
            self.coords(self.clock_info, x1 + round(14 * s), self.coords(self.clock)[1])
        if self.winfo_ismapped():
            self._anim = self.after(33, self._tick)


class PEntry(tk.Entry):
    """Entry with grey placeholder text; get() returns '' while the placeholder shows."""

    def __init__(self, parent, placeholder="", secret=False):
        super().__init__(parent, font=(FONT, 11), relief="flat", bd=0, bg="#ffffff", fg=C["text"],
                         insertbackground=C["text"], disabledbackground="#ffffff",
                         disabledforeground=C["subtle"])
        self.placeholder, self.secret, self.reveal, self._ph = placeholder, secret, False, False
        self.bind("<FocusIn>", lambda e: self._hide_ph(), add="+")
        self.bind("<FocusOut>", lambda e: self._show_ph(), add="+")
        self._show_ph()

    def _has_focus(self):
        try:
            return self.focus_get() is self
        except (KeyError, tk.TclError):
            return False

    def _show_ph(self):
        if self.placeholder and not self._ph and not tk.Entry.get(self):
            self._ph = True
            state = self.cget("state")
            self.configure(state="normal", show="", fg=C["subtle"])
            tk.Entry.insert(self, 0, self.placeholder)
            self.configure(state=state)

    def _hide_ph(self):
        if self._ph:
            self._ph = False
            state = self.cget("state")
            self.configure(state="normal")
            tk.Entry.delete(self, 0, "end")
            self.configure(state=state, fg=C["text"], show="•" if self.secret and not self.reveal else "")

    def get(self):
        return "" if self._ph else tk.Entry.get(self)

    def insert(self, index, text):
        if text:
            self._hide_ph()
            tk.Entry.insert(self, index, text)
        elif not self._has_focus():
            self._show_ph()

    def delete(self, first, last=None):
        if self._ph:
            return
        tk.Entry.delete(self, first, last)
        if not tk.Entry.get(self) and not self._has_focus():
            self._show_ph()

    def select_range(self, start, end):
        if not self._ph:
            tk.Entry.select_range(self, start, end)

    def set_reveal(self, flag):
        self.reveal = flag
        if not self._ph:
            self.configure(show="" if flag or not self.secret else "•")


RIGHT_BG = "#f7f8f6"


def mono(parent, text, size=8, color="text", bold=True, **kw):
    return tk.Label(parent, text=text, font=(MONO, size, "bold" if bold else "normal"),
                    fg=C.get(color, color), bg=kw.pop("bg", parent.cget("bg")), **kw)


class LoginScreen(tk.Frame):
    """Left: illustrated server room. Right: returning users see their saved computers
    (one click to connect); new users see a short form."""

    def __init__(self, app):
        super().__init__(app, bg=RIGHT_BG)
        self.app = app
        self.busy = False
        self.saved_rows = []
        BrandPanel(self, app).place(relx=0, rely=0, relwidth=0.5, relheight=1)
        right = tk.Frame(self, bg=RIGHT_BG)
        right.place(relx=0.5, rely=0, relwidth=0.5, relheight=1)
        mono(right, f"{APP}  ·  ENCRYPTED SSH CONNECTION", 7, "subtle", bold=False).place(
            relx=0.5, rely=1.0, y=-round(16 * app.scale), anchor="s")

        outer = tk.Frame(right, bg=RIGHT_BG)
        outer.place(relx=0.5, rely=0.47, anchor="center")
        width = round(380 * app.scale)

        hb = tk.Frame(outer, bg=RIGHT_BG)
        hb.pack(fill="x", pady=(0, 26))
        tk.Frame(hb, bg=C["primary"], width=max(2, round(3 * app.scale))).pack(side="left", fill="y")
        hi = tk.Frame(hb, bg=RIGHT_BG)
        hi.pack(side="left", fill="x", expand=True, padx=(20, 0))
        top = tk.Frame(hi, bg=RIGHT_BG)
        top.pack(fill="x")
        mono(top, "FILE ACCESS", 8, "primary").pack(side="left")
        mono(top, "SECURE ACCESS", 8, "muted").pack(side="right")
        tk.Label(top, image=icons.get("lock", C["muted"], 12), bg=RIGHT_BG).pack(side="right", padx=(0, 5))
        self.heading = tk.Label(hi, text="Welcome", font=(MONO, 22, "bold"), fg=C["text"], bg=RIGHT_BG,
                                anchor="w")
        self.heading.pack(fill="x", pady=(10, 0))
        self.subheading = label(hi, "", 10, "muted", anchor="w")
        self.subheading.pack(fill="x", pady=(4, 0))

        card = tk.Frame(outer, bg=RIGHT_BG)
        card.pack(fill="x")
        self.saved_slot = tk.Frame(card, bg=RIGHT_BG)
        self.msg_slot = tk.Frame(card, bg=RIGHT_BG)
        self.toggle_slot = tk.Frame(card, bg=RIGHT_BG)
        self.form = tk.Frame(card, bg=RIGHT_BG)
        for slot in (self.saved_slot, self.msg_slot, self.toggle_slot, self.form):
            slot.pack(fill="x")
        tk.Frame(card, bg=RIGHT_BG, width=width, height=0).pack()

        self.msg = tk.Frame(self.msg_slot, bg=C["danger_soft"], padx=12, pady=10)
        self.msg_icon = tk.Label(self.msg, bg=C["danger_soft"])
        self.msg_icon.pack(side="left", anchor="n", padx=(0, 8))
        self.msg_text = label(self.msg, "", 10, bg=C["danger_soft"], anchor="w", justify="left",
                              wraplength=width - round(60 * app.scale))
        self.msg_text.pack(side="left", fill="x", expand=True)

        self.toggle = Btn(self.toggle_slot, "Connect to a different computer", icon="monitor", kind="link",
                          command=self.expand_form, padx=0)

        f = self.form
        self.form_title = mono(f, "CONNECT TO A DIFFERENT COMPUTER", 8, "primary", anchor="w")
        self.addr_box, self.addr = self._field(f, "Computer address", "monitor", "192.168.203.6  or  \\\\LK105")
        self.user_box, self.user = self._field(f, "Username", "user", "Windows username on that computer")
        self.pw_box, self.pw = self._field(f, "Password", "lock", "Password", secret=True)
        self.eye = tk.Label(self.pw_box, image=icons.get("eye", C["subtle"], 17), bg="#ffffff", cursor="hand2")
        self.eye.pack(side="right", padx=(0, 12))
        self.eye.bind("<Button-1>", self._toggle_pw)

        self.remember = tk.BooleanVar(value=True)
        make_check(f, "Remember me on this computer", self.remember).pack(fill="x", pady=(0, 18))
        self.connect_btn = Btn(f, "CONNECT", kind="primary", command=self.submit, pady=12, size=10, family=MONO)
        self.connect_btn.pack(fill="x")

        hline(outer).pack(fill="x", pady=(26, 14))
        foot = tk.Frame(outer, bg=RIGHT_BG)
        foot.pack(fill="x")
        mono(foot, f"Version {VERSION}", 8, "muted", bold=False).pack(side="right")

        for w in (self.addr, self.user, self.pw):
            w.bind("<Return>", lambda e: self.submit())
        self.addr.bind("<FocusOut>", lambda e: self._autofill(), add="+")

    def _field(self, parent, title, icon, placeholder, secret=False):
        lbl = mono(parent, title.upper(), 8, "text", anchor="w")
        lbl.pack(fill="x")
        box = tk.Frame(parent, bg="#ffffff", highlightthickness=1, highlightbackground=C["border"],
                       highlightcolor=C["border"])
        box.pack(fill="x", pady=(7, 18))
        tk.Label(box, image=icons.get(icon, C["muted"], 16), bg="#ffffff").pack(side="left", padx=(14, 10))
        entry = PEntry(box, placeholder, secret)
        entry.pack(side="left", fill="x", expand=True, ipady=round(11 * self.app.scale))
        entry.bind("<FocusIn>", lambda e: box.configure(highlightbackground=C["primary"]), add="+")
        entry.bind("<FocusOut>", lambda e: box.configure(highlightbackground=C["border"]), add="+")
        if not hasattr(self, "first_label"):
            self.first_label = lbl
        return box, entry

    def refresh_saved(self):
        for w in self.saved_slot.winfo_children():
            w.destroy()
        self.saved_rows = []
        pcs = sorted(self.app.cfg["pcs"].items(), key=lambda kv: -kv[1].get("last_used", 0))
        for w in (self.addr, self.user, self.pw):
            w.configure(state="normal")
            w.delete(0, "end")
        for w in self.toggle_slot.winfo_children():
            if w is not self.toggle:
                w.destroy()
        self.saved_slot.configure(height=1)
        self.toggle_slot.configure(height=1)
        self.saved_slot.pack(fill="x", before=self.msg_slot)
        self.heading.configure(text="Welcome back" if pcs else "Welcome")
        self.subheading.configure(text="Choose a computer to open its files." if pcs else
                                  "Enter the other computer's details to connect.")
        if not pcs:
            self.form_title.pack_forget()
            self.toggle.pack_forget()
            self.form.pack(fill="x")
            return
        mono(self.saved_slot, "YOUR COMPUTERS", 8, "text", anchor="w").pack(fill="x", pady=(0, 8))
        for key, pc in pcs[:5]:
            self._saved_row(key, pc)
        self.form_title.pack(fill="x", pady=(0, 16), before=self.first_label)
        self.form.pack_forget()
        self.toggle.pack(anchor="w", pady=(16, 0))

    def expand_form(self, focus=True):
        self.toggle.pack_forget()
        if self.saved_slot.winfo_children() and self.saved_slot.winfo_manager():
            self.saved_slot.pack_forget()
            for w in self.toggle_slot.winfo_children():
                if w is not self.toggle:
                    w.destroy()
            Btn(self.toggle_slot, "Back to your computers", icon="arrow-left", kind="link",
                command=self.collapse_form, padx=0).pack(anchor="w", pady=(0, 16))
        self.form.pack(fill="x")
        if focus:
            self.addr.focus_set()

    def collapse_form(self):
        self.show_error("")
        self.refresh_saved()

    def _saved_row(self, key, pc):
        row = tk.Frame(self.saved_slot, bg="#ffffff", cursor="hand2", highlightthickness=1,
                       highlightbackground=C["border"], highlightcolor=C["border"])
        row.pack(fill="x", pady=4)
        icon = tk.Label(row, image=icons.get("monitor", C["primary"], 20), bg="#ffffff")
        icon.pack(side="left", padx=(16, 12), pady=13)
        txt = tk.Frame(row, bg="#ffffff")
        txt.pack(side="left", fill="x", expand=True)
        name = tk.Label(txt, text=pc.get("name") or key, font=(MONO, 10, "bold"), fg=C["text"], bg="#ffffff",
                        anchor="w")
        name.pack(fill="x")
        sub = label(txt, f"Signed in as {pc.get('shown_user') or pc.get('user', '')}", 9, "muted", anchor="w",
                    bg="#ffffff")
        sub.pack(fill="x")
        forget = tk.Label(row, image=icons.get("x", C["subtle"], 14), bg="#ffffff", cursor="hand2")
        forget.pack(side="right", padx=(4, 14))
        go = mono(row, "CONNECT", 8, "primary", bg="#ffffff")
        go.pack(side="right", padx=(0, 8))
        parts = (row, icon, txt, name, sub, forget, go)

        def paint(bg, border):
            if self.busy:
                return
            for p in parts:
                p.configure(bg=bg)
            row.configure(highlightbackground=border)

        for p in parts:
            p.bind("<Enter>", lambda e: paint(C["primary_soft"], C["primary"]))
            p.bind("<Leave>", lambda e: paint("#ffffff", C["border"]))
            if p is not forget:
                p.bind("<Button-1>", lambda e, k=key: self.use_saved(k))
        forget.bind("<Button-1>", lambda e, k=key: self.forget(k))
        self.saved_rows.append((key, go))

    def _toggle_pw(self, _e=None):
        self.pw.set_reveal(not self.pw.reveal)
        self.eye.configure(image=icons.get("eye-off" if self.pw.reveal else "eye", C["subtle"], 17))

    def _autofill(self):
        host, port, user, _p = parse_address(self.addr.get())
        pc = self.app.cfg["pcs"].get(self.app.pc_key(host, port)) if host else None
        if user and not self.user.get():
            self.user.insert(0, user)
        if pc:
            if not self.user.get():
                self.user.insert(0, pc.get("user", ""))
            if not self.pw.get():
                self.pw.insert(0, decrypt_password(pc.get("pw")))

    def _fill_form(self, key, pc, pw):
        for w, v in ((self.addr, key), (self.user, pc.get("user", "")), (self.pw, pw)):
            w.configure(state="normal")
            w.delete(0, "end")
            w.insert(0, v)

    def use_saved(self, key):
        if self.busy:
            return
        pc = self.app.cfg["pcs"].get(key, {})
        pw = decrypt_password(pc.get("pw"))
        self._fill_form(key, pc, pw)
        if pw or pc.get("no_password"):
            self.submit(from_saved=key)
        else:
            self.expand_form(focus=False)
            self.show_error("")
            self.show_info(f"Enter the password for {pc.get('name') or key}.")
            self.pw.focus_set()

    def forget(self, key):
        if self.busy:
            return
        if confirm(self.app, "Forget this computer?",
                   f"KIRSSH will forget the saved address and password for {key}.", ok="Forget", danger=True):
            self.app.cfg["pcs"].pop(key, None)
            if self.app.cfg.get("last_host") == key:
                self.app.cfg.pop("last_host", None)
            save_config(self.app.cfg)
            self.show_error("")
            self.refresh_saved()

    def submit(self, from_saved=None):
        if self.busy:
            return
        host, port, user_from_addr, start = parse_address(self.addr.get())
        user = self.user.get().strip() or (user_from_addr or "")
        if not host:
            self.show_error("Enter the address of the other computer, for example 192.168.203.6")
            self.addr.focus_set()
            return
        unc, share_path = unc_parts(self.addr.get())
        self.show_error("")
        self.connecting_key = from_saved
        self.app.connect(host, port, user, self.pw.get(), self.remember.get(), start,
                         unc=unc, share_path=share_path)

    def set_busy(self, busy, text="Connecting…"):
        self.busy = busy
        self.connect_btn.set_text(text.upper() if busy else "CONNECT")
        self.connect_btn.set_enabled(not busy)
        for w in (self.addr, self.user, self.pw):
            w.configure(state="disabled" if busy else "normal")
        key = getattr(self, "connecting_key", None)
        for k, go in self.saved_rows:
            go.configure(text="CONNECTING…" if busy and k == key else "CONNECT",
                         fg=C["subtle"] if busy and k != key else C["primary"])
        if busy:
            self._show_msg(text, "info")
        elif self.msg.cget("bg") == C["primary_soft"]:
            self._hide_msg()

    def _show_msg(self, text, kind):
        bg, icon, color = {"error": (C["danger_soft"], "alert", C["danger"]),
                           "info": (C["primary_soft"], "help", C["primary"])}[kind]
        if kind == "info" and self.busy:
            icon = "refresh"
        for w in (self.msg, self.msg_icon, self.msg_text):
            w.configure(bg=bg)
        self.msg_icon.configure(image=icons.get(icon, color, 16))
        self.msg_text.configure(text=text)
        top = (16, 0) if self.saved_slot.winfo_children() and self.saved_slot.winfo_manager() else (0, 18)
        self.msg.pack(fill="x", pady=top)


    def _hide_msg(self):
        self.msg.pack_forget()
        self.msg_slot.configure(height=1)

    def show_info(self, text):
        self._show_msg(text, "info")

    def show_error(self, text):
        if text:
            self._show_msg(text, "error")
        else:
            self._hide_msg()


class NavItem(tk.Frame):
    def __init__(self, parent, icon, text, command):
        super().__init__(parent, bg=C["sidebar"], cursor="hand2")
        self.icon_name, self.command, self.active = icon, command, False
        self.icon = tk.Label(self, bg=C["sidebar"])
        self.icon.pack(side="left", padx=(16, 10), pady=7)
        self.text = label(self, text, 10, anchor="w")
        self.text.pack(side="left", fill="x", expand=True)
        for w in (self, self.icon, self.text):
            w.bind("<Enter>", lambda e: self._paint(True))
            w.bind("<Leave>", lambda e: self._paint(False))
            w.bind("<Button-1>", lambda e: self.command())
        self._paint(False)

    def _paint(self, hover):
        if self.active:
            bg, fg, ic = C["primary_soft"], C["primary"], C["primary"]
        else:
            bg, fg, ic = (C["hover"] if hover else C["sidebar"]), C["text"], C["muted"]
        for w in (self, self.icon, self.text):
            w.configure(bg=bg)
        self.text.configure(fg=fg, font=(FONT, 10, "bold" if self.active else "normal"))
        self.icon.configure(image=icons.get(self.icon_name, ic, 17))

    def set_active(self, flag):
        if flag != self.active:
            self.active = flag
            self._paint(False)


class TransferBar(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["surface"])
        self.app = app
        hline(self).pack(fill="x", side="top")
        inner = tk.Frame(self, bg=C["surface"], padx=20, pady=12)
        inner.pack(fill="x")
        self.icon = tk.Label(inner, bg=C["surface"])
        self.icon.pack(side="left", padx=(0, 12))
        txt = tk.Frame(inner, bg=C["surface"])
        txt.pack(side="left", fill="x", expand=True)
        self.title = label(txt, "", 10, bold=True, anchor="w")
        self.title.pack(fill="x")
        self.detail = label(txt, "", 9, "muted", anchor="w")
        self.detail.pack(fill="x")
        self.actions = tk.Frame(inner, bg=C["surface"])
        self.actions.pack(side="right")
        self.progress = ttk.Progressbar(inner, length=round(260 * app.scale), maximum=100,
                                        style="Thin.Horizontal.TProgressbar")
        self._hide_job = None

    def _clear_actions(self):
        for w in self.actions.winfo_children():
            w.destroy()

    def start(self, title, upload):
        if self._hide_job:
            self.after_cancel(self._hide_job)
            self._hide_job = None
        self.icon.configure(image=icons.get("upload" if upload else "download", C["primary"], 22))
        self.title.configure(text=title)
        self.detail.configure(text="Getting ready…")
        self.progress["value"] = 0
        self.progress.pack(side="right", padx=(16, 16), before=self.actions)
        self._clear_actions()
        Btn(self.actions, "Cancel", command=self.app.cancel_event.set).pack(side="right")
        self.pack(side="bottom", fill="x")

    def update_progress(self, pct, title, detail):
        self.progress["value"] = pct
        self.title.configure(text=title)
        self.detail.configure(text=detail)

    def finish(self, status, title, detail, reveal=None):
        self.progress.pack_forget()
        icon, color = {"ok": ("check", C["success"]), "cancel": ("alert", C["warn"]),
                       "error": ("alert", C["danger"])}[status]
        self.icon.configure(image=icons.get(icon, color, 22))
        self.title.configure(text=title)
        self.detail.configure(text=detail)
        self._clear_actions()
        Btn(self.actions, icon="x", kind="ghost", command=self.hide, padx=6, pady=6).pack(side="right")
        if reveal:
            Btn(self.actions, "Show in folder", icon="folder-open", command=lambda: reveal_in_explorer(reveal)).pack(
                side="right", padx=(0, 6))
        if status == "ok":
            self._hide_job = self.after(12000, self.hide)

    def hide(self):
        self._hide_job = None
        self.pack_forget()


def reveal_in_explorer(path):
    try:
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            os.startfile(path)
    except OSError:
        pass


class BrowserScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app, bg=C["bg"])
        self.app = app
        self.path = ""
        self.items = []
        self.entries = {}
        self.history = []
        self.sort_key, self.sort_rev = "name", False
        self.place_paths = {}
        self._hover = None
        self._notice_job = None

        top = tk.Frame(self, bg=C["surface"])
        top.pack(fill="x")
        tb = tk.Frame(top, bg=C["surface"], padx=18, pady=10)
        tb.pack(fill="x")
        tk.Label(tb, image=icons.logo(26), bg=C["surface"]).pack(side="left")
        label(tb, APP, 13, bold=True).pack(side="left", padx=(8, 16))
        tk.Frame(tb, width=1, height=22, bg=C["border"]).pack(side="left", padx=(0, 16))
        tk.Label(tb, image=icons.get("monitor", C["muted"], 17), bg=C["surface"]).pack(side="left")
        self.pc_name = label(tb, "", 10, bold=True)
        self.pc_name.pack(side="left", padx=(8, 10))
        self.conn_dot = label(tb, "●  Connected", 9, "success")
        self.conn_dot.pack(side="left")
        Btn(tb, "Disconnect", icon="logout", kind="ghost", command=app.disconnect).pack(side="right")
        Btn(tb, "Settings", icon="settings", kind="ghost", command=app.open_settings).pack(side="right", padx=(0, 4))
        hline(top).pack(fill="x")

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(body, bg=C["sidebar"], width=round(210 * app.scale))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Frame(body, width=1, bg=C["border"]).pack(side="left", fill="y")

        main = tk.Frame(body, bg=C["surface"])
        main.pack(side="left", fill="both", expand=True)
        self.main = main
        self.transfer = TransferBar(main, app)

        head = tk.Frame(main, bg=C["surface"], padx=18, pady=12)
        head.pack(fill="x")
        self.back_btn = Btn(head, icon="arrow-left", kind="ghost", command=self.go_back, padx=6, pady=6)
        self.back_btn.pack(side="left")
        self.crumbs = tk.Frame(head, bg=C["surface"], cursor="xterm")
        self.crumbs.pack(side="left", fill="x", expand=True, padx=(6, 12))
        self.crumbs.bind("<Button-1>", lambda e: self.edit_path())
        self.path_entry = make_entry(head)
        self.path_entry.bind("<Return>", lambda e: self._path_entered())
        self.path_entry.bind("<Escape>", lambda e: self._end_edit())
        self.path_entry.bind("<FocusOut>", lambda e: self._end_edit())
        self.search = SearchBox(head, "Search this folder", lambda q: self._fill())
        self.search.pack(side="right")

        bar = tk.Frame(main, bg=C["surface"], padx=18)
        bar.pack(fill="x", pady=(0, 10))
        self.upload_btn = Btn(bar, "Upload files", icon="upload", kind="primary", command=app.upload_files)
        self.upload_btn.pack(side="left")
        self.upload_dir_btn = Btn(bar, "Upload folder", icon="folder-up", command=app.upload_folder)
        self.upload_dir_btn.pack(side="left", padx=(8, 0))
        Btn(bar, "New folder", icon="folder-plus", command=self.new_folder).pack(side="left", padx=(8, 0))
        tk.Frame(bar, width=1, height=24, bg=C["border"]).pack(side="left", padx=12)
        self.download_btn = Btn(bar, "Download", icon="download", command=app.download_selected)
        self.download_btn.pack(side="left")
        self.rename_btn = Btn(bar, "Rename", icon="pencil", kind="ghost", command=self.rename)
        self.rename_btn.pack(side="left", padx=(4, 0))
        self.delete_btn = Btn(bar, "Delete", icon="trash", kind="danger", command=self.delete)
        self.delete_btn.pack(side="left", padx=(4, 0))
        Btn(bar, icon="refresh", kind="ghost", command=self.refresh, padx=7, pady=7).pack(side="right")
        self.count_lbl = label(bar, "", 9, "muted")
        self.count_lbl.pack(side="right", padx=(0, 8))

        self.notice = tk.Frame(main, bg=C["primary_soft"], padx=14, pady=8)
        self.notice_icon = tk.Label(self.notice, bg=C["primary_soft"])
        self.notice_icon.pack(side="left", padx=(0, 8))
        self.notice_text = label(self.notice, "", 10, bg=C["primary_soft"], anchor="w")
        self.notice_text.pack(side="left", fill="x", expand=True)

        lf = tk.Frame(main, bg=C["surface"], padx=18)
        lf.pack(fill="both", expand=True, pady=(0, 6))
        self.list_frame = lf
        hline(lf).pack(fill="x")
        self.tree = ttk.Treeview(lf, columns=("modified", "type", "size"), style="Files.Treeview",
                                 selectmode="extended")
        s = app.scale
        for col, text, w, anchor, stretch in (("#0", "Name", 340, "w", True), ("modified", "Date modified", 170, "w", False),
                                              ("type", "Type", 160, "w", False), ("size", "Size", 100, "e", False)):
            self.tree.heading(col, text=text, anchor=anchor,
                              command=lambda c=col: self.set_sort({"#0": "name", "modified": "mtime",
                                                                   "type": "type", "size": "size"}[c]))
            self.tree.column(col, width=round(w * s), anchor=anchor, stretch=stretch, minwidth=round(60 * s))
        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview, style="Files.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("hover", background="#f6f8fb")

        self.empty = tk.Frame(lf, bg=C["surface"])
        self.empty_icon = tk.Label(self.empty, image=icons.get("folder-open", C["subtle"], 46, width=1.5),
                                   bg=C["surface"])
        self.empty_icon.pack()
        self.empty_title = label(self.empty, "", 12, bold=True)
        self.empty_title.pack(pady=(10, 2))
        self.empty_sub = label(self.empty, "", 10, "muted")
        self.empty_sub.pack()

        t = self.tree
        t.bind("<Double-1>", lambda e: self.open_selected() if t.identify_region(e.x, e.y) != "heading" else None)
        t.bind("<Return>", lambda e: self.open_selected())
        t.bind("<BackSpace>", lambda e: self.go_up())
        t.bind("<Alt-Left>", lambda e: self.go_back())
        t.bind("<Delete>", lambda e: self.delete())
        t.bind("<F2>", lambda e: self.rename())
        t.bind("<F5>", lambda e: self.refresh())
        t.bind("<Control-a>", lambda e: (t.selection_set(list(self.entries)), "break")[1])
        t.bind("<<TreeviewSelect>>", lambda e: self._update_actions())
        t.bind("<Button-3>", self._menu)
        t.bind("<Motion>", self._motion)
        t.bind("<Leave>", lambda e: self._set_hover(None))

        self.menu = tk.Menu(self, tearoff=0, bg=C["surface"], fg=C["text"], activebackground=C["primary_soft"],
                            activeforeground=C["text"], bd=0, font=(FONT, 10), relief="flat")

        if DND_FILES:
            for w in (self.tree, self.empty, self.empty_icon, self.empty_title, self.empty_sub):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<DropEnter>>", self._drop_enter)
                w.dnd_bind("<<DropPosition>>", lambda e: e.action)
                w.dnd_bind("<<DropLeave>>", self._drop_leave)
                w.dnd_bind("<<Drop>>", self._drop)

    def on_connected(self, display_name):
        self.pc_name.configure(text=display_name)
        self.conn_dot.configure(text="●  Connected", fg=C["success"])
        self.history.clear()
        self.path, self.items = "", []
        self.entries.clear()
        self.tree.delete(*self.tree.get_children())
        self.empty.place_forget()
        self.place_paths = {}
        self._build_sidebar()
        fs = self.app.fs
        if fs.kind == "smb":
            self.place_paths = {None: fs.home}
            return

        def resolve():
            return {k: fs.special(k) for k in ("Desktop", "Documents", "Downloads")}

        self.app.run_remote(resolve, self._places_resolved, on_error=lambda e: None)

    def _build_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()
        self.nav = {}
        fs = self.app.fs
        smb = fs.kind == "smb"
        places = ((None, "home", "Home"),) if smb else (
            (None, "home", "Home"), ("Desktop", "monitor", "Desktop"),
            ("Documents", "file-text", "Documents"), ("Downloads", "download", "Downloads"))
        if not (smb and fs.home == "/"):
            label(self.sidebar, "PLACES", 8, "subtle", bold=True, anchor="w").pack(fill="x", padx=18, pady=(18, 6))
            for key, icon, text in places:
                item = NavItem(self.sidebar, icon, text, lambda k=key: self.go_place(k))
                item.pack(fill="x", padx=8, pady=1)
                self.nav[("place", key)] = item
        drives = fs.drives
        title = "SHARED FOLDERS" if smb else ("DRIVES" if drives else "COMPUTER")
        label(self.sidebar, title, 8, "subtle", bold=True, anchor="w").pack(fill="x", padx=18, pady=(20, 6))
        if smb and drives:
            item = NavItem(self.sidebar, "monitor", "All shared folders", lambda: self.go("/"))
            item.pack(fill="x", padx=8, pady=1)
            self.nav[("drive", "/")] = item
        for d in drives or ([] if smb else ["/"]):
            text = (drive_label(d) if re.fullmatch(r"[A-Za-z]:", d) else d) if d != "/" else "All files"
            item = NavItem(self.sidebar, "folder" if smb else "drive", text,
                           lambda d=d: self.go("/" + d if d != "/" else "/"))
            item.pack(fill="x", padx=8, pady=1)
            self.nav[("drive", d)] = item

    def _places_resolved(self, result):
        self.place_paths = {None: self.app.fs.home, **result}
        self._highlight_nav()

    def _highlight_nav(self):
        if not hasattr(self, "nav"):
            return
        active = None
        for key, p in {None: self.app.fs.home if self.app.fs else None, **self.place_paths}.items():
            if p and self.path.rstrip("/").lower() == p.rstrip("/").lower():
                active = ("place", key)
        if active is None:
            first = self.path.strip("/").split("/")[0]
            match = next((k for k in self.nav if k[0] == "drive" and k[1] != "/" and first and
                          k[1].lower() == first.lower()), None)
            if match:
                active = match
            elif ("drive", "/") in self.nav and self.path.strip("/") == "":
                active = ("drive", "/")
        for k, item in self.nav.items():
            item.set_active(k == active)

    def go(self, path, add_history=True, on_fail=None):
        fs = self.app.fs
        if fs is None:
            return

        def fetch():
            p = fs.normalize(path)
            return p, fs.listdir(p)

        def done(result):
            if add_history and self.path and self.path != result[0]:
                self.history.append(self.path)
            self.path, self.items = result
            self.search.clear()
            self._fill()
            self._render_crumbs()
            self._highlight_nav()
            self.tree.focus_set()
            self.app.configure(cursor="")

        def fail(err):
            self.app.configure(cursor="")
            self.count_lbl.configure(text="")
            if on_fail:
                on_fail(err)
            else:
                show_message(self.app, "Can't open this folder", friendly_error(err))

        self.app.configure(cursor="watch")
        self.count_lbl.configure(text="Loading…")
        self.app.run_remote(fetch, done, fail)

    def go_place(self, key):
        if key is None:
            self.go(self.app.fs.home)
            return
        p = self.place_paths.get(key)
        if p:
            self.go(p)
            return
        fs = self.app.fs

        def found(p):
            if p:
                self.place_paths[key] = p
                self.go(p)
            else:
                self.show_notice(f"The other computer doesn't have a {key} folder.", "warn")

        self.app.run_remote(lambda: fs.special(key), found)

    def go_back(self):
        if self.history:
            self.go(self.history.pop(), add_history=False)

    def go_up(self):
        if self.path and self.path != "/":
            self.go(RemoteFS.parent(self.path))

    def refresh(self):
        if self.path:
            self.go(self.path, add_history=False)

    def _crumb_parts(self):
        parts = [(self.app.session["name"], "/")]
        acc = ""
        for seg in [s for s in self.path.strip("/").split("/") if s]:
            acc += "/" + seg
            parts.append((drive_label(seg) if re.fullmatch(r"[A-Za-z]:", seg) else seg, acc))
        return parts

    def _render_crumbs(self):
        for w in self.crumbs.winfo_children():
            w.destroy()
        parts = self._crumb_parts()
        if len(parts) > 5:
            parts = parts[:1] + [("…", None)] + parts[-3:]
        for i, (text, target) in enumerate(parts):
            if i:
                tk.Label(self.crumbs, image=icons.get("chevron-right", C["subtle"], 14),
                         bg=C["surface"]).pack(side="left", padx=2)
            last = i == len(parts) - 1
            lbl = label(self.crumbs, text, 12 if last else 11, "text" if last else "muted", bold=last,
                        padx=4, pady=2, cursor="hand2" if target and not last else "xterm")
            lbl.pack(side="left")
            if target and not last:
                lbl.bind("<Enter>", lambda e, l=lbl: l.configure(bg=C["hover"], fg=C["text"]))
                lbl.bind("<Leave>", lambda e, l=lbl: l.configure(bg=C["surface"], fg=C["muted"]))
                lbl.bind("<Button-1>", lambda e, p=target: self.go(p))
            else:
                lbl.bind("<Button-1>", lambda e: self.edit_path())
        self.back_btn.set_enabled(bool(self.history))

    def edit_path(self):
        self.crumbs.pack_forget()
        self.path_entry.delete(0, "end")
        if self.app.fs and self.app.fs.kind == "smb":
            self.path_entry.insert(0, self.app.fs.unc(self.path))
        else:
            shown = self.path[1:] if re.match(r"^/[A-Za-z]:", self.path) else self.path
            self.path_entry.insert(0, shown.replace("/", "\\") if re.match(r"^[A-Za-z]:", shown) else shown)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(6, 12), ipady=5, before=self.search)
        self.path_entry.focus_set()
        self.path_entry.select_range(0, "end")

    def _end_edit(self):
        if self.path_entry.winfo_ismapped():
            self.path_entry.pack_forget()
            self.crumbs.pack(side="left", fill="x", expand=True, padx=(6, 12), before=self.search)

    def _path_entered(self):
        text = self.path_entry.get().strip()
        self._end_edit()
        if text.startswith("\\\\") and not (self.app.fs and self.app.fs.kind == "smb"):
            _h, _p, _u, start = parse_address(text)
            text = start or "/"
        if text:
            self.go(text)

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        self.entries.clear()
        self._hover = None
        q = self.search.get().lower()
        items = [e for e in self.items if not e["name"].endswith((PART_SUFFIX, OLD_SUFFIX))]
        if not self.app.cfg.get("show_hidden"):
            items = [e for e in items if not e["name"].startswith(".") and e["name"].lower() not in
                     ("desktop.ini", "thumbs.db", "ntuser.dat")]
        if q:
            items = [e for e in items if q in e["name"].lower()]
        key = self.sort_key

        def sort_val(e):
            if key == "size":
                return e["size"] or 0
            if key == "mtime":
                return e["mtime"] or 0
            if key == "type":
                return file_kind(e["name"], e["is_dir"])[1].lower()
            return e["name"].lower()

        dirs = sorted([e for e in items if e["is_dir"]], key=sort_val, reverse=self.sort_rev)
        files = sorted([e for e in items if not e["is_dir"]], key=sort_val, reverse=self.sort_rev)
        for i, e in enumerate(dirs + files):
            iid = f"i{i}"
            self.entries[iid] = e
            img, type_name = file_kind(e["name"], e["is_dir"], e.get("drive"))
            name = drive_label(e["name"]) if e.get("drive") else e["name"]
            self.tree.insert("", "end", iid=iid, text="  " + name, image=img,
                             values=(fmt_date(e["mtime"]), type_name, human_size(e["size"])))
        for col, k, text in (("#0", "name", "Name"), ("modified", "mtime", "Date modified"),
                             ("type", "type", "Type"), ("size", "size", "Size")):
            arrow = ("  ↓" if self.sort_rev else "  ↑") if k == self.sort_key else ""
            self.tree.heading(col, text=text + arrow)

        if not items:
            if q:
                self.empty_icon.configure(image=icons.get("search", C["subtle"], 46, width=1.5))
                self.empty_title.configure(text="No matches")
                self.empty_sub.configure(text=f'Nothing in this folder matches "{q}".')
            else:
                self.empty_icon.configure(image=icons.get("folder-open", C["subtle"], 46, width=1.5))
                self.empty_title.configure(text="This folder is empty")
                self.empty_sub.configure(text="Drag files here from File Explorer, or click Upload files."
                                         if DND_FILES else "Click Upload files to add something here.")
            self.empty.place(in_=self.tree, relx=0.5, rely=0.4, anchor="center")
        else:
            self.empty.place_forget()
        self._update_actions()

    def set_sort(self, key):
        if self.sort_key == key:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_key, self.sort_rev = key, False
        self._fill()

    def _motion(self, e):
        self._set_hover(self.tree.identify_row(e.y) or None)

    def _set_hover(self, iid):
        if iid == self._hover:
            return
        for old, add in ((self._hover, False), (iid, True)):
            if old and self.tree.exists(old):
                self.tree.item(old, tags=("hover",) if add else ())
        self._hover = iid

    def selected(self):
        return [self.entries[i] for i in self.tree.selection() if i in self.entries]

    def _update_actions(self):
        sel = self.selected()
        real = [e for e in sel if not e.get("drive")]
        self.download_btn.set_enabled(bool(real) and not self.app.transfer_running)
        self.delete_btn.set_enabled(bool(real))
        self.rename_btn.set_enabled(len(real) == 1)
        can_upload = bool(self.path) and (self.path != "/" or not self.app.fs or not self.app.fs.drives)
        self.upload_btn.set_enabled(can_upload and not self.app.transfer_running)
        self.upload_dir_btn.set_enabled(can_upload and not self.app.transfer_running)
        if sel:
            self.count_lbl.configure(text=f"{plural(len(sel), 'item')} selected")
        else:
            self.count_lbl.configure(text=plural(len(self.entries), "item"))

    def open_selected(self):
        sel = self.selected()
        if len(sel) != 1:
            return
        e = sel[0]
        p = RemoteFS.join(self.path, e["name"])
        if e["is_dir"]:
            self.go(p)
        else:
            self.app.open_remote_file(p, e["name"])

    def _menu(self, event):
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        sel = self.selected()
        m = self.menu
        m.delete(0, "end")
        if sel:
            m.add_command(label="   Open", command=self.open_selected, state="normal" if len(sel) == 1 else "disabled")
            m.add_command(label="   Download", command=self.app.download_selected)
            m.add_separator()
            m.add_command(label="   Rename", command=self.rename, state="normal" if len(sel) == 1 else "disabled")
            m.add_command(label="   Delete", command=self.delete)
            m.add_separator()
        m.add_command(label="   Upload files here", command=self.app.upload_files)
        m.add_command(label="   New folder", command=self.new_folder)
        m.add_command(label="   Refresh", command=self.refresh)
        m.tk_popup(event.x_root, event.y_root)

    def show_notice(self, text, kind="info", sticky=False):
        bg, fg, icon = {"info": (C["primary_soft"], C["primary"], "help"),
                        "warn": (C["warn_soft"], C["warn"], "alert"),
                        "ok": (C["success_soft"], C["success"], "check"),
                        "drop": (C["primary_soft"], C["primary"], "upload")}[kind]
        for w in (self.notice, self.notice_icon, self.notice_text):
            w.configure(bg=bg)
        self.notice_icon.configure(image=icons.get(icon, fg, 17))
        self.notice_text.configure(text=text, fg=C["text"])
        self.notice.pack(fill="x", padx=18, pady=(0, 10), before=self.list_frame)
        if self._notice_job:
            self.after_cancel(self._notice_job)
            self._notice_job = None
        if not sticky:
            self._notice_job = self.after(6000, self.hide_notice)

    def hide_notice(self):
        self._notice_job = None
        self.notice.pack_forget()

    def _drop_enter(self, e):
        folder = self.app.folder_display_name(self.path)
        self.app.style.configure("Files.Treeview", background=C["primary_soft"], fieldbackground=C["primary_soft"])
        self.show_notice(f"Drop to upload to  {folder}", "drop", sticky=True)
        return e.action

    def _drop_leave(self, e):
        self.app.style.configure("Files.Treeview", background=C["surface"], fieldbackground=C["surface"])
        self.hide_notice()
        return e.action

    def _drop(self, e):
        self._drop_leave(e)
        paths = [p for p in self.tk.splitlist(e.data) if p]
        if paths:
            self.after(10, lambda: self.app.upload_paths(paths))
        return e.action

    def new_folder(self):
        if not self.app.fs or self.path in ("", "/") and self.app.fs.drives:
            return
        existing = {e["name"].lower() for e in self.items}
        default = "New folder" if "new folder" not in existing else unique_name(
            "New folder", lambda n: n.lower() in existing)
        name = ask_text(self.app, "New folder", "Name the new folder:", default, ok="Create")
        if not name:
            return
        p = RemoteFS.join(self.path, name)
        self.app.run_remote(lambda: self.app.fs.mkdir(p),
                            lambda _: (self.refresh(), self.show_notice(f'Folder "{name}" created.', "ok")))

    def rename(self):
        sel = [e for e in self.selected() if not e.get("drive")]
        if len(sel) != 1:
            return
        old = sel[0]["name"]
        new = ask_text(self.app, "Rename", "Enter a new name:", old, ok="Rename", select_stem=not sel[0]["is_dir"])
        if not new or new == old:
            return
        a, b = RemoteFS.join(self.path, old), RemoteFS.join(self.path, new)
        self.app.run_remote(lambda: self.app.fs.rename(a, b), lambda _: self.refresh())

    def delete(self):
        sel = [e for e in self.selected() if not e.get("drive")]
        if not sel:
            return
        if len(sel) == 1:
            what = f'"{sel[0]["name"]}"' + (" and everything in it" if sel[0]["is_dir"] else "")
            title = "Delete this folder?" if sel[0]["is_dir"] else "Delete this file?"
        else:
            what = f"these {len(sel)} items"
            title = f"Delete {len(sel)} items?"
        if not confirm(self.app, title, f"{what[0].upper() + what[1:]} will be permanently deleted from "
                                        f"{self.app.session['name']}. This can't be undone.",
                       ok="Delete", danger=True, icon="trash"):
            return
        targets = [(RemoteFS.join(self.path, e["name"]), e["is_dir"]) for e in sel]
        fs = self.app.fs

        def work():
            for p, is_dir in targets:
                fs.delete(p, is_dir)

        self.app.run_remote(work, lambda _: (self.refresh(),
                                             self.show_notice(f"Deleted {plural(len(targets), 'item')}.", "ok")))


def open_settings_dialog(app):
    d = Dialog(app, "Settings", icon="settings", width=480)
    c = d.content
    label(c, "Save downloaded files to", 10, "muted", anchor="w").pack(fill="x", pady=(14, 4))
    row = tk.Frame(c, bg=C["surface"])
    row.pack(fill="x")
    path_var = tk.StringVar(value=app.download_dir())
    e = make_entry(row, width=34)
    e.configure(textvariable=path_var, state="readonly", readonlybackground="#fafbfc")
    e.pack(side="left", fill="x", expand=True, ipady=6)

    def change():
        p = filedialog.askdirectory(parent=d, initialdir=path_var.get(), title="Choose where downloads are saved")
        if p:
            path_var.set(os.path.normpath(p))

    Btn(row, "Change…", command=change).pack(side="left", padx=(8, 0))
    auto = tk.BooleanVar(value=app.cfg.get("auto_connect", True))
    hidden = tk.BooleanVar(value=app.cfg.get("show_hidden", False))
    make_check(c, "Connect automatically when KIRSSH opens", auto).pack(fill="x", pady=(16, 4))
    make_check(c, "Show hidden and system files", hidden).pack(fill="x")
    d.add_button("Done", True, "primary", default=True)
    d.add_button("Cancel", None)
    if d.show():
        app.cfg["download_dir"] = path_var.get()
        app.cfg["auto_connect"] = bool(auto.get())
        app.cfg["show_hidden"] = bool(hidden.get())
        save_config(app.cfg)
        if app.fs is not None:
            app.browser._fill()


class App(BaseTk):
    CONNECT_TIMEOUT = 30

    def __init__(self):
        super().__init__()
        global icons, MONO
        self.withdraw()
        families = set(tkfont.families(self))
        MONO = next((f for f in ("Cascadia Mono", "Consolas", "Courier New") if f in families), "Courier")
        self.title(APP)
        self.configure(bg=C["bg"])
        self.scale = max(1.0, self.winfo_fpixels("1i") / 96.0)
        icons = IconSet(self, self.scale)
        self.icons = icons
        self.iconphoto(True, icons.logo(32))
        self._setup_style()

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(round(1240 * self.scale), sw - 40), min(round(780 * self.scale), sh - 80)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
        self.minsize(min(round(940 * self.scale), sw - 40), min(round(600 * self.scale), sh - 80))

        self.cfg = load_config()
        self.client = self.sftp = self.transport = self.fs = None
        self.session = None
        self.remote_lock = threading.Lock()
        self.ui_queue = queue.Queue()
        self.transfer_running = False
        self.cancel_event = threading.Event()
        self.connecting = False
        self._connect_token = None
        self._watched = {}
        self._watch_job = None

        self.login = LoginScreen(self)
        self.browser = BrowserScreen(self)
        self.show_login()
        self._fade_in()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self._drain_queue)
        self.after(5000, self._watchdog)

        last = self.cfg.get("last_host")
        pc = self.cfg["pcs"].get(last) if last else None
        if pc and self.cfg.get("auto_connect") and (pc.get("pw") or pc.get("no_password")):
            self.after(250, lambda: self.login.use_saved(last))

    def _fade_in(self, step=0):
        if step == 0:
            try:
                self.attributes("-alpha", 0.0)
            except tk.TclError:
                self.deiconify()
                return
            self.deiconify()
        alpha = min(1.0, step / 12)
        self.attributes("-alpha", alpha)
        if alpha < 1.0:
            self.after(16, lambda: self._fade_in(step + 1))

    def _setup_style(self):
        s = ttk.Style(self)
        self.style = s
        s.theme_use("clam")
        row_h = round(34 * self.scale)
        s.configure("Files.Treeview", background=C["surface"], fieldbackground=C["surface"], foreground=C["text"],
                    rowheight=row_h, font=(FONT, 10), borderwidth=0, relief="flat")
        s.layout("Files.Treeview", [("Files.Treeview.treearea", {"sticky": "nswe"})])
        s.layout("Files.Treeview.Item", [("Treeitem.padding", {"sticky": "nswe", "children": [
            ("Treeitem.image", {"side": "left", "sticky": ""}),
            ("Treeitem.text", {"side": "left", "sticky": ""})]})])
        s.configure("Files.Treeview.Item", padding=(round(6 * self.scale), 0))
        s.configure("Files.Treeview.Heading", background=C["surface"], foreground=C["muted"],
                    font=(FONT, 9, "bold"), relief="flat", borderwidth=0, padding=(8, 9),
                    lightcolor=C["surface"], darkcolor=C["surface"], bordercolor=C["surface"])
        s.map("Files.Treeview.Heading", background=[("active", C["hover"])])
        s.map("Files.Treeview", background=[("selected", C["primary_soft"])], foreground=[("selected", C["text"])])
        s.configure("Files.Vertical.TScrollbar", background="#d7dbe1", troughcolor=C["surface"],
                    bordercolor=C["surface"], lightcolor="#d7dbe1", darkcolor="#d7dbe1", arrowcolor=C["muted"],
                    gripcount=0, relief="flat", arrowsize=round(12 * self.scale))
        s.map("Files.Vertical.TScrollbar", background=[("active", "#c3c8d0")])
        s.configure("Thin.Horizontal.TProgressbar", thickness=round(6 * self.scale), background=C["primary"],
                    troughcolor="#e6e9ee", borderwidth=0, lightcolor=C["primary"], darkcolor=C["primary"],
                    bordercolor="#e6e9ee")

    def show_login(self, error=None):
        self.browser.pack_forget()
        self.login.refresh_saved()
        self.login.set_busy(False)
        self.login.show_error(error or "")
        self.login.pack(fill="both", expand=True)
        self.title(APP)

    def show_browser(self):
        self.login.pack_forget()
        self.browser.pack(fill="both", expand=True)
        self.title(f"{self.session['name']} - {APP}")

    def post(self, fn):
        self.ui_queue.put(fn)

    def _drain_queue(self):
        while True:
            try:
                fn = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                if sys.stderr:
                    import traceback
                    traceback.print_exc()
        self.after(40, self._drain_queue)

    def _watchdog(self):
        if self.transport is not None and not self.transport.is_active():
            self._connection_lost()
        self.after(5000, self._watchdog)

    def run_remote(self, func, on_done=None, on_error=None):
        if self.fs is None:
            return

        def worker():
            try:
                with self.remote_lock:
                    res = func()
            except Exception as e:
                err = e
                self.post(lambda: self._remote_error(err, on_error))
            else:
                if on_done:
                    self.post(lambda: on_done(res))

        threading.Thread(target=worker, daemon=True).start()

    def _remote_error(self, err, on_error):
        if self.transport is not None and not self.transport.is_active():
            self._connection_lost()
            return
        self.configure(cursor="")
        if on_error:
            on_error(err)
        else:
            show_message(self, "Something went wrong", friendly_error(err))

    @staticmethod
    def pc_key(host, port):
        return host.lower() if port == 22 else f"{host.lower()}:{port}"

    def folder_display_name(self, path):
        seg = posixpath.basename(path.rstrip("/"))
        if not seg:
            return self.session["name"] if self.session else "this folder"
        return drive_label(seg) if re.fullmatch(r"[A-Za-z]:", seg) else seg

    def download_dir(self):
        d = self.cfg.get("download_dir")
        if d and os.path.isdir(d):
            return d
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def connect(self, host, port, user, pw, remember, start=None, reconnect=False, unc=False, share_path=None):
        """Username and password are optional.
        \\\\nas05 style addresses open as Windows shared folders first (using your own Windows login
        when nothing is typed); plain names / IPs try SSH first. Each falls back to the other."""
        if self.connecting:
            return
        self.connecting = True
        self._last_connect = (host, port, user, pw, remember, start, unc, share_path)
        key = self.pc_key(host, port)
        saved = self.cfg["pcs"].get(key, {})
        prefer = (self.session or {}).get("kind") if reconnect else (saved.get("kind") or ("smb" if unc else "ssh"))
        order = ["smb", "ssh"] if prefer == "smb" else ["ssh", "smb"]
        if port != 22 or not IS_WINDOWS:
            order = ["ssh"]
        if not reconnect:
            self.login.set_busy(True, f"Connecting to {host}…")

        def worker():
            errors = {}
            result = None
            for method in order:
                try:
                    if method == "ssh":
                        result = self._open_ssh(host, port, user, pw)
                    else:
                        result = self._open_smb(host, user, pw, share_path)
                    break
                except Exception as e:
                    errors[method] = e
                    if (user or pw) and not self._is_unreachable(e):
                        break
            if result is None:
                self.post(lambda: token is self._connect_token and
                          self._connect_failed(errors, order, host, bool(user or pw), reconnect))
                return
            session = {"key": key, "host": host, "port": port, "user": user, "pw": pw, "remember": remember,
                       "name": saved.get("name") or host, "kind": result["kind"]}

            def deliver():
                if token is self._connect_token:
                    self._connected(result, session, saved, start, share_path, reconnect)
                else:
                    if result.get("client"):
                        result["client"].close()
                    smb_logout(result.get("smb_handle"))

            self.post(deliver)

        token = object()
        self._connect_token = token
        self.after(int(self.CONNECT_TIMEOUT * 1000),
                   lambda: self._connect_timeout(token, host, bool(user or pw), reconnect))
        threading.Thread(target=worker, daemon=True).start()

    def _connect_timeout(self, token, host, has_creds, reconnect):
        if token is self._connect_token and self.connecting:
            self._connect_token = None
            self._connect_failed({"ssh": TimeoutError("timed out")}, ["ssh"], host, has_creds, reconnect)

    @staticmethod
    def _open_ssh(host, port, user, pw):
        sock = socket.create_connection((host, port), timeout=4)
        user = user or getpass.getuser()
        client = paramiko.SSHClient()
        try:
            with _host_keys_lock:
                os.makedirs(CONFIG_DIR, exist_ok=True)
                if not os.path.exists(KNOWN_HOSTS):
                    open(KNOWN_HOSTS, "a").close()
                client.load_host_keys(KNOWN_HOSTS)
        except (OSError, paramiko.SSHException):
            pass
        client.set_missing_host_key_policy(_RememberHostKey())
        try:
            client.connect(host, port=port, username=user, password=pw or None, timeout=10, sock=sock,
                           banner_timeout=15, auth_timeout=15, allow_agent=not pw, look_for_keys=not pw)
        except Exception:
            client.close()
            sock.close()
            raise
        sftp = client.open_sftp()
        home = sftp.normalize(".")
        drives = []
        if re.match(r"^/[A-Za-z]:", home):
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                try:
                    sftp.stat(f"/{letter}:/")
                    drives.append(f"{letter}:")
                except IOError:
                    pass
        return {"kind": "ssh", "client": client, "home": home, "user_used": user,
                "fs": RemoteFS(sftp, home, drives, client.get_transport())}

    @staticmethod
    def _open_smb(host, user, pw, share_path):
        socket.create_connection((host, 445), timeout=3).close()
        handle = smb_login(host, user, pw) if (user or pw) else None
        try:
            fs = ShareFS(host, [], "/")
            if share_path:
                os.listdir(fs.unc(share_path))
                try:
                    fs.drives = list_shares(host)
                except OSError:
                    fs.home = share_path
            else:
                fs.drives = list_shares(host)
            if not fs.drives:
                fs.home = share_path or fs.home
        except Exception:
            smb_logout(handle)
            raise
        return {"kind": "smb", "client": None, "home": share_path or fs.home, "fs": fs, "smb_handle": handle,
                "user_used": user or getpass.getuser()}

    @staticmethod
    def _is_unreachable(err):
        code = getattr(err, "winerror", None) or (err.args[0] if isinstance(err, OSError) and err.args and
                                                  isinstance(err.args[0], int) else None)
        return (isinstance(err, (socket.gaierror, socket.timeout, TimeoutError, ConnectionRefusedError)) or
                code in (53, 67, 1203, 1222, 10051, 10060, 10061, 10065) or "refused" in str(err).lower())

    @staticmethod
    def _is_auth_error(err):
        code = err.args[0] if isinstance(err, OSError) and err.args and isinstance(err.args[0], int) else None
        no_login = isinstance(err, paramiko.SSHException) and any(
            m in str(err).lower() for m in ("no existing session", "no authentication methods", "authentication"))
        return no_login or isinstance(err, (paramiko.AuthenticationException, PermissionError)) or \
            code in (5, 86, 1326, 1327, 1331, 1907)

    def _host_key_changed(self, bad, host, reconnect):
        """A different machine (or a reinstalled one) answered at a known address. Never send the password
        without asking - this is exactly what an impostor on the network would look like."""
        msg = (f"{host} is not the computer KIRSSH connected to before - its security identity has changed.\n\n"
               f"This is expected only if that computer was reinstalled or replaced, or SSH was set up again. "
               f"Otherwise someone may be pretending to be it, and you should not connect.\n\n"
               f"Expected:  {fingerprint(bad.expected_key)}\nNow:          {fingerprint(bad.key)}")
        if reconnect:
            self._teardown()
            self.show_login(f"Lost the connection to {host}, and it now has a different security identity. "
                            f"Connect again only if you know it was reinstalled or replaced.")
            return
        self.login.set_busy(False)
        self.login.show_error(f"{host} has a different security identity than before. Not connected.")
        if confirm(self, "This computer's identity changed", msg, ok="Trust the new identity", danger=True):
            h, port, user, pw, remember, start, unc, share_path = self._last_connect
            forget_host_key(h, port)
            self.login.show_error("")
            self.connect(h, port, user, pw, remember, start, unc=unc, share_path=share_path)

    def _connect_failed(self, errors, order, host, has_creds, reconnect):
        self.connecting = False
        bad = next((e for e in errors.values() if isinstance(e, paramiko.BadHostKeyException)), None)
        if bad is not None:
            self.after(0, lambda: self._host_key_changed(bad, host, reconnect))
            return
        err = errors[order[0]]
        for m in order[1:]:
            if m in errors and self._is_unreachable(err) and not self._is_unreachable(errors[m]):
                err = errors[m]
        code = err.args[0] if isinstance(err, OSError) and err.args and isinstance(err.args[0], int) else None
        auth = self._is_auth_error(err)
        if auth:
            msg = ("The username or password is incorrect." if has_creds else
                   f"{host} needs a username and password.")
        elif isinstance(err, socket.gaierror) or code in (53, 1203):
            msg = f"Couldn't find a computer called \"{host}\". Check the address and try again."
        elif code == 67:
            msg = f"That shared folder doesn't exist on {host}."
        elif isinstance(err, (socket.timeout, TimeoutError)) or code == 10060:
            msg = f"{host} isn't answering. Make sure it's turned on and on the same network."
        elif isinstance(err, ConnectionRefusedError) or code == 10061 or "refused" in str(err).lower():
            msg = f"{host} refused the connection."
        elif code in (10051, 10065):
            msg = f"Can't reach {host} from this network."
        else:
            msg = f"Couldn't connect to {host}. ({err.__class__.__name__}: {err})"
        if reconnect:
            self._teardown()
            self.show_login(f"Lost the connection to {host}. {msg}")
        else:
            self.login.set_busy(False)
            self.login.show_error(msg)
            if auth:
                self.login.expand_form(focus=False)
                (self.login.pw if has_creds else self.login.user).focus_set()
                if has_creds:
                    self.login.pw.select_range(0, "end")

    def _connected(self, result, session, saved, start, share_path, reconnect):
        self.connecting = False
        self.client = result["client"]
        self.fs = result["fs"]
        self.sftp = self.fs.sftp
        self.transport = self.fs.transport
        if self.transport is not None:
            self.transport.set_keepalive(30)
        self._smb_handle = result.get("smb_handle")
        self.session = session
        kind, home = result["kind"], result["home"]

        pc = self.cfg["pcs"].get(session["key"], {})
        pc.update({"user": session["user"], "shown_user": result["user_used"], "port": session["port"],
                   "kind": kind, "last_used": time.time(), "no_password": not session["pw"],
                   "pw": encrypt_password(session["pw"]) if session["remember"] and session["pw"] else None})
        self.cfg["pcs"][session["key"]] = pc
        self.cfg["last_host"] = session["key"]
        save_config(self.cfg)

        if reconnect:
            self.browser.conn_dot.configure(text="●  Connected", fg=C["success"])
            self.browser.show_notice("Reconnected.", "ok")
            self.browser.refresh()
            if self._watched and self._watch_job is None:
                self._watch_job = self.after(1000, self._check_watched)
            return
        if kind == "smb":
            start = share_path
        if not start and saved.get("kind", kind) == kind:
            start = saved.get("last_dir")
        self.browser.on_connected(session["name"])
        self.show_browser()
        self.browser.go(start or home, on_fail=lambda e: self.browser.go(home))

    def disconnect(self):
        if self.transfer_running and not confirm(self, "Stop the transfer?",
                                                 "A file transfer is still running. Disconnect anyway?",
                                                 ok="Disconnect", danger=True):
            return
        if not self._confirm_unsaved("Disconnect"):
            return
        self.cancel_event.set()
        self._remember_dir()
        self._teardown()
        self.show_login()

    def _teardown(self):
        client = self.client
        self.client = self.sftp = self.transport = self.fs = None
        smb_logout(getattr(self, "_smb_handle", None))
        self._smb_handle = None
        self._watched.clear()
        if self._watch_job is not None:
            self.after_cancel(self._watch_job)
            self._watch_job = None
        self.browser.transfer.hide()
        self.browser.hide_notice()
        try:
            if client:
                client.close()
        except Exception:
            pass

    def _connection_lost(self):
        if self.transport is None or self.connecting:
            return
        s = self.session
        self._remember_dir()
        try:
            self.client.close()
        except Exception:
            pass
        self.client = self.sftp = self.transport = None
        self.browser.conn_dot.configure(text="●  Reconnecting…", fg=C["warn"])
        self.browser.show_notice(f"Lost the connection to {s['name']}. Reconnecting…", "warn", sticky=True)
        self.connect(s["host"], s["port"], s["user"], s["pw"], s["remember"], reconnect=True)

    def _busy_check(self):
        if self.fs is None:
            return False
        if self.transfer_running:
            self.browser.show_notice("Please wait until the current transfer finishes.", "warn")
            return False
        return True

    def upload_files(self):
        if not self._busy_check() or not self.browser.upload_btn.enabled:
            return
        paths = filedialog.askopenfilenames(parent=self, title="Choose files to upload",
                                            initialdir=self.cfg.get("last_upload_dir") or os.path.expanduser("~"))
        if paths:
            self.cfg["last_upload_dir"] = os.path.dirname(paths[0])
            self.upload_paths(list(paths))

    def upload_folder(self):
        if not self._busy_check() or not self.browser.upload_btn.enabled:
            return
        p = filedialog.askdirectory(parent=self, title="Choose a folder to upload",
                                    initialdir=self.cfg.get("last_upload_dir") or os.path.expanduser("~"))
        if p:
            self.cfg["last_upload_dir"] = os.path.dirname(os.path.normpath(p))
            self.upload_paths([p])

    def upload_paths(self, paths):
        if not self._busy_check():
            return
        b = self.browser
        if not b.path:
            return
        if b.path == "/" and self.fs.drives:
            b.show_notice("Open a folder first, then upload into it.", "warn")
            return
        jobs = [{"src": os.path.normpath(p), "is_dir": os.path.isdir(p),
                 "name": os.path.basename(os.path.normpath(p))} for p in paths if os.path.exists(p)]
        if not jobs:
            return
        existing = {e["name"].lower() for e in b.items}
        jobs = self._resolve_conflicts(jobs, lambda n: n.lower() in existing,
                                       self.folder_display_name(b.path))
        if jobs:
            self._start_transfer("up", jobs, b.path)

    def download_selected(self):
        if not self._busy_check():
            return
        b = self.browser
        sel = [e for e in b.selected() if not e.get("drive")]
        if not sel:
            return
        dest = self.download_dir()
        os.makedirs(dest, exist_ok=True)
        jobs = [{"src": RemoteFS.join(b.path, e["name"]), "is_dir": e["is_dir"], "name": e["name"]} for e in sel]
        jobs = self._resolve_conflicts(jobs, lambda n: os.path.exists(os.path.join(dest, n)),
                                       os.path.basename(dest) or dest)
        if jobs:
            self._start_transfer("down", jobs, dest)

    def _resolve_conflicts(self, jobs, exists, where):
        clash = [j for j in jobs if exists(j["name"])]
        if not clash:
            return jobs
        if len(clash) == 1:
            msg = f'"{clash[0]["name"]}" already exists in {where}.'
        else:
            msg = f"{len(clash)} of these items already exist in {where}."
        ask = ("Replace it, or keep both by giving the new copy a different name?" if len(clash) == 1 else
               "Replace them, or keep both by giving the new copies different names?")
        choice = choose(self, "Replace or keep both?", f"{msg}\n\n{ask}",
                        [("Replace", "replace", "primary"), ("Keep both", "keep", "secondary"),
                         ("Cancel", None, "ghost")])
        if choice is None:
            return None
        if choice == "keep":
            taken = set()
            for j in clash:
                j["name"] = unique_name(j["name"], lambda n: exists(n) or n.lower() in taken)
                taken.add(j["name"].lower())
        return jobs

    def _start_transfer(self, kind, jobs, dest_dir):
        self.transfer_running = True
        self.cancel_event.clear()
        b = self.browser
        b._update_actions()
        n_items = len(jobs)
        upload = kind == "up"
        where = self.folder_display_name(dest_dir) if upload else (os.path.basename(dest_dir) or dest_dir)
        title_running = (f"Uploading {plural(n_items, 'item')} to {where}" if upload
                         else f"Downloading {plural(n_items, 'item')}")
        b.transfer.start(title_running, upload)
        fs, cancel = self.fs, self.cancel_event

        def worker():
            sftp = None
            files_done = 0
            current_dst = None
            try:
                sftp = fs.open_transfer()
                dirs, plan = [], []
                if upload:
                    for j in jobs:
                        dst = posixpath.join(dest_dir, j["name"])
                        if j["is_dir"]:
                            for root, _dn, fnames in os.walk(j["src"]):
                                rel = os.path.relpath(root, j["src"])
                                rdst = dst if rel == "." else posixpath.join(dst, *rel.split(os.sep))
                                dirs.append(rdst)
                                for f in fnames:
                                    lp = os.path.join(root, f)
                                    st = os.stat(lp)
                                    plan.append((lp, posixpath.join(rdst, f), st.st_size, st.st_atime, st.st_mtime))
                        else:
                            st = os.stat(j["src"])
                            plan.append((j["src"], dst, st.st_size, st.st_atime, st.st_mtime))
                else:
                    def walk(rsrc, ldst):
                        dirs.append(ldst)
                        for fname, is_dir, size, atime, mtime in sftp.listdir(rsrc):
                            if cancel.is_set():
                                raise Cancelled()
                            rp, lp = posixpath.join(rsrc, fname), os.path.join(ldst, fname)
                            if is_dir:
                                walk(rp, lp)
                            else:
                                plan.append((rp, lp, size, atime, mtime))

                    for j in jobs:
                        dst = os.path.join(dest_dir, j["name"])
                        if j["is_dir"]:
                            walk(j["src"], dst)
                        else:
                            size, atime, mtime = sftp.stat(j["src"])
                            plan.append((j["src"], dst, size, atime, mtime))

                for d in dirs:
                    if upload:
                        if not sftp.exists(d):
                            sftp.mkdir(d)
                    else:
                        os.makedirs(d, exist_ok=True)

                total = sum(p[2] for p in plan) or 1
                n = len(plan)
                done_bytes = 0
                start = time.time()
                last = [0.0]

                for i, (src, dst, size, atime, mtime) in enumerate(plan, 1):
                    if cancel.is_set():
                        raise Cancelled()
                    name = os.path.basename(src) if upload else posixpath.basename(src)
                    base = done_bytes

                    def cb(x, _t, base=base, name=name, i=i):
                        if cancel.is_set():
                            raise Cancelled()
                        now = time.time()
                        if now - last[0] < 0.15:
                            return
                        last[0] = now
                        sofar = base + x
                        elapsed = max(now - start, 0.001)
                        speed = sofar / elapsed
                        left = (total - sofar) / speed if speed > 0 else 0
                        files = f"file {i} of {n}  ·  " if n > 1 else ""
                        detail = (f"{name}  ·  {files}{human_size(sofar)} of {human_size(total)}  ·  "
                                  f"about {fmt_duration(left)} left")
                        pct = sofar * 100 / total
                        self.post(lambda: b.transfer.update_progress(pct, title_running, detail))

                    part = dst + PART_SUFFIX
                    current_dst = part
                    if upload:
                        sftp.put(src, part, cb)
                        sftp.replace(part, dst)
                        current_dst = None
                        try:
                            sftp.utime(dst, (atime, mtime))
                        except (IOError, OSError):
                            pass
                    else:
                        sftp.get(src, part, cb)
                        os.replace(part, dst)
                        current_dst = None
                        try:
                            if mtime:
                                os.utime(dst, (atime or mtime, mtime))
                        except OSError:
                            pass
                    done_bytes += size
                    files_done += 1

                elapsed = time.time() - start
                if upload:
                    title = f"Uploaded {plural(n_items, 'item')} to {where}"
                    reveal = None
                else:
                    title = f"Downloaded {plural(n_items, 'item')} to {where}"
                    reveal = os.path.join(dest_dir, jobs[0]["name"]) if n_items == 1 else dest_dir
                detail = f"{human_size(done_bytes)}  ·  took {fmt_duration(elapsed)}"
                self.post(lambda: self._transfer_finished(kind, dest_dir, "ok", title, detail, reveal))
            except Exception as e:
                if current_dst:
                    try:
                        if upload:
                            sftp.remove(current_dst)
                        else:
                            os.remove(current_dst)
                    except Exception:
                        pass
                verb = "Upload" if upload else "Download"
                if isinstance(e, Cancelled):
                    title = f"{verb} cancelled"
                    detail = f"{plural(files_done, 'file')} finished before you cancelled."
                    self.post(lambda: self._transfer_finished(kind, dest_dir, "cancel", title, detail))
                else:
                    err = e
                    title = f"{verb} didn't finish"
                    self.post(lambda: self._transfer_finished(kind, dest_dir, "error", title,
                                                              friendly_error(err), error=err))
            finally:
                if sftp is not None:
                    try:
                        sftp.close()
                    except Exception:
                        pass

        threading.Thread(target=worker, daemon=True).start()

    def _transfer_finished(self, kind, dest_dir, status, title, detail, reveal=None, error=None):
        self.transfer_running = False
        b = self.browser
        b.transfer.finish(status, title, detail, reveal)
        b._update_actions()
        if error is not None and self.transport is not None and not self.transport.is_active():
            self._connection_lost()
            return
        if kind == "up" and self.fs is not None and b.path == dest_dir:
            b.refresh()

    def open_remote_file(self, remote_path, name):
        pc = self.session["name"]
        if self.fs.kind == "smb":
            try:
                os.startfile(self.fs.unc(remote_path))
                self.browser.show_notice(f"Opened {name}. When you save it, it's saved on {pc}.", "info")
            except OSError as e:
                show_message(self, "Couldn't open the file", friendly_error(e))
            return

        tmp_dir = tempfile.mkdtemp(prefix="kirssh_")
        local = os.path.join(tmp_dir, name)
        self.configure(cursor="watch")
        self.browser.show_notice(f"Opening {name}…", "info", sticky=True)

        fs = self.fs

        def fetch():
            fs.download_file(remote_path, local)
            return local, fs.signature(remote_path)

        def done(result):
            path, remote_sig = result
            self.configure(cursor="")
            self.browser.show_notice(f"Opened {name}. When you save it, KIRSSH saves it back to {pc}.", "info")
            self._watch_file(path, remote_path, name, remote_sig)
            try:
                os.startfile(path)
            except OSError as e:
                show_message(self, "Couldn't open the file", friendly_error(e))

        def fail(err):
            self.browser.hide_notice()
            show_message(self, "Couldn't open the file", friendly_error(err))

        self.run_remote(fetch, done, fail)

    @staticmethod
    def _file_sig(path):
        st = os.stat(path)
        return st.st_mtime_ns, st.st_size

    def _watch_file(self, local, remote, name, remote_sig):
        try:
            sig = self._file_sig(local)
        except OSError:
            return
        self._watched[local] = {"remote": remote, "name": name, "synced": sig, "seen": None,
                                "busy": False, "retry_at": 0.0, "remote_sig": remote_sig, "paused": None}
        if self._watch_job is None:
            self._watch_job = self.after(1000, self._check_watched)

    def _check_watched(self):
        self._watch_job = None
        if self.fs is None:
            return
        now = time.time()
        for local, w in list(self._watched.items()):
            if w["busy"] or now < w["retry_at"]:
                continue
            try:
                sig = self._file_sig(local)
            except OSError:
                continue
            if sig == w["synced"] or sig == w["paused"]:
                w["seen"] = None
                continue
            if w["seen"] != sig:
                w["seen"] = sig
                continue
            self._save_back(local, w, sig)
        if self._watched:
            self._watch_job = self.after(1000, self._check_watched)

    def _save_back(self, local, w, sig, mode="normal"):
        """mode: "normal" (stop if someone else changed the file), "replace" (overwrite theirs),
        or "copy" (save next to theirs under a new name)."""
        fs, name, pc = self.fs, w["name"], self.session["name"]
        w["busy"] = True
        self.browser.show_notice(f"Saving {name} to {pc}…", "info", sticky=True)

        def worker():
            snap = local + ".kirssh-upload"
            x = part = None
            try:
                shutil.copyfile(local, snap)
                x = fs.open_transfer()
                target = w["remote"]
                if mode == "normal":
                    try:
                        size, _at, mtime = x.stat(target)
                        current = (size, mtime)
                    except IOError:
                        current = None
                    if current is not None and current != w["remote_sig"]:
                        self.post(lambda: self.after(0, lambda: conflict()))
                        return
                elif mode == "copy":
                    folder = RemoteFS.parent(target)
                    base, ext = os.path.splitext(posixpath.basename(target))
                    copy_name = f"{base} (my copy){ext}"
                    taken = lambda n: x.exists(posixpath.join(folder, n))
                    target = posixpath.join(folder, copy_name if not taken(copy_name)
                                            else unique_name(copy_name, taken))
                part = target + PART_SUFFIX
                x.put(snap, part, lambda _a, _b: None)
                x.replace(part, target)
                part = None
                size, _at, mtime = x.stat(target)
            except Exception as e:
                err = e
                if part and x is not None:
                    try:
                        x.remove(part)
                    except Exception:
                        pass
                self.post(lambda: failed(err))
            else:
                self.post(lambda: done(target, (size, mtime)))
            finally:
                if x is not None:
                    try:
                        x.close()
                    except Exception:
                        pass
                try:
                    os.remove(snap)
                except OSError:
                    pass

        def conflict():
            if local not in self._watched:
                return
            choice = choose(self, "Someone else changed this file",
                            f"{name} was changed on {pc} after you opened it.\n\n"
                            f"Replace their version with yours, or save yours as a separate copy?",
                            [("Save mine as a copy", "copy", "primary"), ("Replace theirs", "replace", "secondary"),
                             ("Not now", None, "ghost")])
            w["busy"] = False
            if choice is None or self.fs is None:
                w["paused"], w["seen"] = sig, None
                self.browser.show_notice(f"{name} wasn't saved to {pc}. Save it again to retry.", "warn",
                                         sticky=True)
            else:
                self._save_back(local, w, sig, choice)

        def done(target, remote_sig):
            w["busy"], w["synced"], w["seen"], w["paused"] = False, sig, None, None
            w["remote"], w["remote_sig"] = target, remote_sig
            w["name"] = posixpath.basename(target)
            self.browser.show_notice(f"Saved {w['name']} to {pc}.", "ok")
            if self.fs is not None and self.browser.path == RemoteFS.parent(target):
                self.browser.refresh()

        def failed(err):
            w["busy"], w["seen"], w["retry_at"] = False, None, time.time() + 10
            if self.transport is not None and not self.transport.is_active():
                self._connection_lost()
            self.browser.show_notice(f"Couldn't save {name} to {pc} yet ({friendly_error(err)}) - "
                                     f"KIRSSH will try again.", "warn", sticky=True)

        threading.Thread(target=worker, daemon=True).start()

    def _unsaved_files(self):
        out = []
        for local, w in self._watched.items():
            try:
                if w["busy"] or self._file_sig(local) != w["synced"]:
                    out.append(w["name"])
            except OSError:
                pass
        return out

    def _confirm_unsaved(self, action):
        names = self._unsaved_files()
        if not names:
            return True
        listed = ", ".join(names[:3]) + ("…" if len(names) > 3 else "")
        return confirm(self, "Changes not saved yet",
                       f"{listed} {'has' if len(names) == 1 else 'have'} changes that haven't been saved to "
                       f"{self.session['name']} yet. {action} anyway?", ok=action, danger=True)

    def open_settings(self):
        open_settings_dialog(self)

    def _remember_dir(self):
        if self.session and self.browser.path and self.session["key"] in self.cfg["pcs"]:
            self.cfg["pcs"][self.session["key"]]["last_dir"] = self.browser.path
            save_config(self.cfg)

    def on_close(self):
        if self.transfer_running and not confirm(self, "Quit KIRSSH?", "A file transfer is still running. "
                                                                        "Quit anyway?", ok="Quit", danger=True):
            return
        if self.fs is not None and not self._confirm_unsaved("Quit"):
            return
        self.cancel_event.set()
        self._remember_dir()
        self._teardown()
        self.destroy()


def main():
    if IS_WINDOWS:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
