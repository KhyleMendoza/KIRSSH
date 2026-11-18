"""Tests for KIRSSH safe transfers, save-back conflicts and host keys, against a local stub SFTP server.

Run from the kirssh folder:   py -3.15 tests/test_fixes.py .
(needs paramiko; uses a temp folder, never your real settings)
"""
import os, sys, socket, threading, time, tempfile, shutil
import paramiko
from paramiko import SFTPServerInterface, SFTPServer, SFTPAttributes, SFTPHandle, SFTP_OK, ServerInterface
from paramiko.sftp import SFTP_OP_UNSUPPORTED

sys.path.insert(0, sys.argv[1])
import kirssh

WORK = tempfile.mkdtemp(prefix="kt_")
ROOT = os.path.join(WORK, "remote"); os.makedirs(ROOT)
LOCAL = os.path.join(WORK, "local"); os.makedirs(LOCAL)
kirssh.CONFIG_DIR = os.path.join(WORK, "cfg")
kirssh.CONFIG_FILE = os.path.join(kirssh.CONFIG_DIR, "kirssh_config.json")
kirssh.KNOWN_HOSTS = os.path.join(kirssh.CONFIG_DIR, "known_hosts")

HOST_KEY = [paramiko.RSAKey.generate(2048)]


class Srv(ServerInterface):
    def check_auth_password(self, u, p): return paramiko.AUTH_SUCCESSFUL if p == "pw" else paramiko.AUTH_FAILED
    def get_allowed_auths(self, u): return "password"
    def check_channel_request(self, kind, cid): return paramiko.OPEN_SUCCEEDED


class H(SFTPHandle):
    def stat(self): return SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))


class FS(SFTPServerInterface):
    def _p(self, p): return os.path.join(ROOT, *[s for s in p.split("/") if s and s != "."])
    def canonicalize(self, p): return "/" + "/".join(s for s in p.split("/") if s and s != ".")
    def list_folder(self, p):
        out = []
        for n in os.listdir(self._p(p)):
            a = SFTPAttributes.from_stat(os.stat(os.path.join(self._p(p), n))); a.filename = n; out.append(a)
        return out
    def stat(self, p):
        try: return SFTPAttributes.from_stat(os.stat(self._p(p)))
        except OSError as e: return SFTPServer.convert_errno(e.errno)
    lstat = stat
    def open(self, p, flags, attr):
        fp = self._p(p)
        mode = "r+b" if flags & os.O_RDWR else ("wb" if flags & os.O_WRONLY else "rb")
        if flags & os.O_WRONLY and not (flags & os.O_TRUNC) and os.path.exists(fp): mode = "r+b"
        try: f = open(fp, mode)
        except OSError as e: return SFTPServer.convert_errno(e.errno)
        h = H(flags); h.readfile = h.writefile = f; return h
    def remove(self, p): os.remove(self._p(p)); return SFTP_OK
    def rename(self, a, b):                 # Windows-like: fails if the target exists
        try: os.rename(self._p(a), self._p(b)); return SFTP_OK
        except OSError as e: return SFTPServer.convert_errno(e.errno)
    def posix_rename(self, a, b): return SFTP_OP_UNSUPPORTED
    def mkdir(self, p, attr): os.mkdir(self._p(p)); return SFTP_OK
    def rmdir(self, p): os.rmdir(self._p(p)); return SFTP_OK
    def chattr(self, p, attr):
        if attr.st_mtime is not None: os.utime(self._p(p), (attr.st_atime, attr.st_mtime))
        return SFTP_OK


lsock = socket.socket(); lsock.bind(("127.0.0.1", 0)); lsock.listen(20)
PORT = lsock.getsockname()[1]


def serve():
    while True:
        c, _ = lsock.accept()
        t = paramiko.Transport(c); t.add_server_key(HOST_KEY[0])
        t.set_subsystem_handler("sftp", SFTPServer, FS)
        try:
            t.start_server(server=Srv())
        except Exception:   # client hung up during the handshake (e.g. it refused our key)
            pass


threading.Thread(target=serve, daemon=True).start()
results = []


def check(name, cond):
    results.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name)


# 1. host keys: first connect remembered, changed key refused, forgetting allows again
r = kirssh.App._open_ssh("127.0.0.1", PORT, "u", "pw")
check("first connect succeeds and saves known_hosts",
      os.path.exists(kirssh.KNOWN_HOSTS) and f"[127.0.0.1]:{PORT}" in open(kirssh.KNOWN_HOSTS).read())
r["client"].close()
r = kirssh.App._open_ssh("127.0.0.1", PORT, "u", "pw"); r["client"].close()
check("second connect with same key succeeds", True)
HOST_KEY[0] = paramiko.RSAKey.generate(2048)
try:
    kirssh.App._open_ssh("127.0.0.1", PORT, "u", "pw"); check("changed key is refused", False)
except paramiko.BadHostKeyException as e:
    check("changed key is refused", True); bad = e
    check("fingerprint formats", kirssh.fingerprint(bad.key).startswith("SHA256:"))
    kirssh.forget_host_key("127.0.0.1", PORT)
r = kirssh.App._open_ssh("127.0.0.1", PORT, "u", "pw")
check("connect works after trusting new key", True)
fs = r["fs"]

# 2. SftpTransfer.replace over an existing file (posix_rename unsupported -> fallback)
open(os.path.join(ROOT, "a.txt"), "w").write("OLD")
open(os.path.join(ROOT, "a.txt.kirssh-part"), "w").write("NEW")
x = fs.open_transfer(); x.replace("/a.txt.kirssh-part", "/a.txt")
check("replace swaps content", open(os.path.join(ROOT, "a.txt")).read() == "NEW")
check("replace leaves no temp files", sorted(os.listdir(ROOT)) == ["a.txt"])
x.close()

# 3. GUI transfer: Replace then cancel keeps the original; normal replace works
app = kirssh.App()
app.fs, app.client, app.transport = fs, r["client"], fs.transport
app.session = {"name": "test", "key": "k", "host": "127.0.0.1", "port": PORT}
app.browser.path = "/"
app.fs.drives = []


def rd(name):
    try:
        return open(os.path.join(ROOT, name)).read()
    except OSError:
        return None


def pump(cond, timeout=20):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.update(); time.sleep(0.02)


big = os.path.join(LOCAL, "big.bin")
with open(big, "wb") as f: f.write(os.urandom(8 * 1024 * 1024))
open(os.path.join(ROOT, "big.bin"), "wb").write(b"ORIGINAL")
real_put = kirssh.SftpTransfer.put
def slow_put(self, src, dst, cb):
    def cb2(a, b):
        if a > 1024 * 1024: app.cancel_event.set()
        cb(a, b)
    real_put(self, src, dst, cb2)
kirssh.SftpTransfer.put = slow_put
app._start_transfer("up", [{"src": big, "is_dir": False, "name": "big.bin"}], "/")
pump(lambda: not app.transfer_running)
check("cancelled replace keeps original remote file", open(os.path.join(ROOT, "big.bin"), "rb").read() == b"ORIGINAL")
check("cancelled upload leaves no part file", not os.path.exists(os.path.join(ROOT, "big.bin.kirssh-part")))
kirssh.SftpTransfer.put = real_put

app._start_transfer("up", [{"src": big, "is_dir": False, "name": "big.bin"}], "/")
pump(lambda: not app.transfer_running)
check("upload replaces remote file", os.path.getsize(os.path.join(ROOT, "big.bin")) == 8 * 1024 * 1024)

open(os.path.join(LOCAL, "big.bin"), "wb").write(b"LOCALORIG")
real_get = kirssh.SftpTransfer.get
def slow_get(self, src, dst, cb):
    def cb2(a, b):
        if a > 1024 * 1024: app.cancel_event.set()
        cb(a, b)
    real_get(self, src, dst, cb2)
kirssh.SftpTransfer.get = slow_get
app._start_transfer("down", [{"src": "/big.bin", "is_dir": False, "name": "big.bin"}], LOCAL)
pump(lambda: not app.transfer_running)
check("cancelled download keeps original local file", open(os.path.join(LOCAL, "big.bin"), "rb").read() == b"LOCALORIG")
kirssh.SftpTransfer.get = real_get
app._start_transfer("down", [{"src": "/big.bin", "is_dir": False, "name": "big.bin"}], LOCAL)
pump(lambda: not app.transfer_running)
check("download replaces local file", os.path.getsize(os.path.join(LOCAL, "big.bin")) == 8 * 1024 * 1024)
check("download leaves no part file", not os.path.exists(os.path.join(LOCAL, "big.bin.kirssh-part")))

# 4. save-back: normal save, then conflict -> copy / replace
open(os.path.join(ROOT, "doc.txt"), "w").write("v1")
edit = os.path.join(LOCAL, "doc.txt"); shutil.copy(os.path.join(ROOT, "doc.txt"), edit)
app._watch_file(edit, "/doc.txt", "doc.txt", fs.signature("/doc.txt"))
w = app._watched[edit]
time.sleep(1.1); open(edit, "w").write("v2 mine")
pump(lambda: rd("doc.txt") == "v2 mine" and not w["busy"], 15)
check("save-back writes changes", open(os.path.join(ROOT, "doc.txt")).read() == "v2 mine")

answers = []
kirssh.choose = lambda *a, **k: answers.pop(0)
time.sleep(1.1); open(os.path.join(ROOT, "doc.txt"), "w").write("v3 theirs!")    # someone else edits
answers.append("copy")
time.sleep(1.1); open(edit, "w").write("v3 mine")
pump(lambda: os.path.exists(os.path.join(ROOT, "doc (my copy).txt")) and not w["busy"], 15)
check("conflict: theirs untouched", open(os.path.join(ROOT, "doc.txt")).read() == "v3 theirs!")
check("conflict: mine saved as copy", open(os.path.join(ROOT, "doc (my copy).txt")).read() == "v3 mine")
check("later saves go to the copy", w["remote"] == "/doc (my copy).txt")

time.sleep(1.1); open(os.path.join(ROOT, "doc (my copy).txt"), "w").write("changed remotely")
answers.append("replace")
time.sleep(1.1); open(edit, "w").write("v4 mine wins")
pump(lambda: rd("doc (my copy).txt") == "v4 mine wins" and not w["busy"], 15)
check("conflict: replace overwrites theirs", open(os.path.join(ROOT, "doc (my copy).txt")).read() == "v4 mine wins")

time.sleep(1.1); open(os.path.join(ROOT, "doc (my copy).txt"), "w").write("remote again")
answers.append(None)
time.sleep(1.1); open(edit, "w").write("v5 not now")
pump(lambda: w["paused"] is not None, 15)
pump(lambda: False, 3)
check("conflict: not now leaves remote alone", open(os.path.join(ROOT, "doc (my copy).txt")).read() == "remote again")
check("conflict: not now doesn't re-ask", not answers and app._unsaved_files() == ["doc (my copy).txt"])
check("no leftover part files", not [n for n in os.listdir(ROOT) if n.endswith((".kirssh-part", ".kirssh-old"))])

app._watched.clear(); app.destroy()
print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
shutil.rmtree(WORK, ignore_errors=True)
sys.exit(0 if all(ok for _, ok in results) else 1)
