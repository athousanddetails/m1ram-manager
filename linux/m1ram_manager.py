import sys, os, glob, base64, threading

VID, PID = 0x16C0, 0x1770
CARD_SIZE = 32768
REPORT = 0x14
SUB_SETADDR, SUB_WRITE = 0x01, 0x02
REPORT_ACK, REPORT_STATUS = 0x15, 0x16
WRITE_CHUNK, READ_CHUNK = 60, 64
FEATURE_LEN = 64  # the card's HID feature-report length (Windows requires full-length reports)
RAM_MARKER = 0x11
HEADER_MARKER = 0x10
GLOBAL_OFF, GLOBAL_LEN = 16, 1225
COMBI_OFF, COMBI_LEN = 1241, 12400
PROG_OFF, PROG_LEN = 13641, 14300
N = 100
PROG_REC, COMBI_REC = 143, 124
TIMBRE_PTRS = [36, 47, 58, 69, 80, 91, 102, 113]
TIMBRE_BIAS = 100
F_PROG, F_COMBI = 0x4C, 0x4D
GLOBAL_TEMPLATE = "AAABAAEAAAABBwAAAAAAAM4AAAAAAADOAQAAGAUAGAAAAAABABoFABoAAAAAAgAcBQAcAAAAAAMAHQUAHQAAAAAEAB8FAB8AAAAABQAhBQAhAAAAAAYAIwUAIwAAAAAHACQHACQAAAAACAAmAxQnAAAAAAkAKAcUKgAAAAAKACkEACkAAAAACwArBAArAAAAAAwALQQALQAAAAANAC8EAC8AAAAADgAwBwAwAADdAA8AMgJGMgAAAAAQADQIADQAAAAAEQA1ASg1AAAAABIANwkANwAAAAATADkGADkAAAAAFAA7BgA7AAAAABUAPAYAPAAAAAAdAD4FAD4AAAAAFwBABQBAAAAAABgAQQEAQQAAAAAZAEMJAEMAAAAAGgBFBABFAAAAABsARwEARwAAAAAcAEgJAEgAAAAAFgBUBbBXAAAAAAAAGAUAGQAAEQAFABoF7BoAAAAAGgAcCBQe3wAAAAoAHQIAHfEAAAALAB8CAB8AAOoACgAeAgAeAADzAAIAGQXYGQAAAQAGABsF9hvdAAAACAAmAuwlAAAAAAkALAUoLmMAAAAJADAIHi4AAAAACgAyBwAyAADtAAsAIAIAIAAAnQAPADQD9jkAAAAADwA1BwA1AAAAABAANwfsLwAAAAAQADYFADYAAAAAEQA4AABEAAAAABEAOQIAOQAAAAASADoKAEYAAAAAEgA7CB48AABjABMAPAYAPAAAAAAUAD8E2EHrAGMAFQBACABA5wCdABUAQQcAQWMAAAAXAEID2EIAAAAAFgBKBRRMAAAAABwASwT2QgAAAAAkAEwHAE4AAOQAHABzBSh7AADDAAAAGAUAGewADAAHABkFKBsAABQABgAaBQAaRgAAABQAGwgyGu0AAAAIAB0KAB4jAAAACgAeCPYdxwAAABoAIAUeJDIAAAAJACEFACEAAAAACwAiCeIh1gAAAAkAJAD2IgAAAAAOACUAAB4yAM4ADgAmCOwkAADmABcAKAn2J80AIAAWACkKADXOAAAADwAqAAAqAAAAABYALQXsMOIAAAAQAC4AAC4AAAAAFgAwAOIqzgAyACEAOwXYOwAAYwAgAEIF7EUAAAAAEwA9BQBCAAAAAB0ARwXsSgAAAAAeAE4F7FAAAAAAAgBIBQBIYwAIAAMASgUATGMAAAAEAEwFAExjAAAAGABUBQBUAAAAAP//DAUADAAAAAD//w0FAA0AAAAA//8OBQAOAAAAAP//MAUAMAAAAAD//zIFADIAAAAA//80BQA0AAAAAP//NQUANQAAAAD//zcFADcAAAAA//85BQA5AAAAAP//OwUAOwAAAAD//zwFADwAAAAA//8+BQA+AAAAAP//QAUAQAAAAAD//0EFAEEAAAAA//9DBQBDAAAAAP//RQUARQAAAAD//0cFAEcAAAAA//9IBQBIAAAAAP//SgUASgAAAAD//0wFAEwAAAAA//9NBQBNAAAAAP//TwUATwAAAAD//1EFAFEAAAAA//9TBQBTAAAAAP//VAUAVAAAAAD//1YFAFYAAAAA//9YBQBYAAAAAP//WQUAWQAAAAD//1sFAFsAAAAA//9dBQBdAAAAAP//XwUAXwAAAAD//2AFAGAAAAAA//9iBQBiAAAAAA=="

INIT_COMBI = None


def korg_unpack(data):
    out = bytearray()
    i = 0
    while i < len(data):
        msb = data[i]
        i += 1
        for k in range(7):
            if i >= len(data):
                break
            b = data[i]
            i += 1
            if msb & (1 << k):
                b |= 0x80
            out.append(b)
    return bytes(out)


def korg_pack(data):
    out = bytearray()
    i = 0
    while i < len(data):
        group = data[i:i + 7]
        i += 7
        msb = 0
        for k, b in enumerate(group):
            if b & 0x80:
                msb |= (1 << k)
        out.append(msb)
        out.extend(b & 0x7F for b in group)
    return bytes(out)


def parse_syx(raw):
    blocks = {}
    i = 0
    while i < len(raw):
        if raw[i] != 0xF0:
            i += 1
            continue
        j = raw.find(0xF7, i)
        if j < 0:
            break
        seg = raw[i:j + 1]
        if len(seg) >= 6 and seg[1] == 0x42 and seg[3] == 0x19 and seg[4] not in blocks:
            blocks[seg[4]] = korg_unpack(seg[6:-1])
        i = j + 1
    return blocks


def rec_name(rec):
    return "".join(chr(c) if 32 <= c < 127 else " " for c in rec[:10]).strip()


def assemble(prog, combi):
    card = bytearray(CARD_SIZE)
    card[0:5] = bytes([0x4B, 0x4F, 0x52, 0x47, HEADER_MARKER])
    t = base64.b64decode(GLOBAL_TEMPLATE)
    card[GLOBAL_OFF:GLOBAL_OFF + GLOBAL_LEN] = t[:GLOBAL_LEN]
    card[PROG_OFF:PROG_OFF + PROG_LEN] = prog
    cb = bytearray(combi)
    for n in range(N):
        base = n * COMBI_REC
        for off in TIMBRE_PTRS:
            cb[base + off] = (cb[base + off] + TIMBRE_BIAS) & 0xFF
    card[COMBI_OFF:COMBI_OFF + COMBI_LEN] = cb
    return bytes(card)


def build_card(paths):
    if isinstance(paths, str):
        paths = [paths]
    b = {}
    for p in paths:
        for f, payload in parse_syx(open(p, "rb").read()).items():
            b.setdefault(f, payload)
    prog, combi = b.get(F_PROG), b.get(F_COMBI)
    if prog is None or combi is None:
        raise ValueError("Need all-programs (0x4C) and all-combinations (0x4D) dumps; found " +
                         ", ".join("0x%02X" % f for f in b))
    if len(prog) != PROG_LEN or len(combi) != COMBI_LEN:
        raise ValueError("unexpected block sizes")
    return assemble(prog, combi)


def card_preset_names(img):
    p = [rec_name(img[PROG_OFF + i * PROG_REC:PROG_OFF + i * PROG_REC + 10]) for i in range(N)]
    c = [rec_name(img[COMBI_OFF + i * COMBI_REC:COMBI_OFF + i * COMBI_REC + 10]) for i in range(N)]
    return p, c


def init_combi_block():
    global INIT_COMBI
    if INIT_COMBI is None:
        rec = bytearray(124)
        rec[0:10] = b"INIT      "
        for off in TIMBRE_PTRS:
            rec[off + 10] = 0x10
        INIT_COMBI = bytes(rec) * 100
    return INIT_COMBI


class Bank:
    def __init__(self, path):
        self.path = path
        self.title = os.path.splitext(os.path.basename(path))[0]
        b = parse_syx(open(path, "rb").read())
        prog, combi = b.get(F_PROG), b.get(F_COMBI)
        if not prog or not combi or len(prog) != PROG_LEN or len(combi) != COMBI_LEN:
            raise ValueError("not a full bank")
        self.progs = [prog[i * PROG_REC:(i + 1) * PROG_REC] for i in range(N)]
        self.combis = [combi[i * COMBI_REC:(i + 1) * COMBI_REC] for i in range(N)]

    def prog_name(self, i):
        return rec_name(self.progs[i])

    def combi_name(self, i):
        return rec_name(self.combis[i])

    def combi_timbres(self, i):
        rec = self.combis[i]
        return [(t, rec[off]) for t, off in enumerate(TIMBRE_PTRS) if (rec[off + 10] & 0x10) == 0]


class Builder:
    def __init__(self):
        self.progs = []
        self.combis = []
        self._src = {}
        self.warnings = []

    def _add_prog(self, bank, idx):
        key = (bank.path, idx)
        if key in self._src:
            return self._src[key]
        if len(self.progs) >= N:
            self.warnings.append("program slots full")
            return None
        slot = len(self.progs)
        self.progs.append(bytearray(bank.progs[idx]))
        self._src[key] = slot
        return slot

    def add_program(self, bank, idx):
        self._add_prog(bank, idx)

    def add_combi(self, bank, idx):
        if len(self.combis) >= N:
            self.warnings.append("combi slots full")
            return
        rec = bytearray(bank.combis[idx])
        for t, srcprog in bank.combi_timbres(idx):
            slot = self._add_prog(bank, srcprog)
            if slot is not None:
                rec[TIMBRE_PTRS[t]] = slot
        self.combis.append(rec)

    def reset(self):
        self.__init__()

    def image(self):
        init_p = self.progs[0] if self.progs else bytearray(PROG_REC)
        pb = b"".join(bytes(self.progs[i]) if i < len(self.progs) else bytes(init_p) for i in range(N))
        ic = init_combi_block()
        cb = b"".join(bytes(self.combis[i]) if i < len(self.combis) else ic[i * 124:(i + 1) * 124] for i in range(N))
        return assemble(pb, cb)


class CardUSB:
    def __init__(self):
        self.backend = None
        self.note = ""
        try:
            import usb.core
            try:
                import libusb_package
                dev = usb.core.find(idVendor=VID, idProduct=PID, backend=libusb_package.get_libusb1_backend())
            except Exception:
                dev = usb.core.find(idVendor=VID, idProduct=PID)
            if dev is not None:
                try:
                    if dev.is_kernel_driver_active(0):
                        dev.detach_kernel_driver(0)
                except Exception:
                    pass
                try:
                    dev.set_configuration()
                except Exception:
                    pass
                dev.ctrl_transfer(0xA1, 0x01, (0x03 << 8) | REPORT_STATUS, 0, 8)
                self.dev = dev
                self.iface = 0
                self.backend = "libusb"
        except Exception:
            pass
        if self.backend is None:
            try:
                import hid
                h = hid.device()
                h.open(VID, PID)
                h.set_nonblocking(0)
                self.h = h
                self.backend = "hid"
                self.note = ("Using the built-in HID driver (no Zadig needed). Reads are reliable; "
                             "if a write does not verify, install the WinUSB driver for "
                             "16C0:1770 with Zadig for a reliable write path.")
            except Exception:
                pass
        if self.backend is None:
            raise RuntimeError("No m1RAM card found on USB (%04x:%04x)." % (VID, PID))

    def _set(self, payload, delay=0.0):
        import time
        buf = bytes(payload)
        if self.backend == "libusb":
            self.dev.ctrl_transfer(0x21, 0x09, (0x01 << 8) | REPORT, self.iface, buf)
        else:
            # Windows HidD_SetFeature rejects a feature report shorter than the
            # device's declared report length (fails with ERROR_INVALID_PARAMETER),
            # so the set-address command never reaches the card and every read
            # comes back as stale 0xFF. Pad to the full length; hidraw on
            # macOS/Linux simply ignores the trailing zero bytes.
            if len(buf) < FEATURE_LEN:
                buf = buf + bytes(FEATURE_LEN - len(buf))
            self.h.send_feature_report(buf)
        if delay:
            time.sleep(delay)

    def _get_raw(self, report_id, length):
        if self.backend == "libusb":
            return bytes(self.dev.ctrl_transfer(0xA1, 0x01, (0x03 << 8) | report_id, self.iface, length))
        # Windows also needs the read buffer to cover the full report length.
        return bytes(self.h.get_feature_report(report_id, max(length, FEATURE_LEN) + 1))

    def _get(self, report_id, length):
        r = self._get_raw(report_id, length)
        if self.backend == "libusb":
            return r[:length]
        return r[1:1 + length] if len(r) > length else r[:length]

    def status(self):
        return self._get(REPORT_STATUS, 8)

    def _set_addr(self, blk):
        self._set([REPORT, SUB_SETADDR, (blk >> 8) & 0xFF, blk & 0xFF])

    def read(self, progress=None):
        import time
        nblk = CARD_SIZE // READ_CHUNK
        last = b"\xff" * CARD_SIZE
        for delay in (0.005, 0.015, 0.03, 0.07):
            out = bytearray()
            off = 0 if self.backend == "libusb" else None
            for blk in range(nblk):
                self._set_addr(blk)
                time.sleep(delay)
                r = self._get_raw(REPORT, READ_CHUNK)
                if off is None:
                    # This card uses an unnumbered HID report, and hidapi is not
                    # consistent across platforms/versions about whether it keeps
                    # the leading report-id byte. Block 0 always begins with
                    # 'KORG', so calibrate the payload offset from it once.
                    off = 0 if r[0:4] == b"KORG" else 1
                out += r[off:off + READ_CHUNK]
                if progress and blk % 16 == 0:
                    progress(blk / nblk)
            if bytes(out[:4]) == b"KORG":
                return bytes(out[:CARD_SIZE])
            last = bytes(out[:CARD_SIZE])
        return last

    def _write_block(self, img, blk):
        chunk = bytes(img[blk * WRITE_CHUNK:(blk + 1) * WRITE_CHUNK])
        chunk = chunk + bytes(WRITE_CHUNK - len(chunk))
        self._set([REPORT, SUB_WRITE, (blk >> 8) & 0xFF, blk & 0xFF] + list(chunk), 0.002)
        try:
            self._get(REPORT_ACK, 8)
        except Exception:
            pass

    def write(self, image, progress=None, blocks=None):
        img = bytearray(image)
        img[4] = RAM_MARKER
        n = (CARD_SIZE + WRITE_CHUNK - 1) // WRITE_CHUNK
        if blocks is None:
            self._set([REPORT, SUB_WRITE, 0, 0, 0xDE, 0xAD, 0xBE, 0xEF] + [0] * (WRITE_CHUNK - 4), 0.002)
            try:
                self._get(REPORT_ACK, 8)
            except Exception:
                pass
            blocks = range(n)
        for i, blk in enumerate(blocks):
            self._write_block(img, blk)
            if progress and i % 16 == 0:
                progress(i / n)

    def write_verify(self, image, progress=None, attempts=5):
        # Individual block writes occasionally drop on Windows HID, leaving a
        # corrupt block. Write, read back, and re-write exactly the blocks that
        # did not match; repeat until the card is byte-for-byte correct.
        intended = bytearray(image)
        intended[4] = RAM_MARKER
        intended = bytes(intended)
        self.write(image, (lambda p: progress(p * 0.6)) if progress else None)
        for _ in range(attempts):
            back = self.read((lambda p: progress(0.6 + p * 0.4)) if progress else None)
            if back == intended:
                return True
            bad = sorted({off // WRITE_CHUNK for off in range(CARD_SIZE) if back[off] != intended[off]})
            if not bad:
                return True
            if len(bad) > 64:
                self.write(image)
            else:
                self.write(image, blocks=bad)
        return self.read() == intended


def run_cli(args):
    if args[0] == "convert":
        open(args[2], "wb").write(bytes(build_card(args[1])))
        print("wrote", args[2])
    elif args[0] == "identify":
        img = open(args[1], "rb").read()
        prog = img[PROG_OFF:PROG_OFF + PROG_LEN]
        for f in glob.glob(os.path.join(args[2], "**", "*.syx"), recursive=True):
            b = parse_syx(open(f, "rb").read())
            if b.get(F_PROG) == prog:
                print("match:", f)
                return
        print("no match")


def _bundled(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, name)
    return p if os.path.exists(p) else None


def install_winusb_driver():
    if sys.platform != "win32":
        return False
    import subprocess, tempfile, webbrowser
    zadig = _bundled("zadig.exe")
    if not zadig:
        webbrowser.open("https://zadig.akeo.ie/")
        return False
    workdir = tempfile.mkdtemp(prefix="m1ram_drv_")
    with open(os.path.join(workdir, "zadig.ini"), "w") as f:
        f.write("[general]\nadvanced_mode=true\nexit_on_success=false\nlog_level=1\n"
                "[device]\nlist_all=true\ninclude_hubs=false\ntrim_whitespaces=true\n"
                "[driver]\ndefault_driver=0\n")
    cfg = os.path.join(workdir, "m1ram.cfg")
    with open(cfg, "w") as f:
        f.write("[device]\nDescription=m1Ram MC-02\nVID=0x16C0\nPID=0x1770\n")
    try:
        subprocess.Popen([zadig, cfg], cwd=workdir)
    except Exception:
        subprocess.Popen([zadig], cwd=workdir)
    return True


def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog

    app = tk.Tk()
    app.title("M1 RAM Manager")
    app.geometry("720x560")
    app.minsize(680, 520)
    state = {"files": [], "banks": [], "selected": None, "builder": Builder(), "last_img": None}

    top = ttk.Frame(app)
    top.pack(fill="x", padx=12, pady=8)
    ttk.Label(top, text="M1 RAM Manager", font=("Helvetica", 16, "bold")).pack(side="left")
    status = ttk.Label(top, text="", foreground="gray")
    status.pack(side="right")

    log = tk.Text(app, height=6)

    def out(s):
        log.insert("end", s + "\n")
        log.see("end")
        app.update_idletasks()

    def usb_job(fn):
        def worker():
            try:
                fn()
            except Exception as e:
                out("ERROR: %s" % e)
        threading.Thread(target=worker, daemon=True).start()

    def open_card_for_write():
        io = CardUSB()
        out("Backend: %s.%s" % (io.backend, (" " + io.note) if io.note else ""))
        if io.backend != "hid" or sys.platform != "win32":
            return io
        from tkinter import messagebox
        r = messagebox.askyesnocancel(
            "Install write driver?",
            "No WinUSB driver was found for the card.\n\n"
            "Reading works over the built-in driver, but a reliable WRITE needs WinUSB.\n\n"
            "Yes = install it now (opens Zadig already pointed at the card: click "
            "\"Install Driver\", approve the Windows prompt, then replug the card and Write again).\n"
            "No = try writing over the built-in driver anyway.\n"
            "Cancel = do nothing.")
        if r is None:
            return None
        if r:
            if install_winusb_driver():
                out("Opened the WinUSB installer. When it finishes, replug the card and press Write again.")
            else:
                out("Bundled installer not found; opened the Zadig site. Install WinUSB for device 16C0:1770.")
            return None
        return io

    nb = ttk.Notebook(app)
    nb.pack(fill="both", expand=True, padx=12, pady=4)

    tab_w = ttk.Frame(nb)
    nb.add(tab_w, text="Write bank")
    wlist = tk.Listbox(tab_w, height=8)
    wlist.pack(fill="both", expand=True, padx=8, pady=8)

    def w_pick():
        for f in filedialog.askopenfilenames(filetypes=[("Korg SysEx", "*.syx *.SYX"), ("All", "*.*")]):
            state["files"].append(f)
            wlist.insert("end", os.path.basename(f))

    def w_write():
        if not state["files"]:
            out("Pick a .SYX first.")
            return
        try:
            img = build_card(list(state["files"]))
        except Exception as e:
            out("Convert error: %s" % e)
            return

        io = open_card_for_write()
        if io is None:
            return

        def job():
            out("Writing + verifying (~20s)...")
            ok = io.write_verify(img, lambda p: status.config(text="%d%%" % int(p * 100)))
            out("DONE - verified OK." if ok else
                "Write did not verify. Press Write again to install the WinUSB driver.")
            status.config(text="")
        usb_job(job)
    wb = ttk.Frame(tab_w)
    wb.pack(fill="x", padx=8, pady=4)
    ttk.Button(wb, text="Choose .SYX...", command=w_pick).pack(side="left")
    ttk.Button(wb, text="Clear", command=lambda: (state["files"].clear(), wlist.delete(0, "end"))).pack(side="left", padx=6)
    ttk.Button(wb, text="Write to card", command=w_write).pack(side="right")

    tab_b = ttk.Frame(nb)
    nb.add(tab_b, text="Build custom")
    bctl = ttk.Frame(tab_b)
    bctl.pack(fill="x", padx=8, pady=6)
    binfo = ttk.Label(bctl, text="0/100 programs · 0/100 combis")
    binfo.pack(side="right")
    panes = ttk.Frame(tab_b)
    panes.pack(fill="both", expand=True, padx=8)
    banks_lb = tk.Listbox(panes, width=22)
    banks_lb.pack(side="left", fill="y")
    prog_lb = tk.Listbox(panes)
    prog_lb.pack(side="left", fill="both", expand=True, padx=4)
    combi_lb = tk.Listbox(panes)
    combi_lb.pack(side="left", fill="both", expand=True, padx=4)
    build_lb = tk.Listbox(panes, width=24)
    build_lb.pack(side="left", fill="y")

    def refresh_build():
        build_lb.delete(0, "end")
        for c in state["builder"].combis:
            build_lb.insert("end", "C " + rec_name(c))
        for p in state["builder"].progs:
            build_lb.insert("end", "P " + rec_name(p))
        binfo.config(text="%d/100 programs · %d/100 combis" % (len(state["builder"].progs), len(state["builder"].combis)))

    def load_folder():
        d = filedialog.askdirectory()
        if not d:
            return
        state["banks"] = []
        banks_lb.delete(0, "end")
        for f in sorted(glob.glob(os.path.join(d, "**", "*.syx"), recursive=True) +
                        glob.glob(os.path.join(d, "**", "*.SYX"), recursive=True)):
            try:
                state["banks"].append(Bank(f))
                banks_lb.insert("end", state["banks"][-1].title)
            except Exception:
                pass
        out("Loaded %d bank(s)." % len(state["banks"]))

    def select_bank(_e=None):
        sel = banks_lb.curselection()
        if not sel:
            return
        bank = state["banks"][sel[0]]
        state["selected"] = bank
        prog_lb.delete(0, "end")
        combi_lb.delete(0, "end")
        for i in range(N):
            n = bank.prog_name(i)
            if n:
                prog_lb.insert("end", "%02d %s" % (i, n))
            n = bank.combi_name(i)
            if n:
                combi_lb.insert("end", "%02d %s" % (i, n))

    def add_prog(_e=None):
        b = state["selected"]
        s = prog_lb.curselection()
        if b and s:
            state["builder"].add_program(b, int(prog_lb.get(s[0])[:2]))
            refresh_build()

    def add_combi(_e=None):
        b = state["selected"]
        s = combi_lb.curselection()
        if b and s:
            state["builder"].add_combi(b, int(combi_lb.get(s[0])[:2]))
            refresh_build()

    banks_lb.bind("<<ListboxSelect>>", select_bank)
    prog_lb.bind("<Double-Button-1>", add_prog)
    combi_lb.bind("<Double-Button-1>", add_combi)
    bbtn = ttk.Frame(tab_b)
    bbtn.pack(fill="x", padx=8, pady=6)
    ttk.Button(bbtn, text="Choose backups folder...", command=load_folder).pack(side="left")
    ttk.Button(bbtn, text="+ program", command=add_prog).pack(side="left", padx=4)
    ttk.Button(bbtn, text="+ combi", command=add_combi).pack(side="left", padx=4)
    ttk.Button(bbtn, text="Clear", command=lambda: (state["builder"].reset(), refresh_build())).pack(side="left", padx=4)

    def build_write():
        bd = state["builder"]
        if not bd.progs and not bd.combis:
            out("Add some presets first (double-click a program or combi).")
            return
        img = bd.image()
        io = open_card_for_write()
        if io is None:
            return

        def job():
            out("Writing custom card + verifying...")
            ok = io.write_verify(img, lambda p: status.config(text="%d%%" % int(p * 100)))
            out("DONE - verified OK." if ok else
                "Write did not verify. Press Write again to install the WinUSB driver.")
            status.config(text="")
        usb_job(job)
    ttk.Button(bbtn, text="Write custom card", command=build_write).pack(side="right")

    tab_c = ttk.Frame(nb)
    nb.add(tab_c, text="Card")
    ctitle = ttk.Label(tab_c, text="Click Read card", font=("Helvetica", 12, "bold"))
    ctitle.pack(anchor="w", padx=8, pady=6)
    cpanes = ttk.Frame(tab_c)
    cpanes.pack(fill="both", expand=True, padx=8)
    cprog = tk.Listbox(cpanes)
    cprog.pack(side="left", fill="both", expand=True, padx=4)
    ccombi = tk.Listbox(cpanes)
    ccombi.pack(side="left", fill="both", expand=True, padx=4)

    def read_card():
        def job():
            out("Reading card...")
            io = CardUSB()
            img = io.read(lambda p: status.config(text="%d%%" % int(p * 100)))
            status.config(text="")
            state["last_img"] = img
            cprog.delete(0, "end")
            ccombi.delete(0, "end")
            if bytes(img[:4]) != b"KORG":
                ctitle.config(text="Card reads blank / unwritten")
                return
            p, c = card_preset_names(img)
            real = [x for x in p if x and x != "INIT"]
            ctitle.config(text="Korg M1 card · %d programs · e.g. %s" % (len(real), ", ".join(real[:3])))
            for i, n in enumerate(p):
                cprog.insert("end", "%02d %s" % (i, n))
            for i, n in enumerate(c):
                ccombi.insert("end", "%02d %s" % (i, n))
        usb_job(job)

    def download_card():
        if state["last_img"] is None:
            out("Read the card first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".rom")
        if path:
            open(path, "wb").write(state["last_img"])
            out("Saved %s" % os.path.basename(path))

    def identify_card():
        if state["last_img"] is None:
            out("Read the card first.")
            return
        d = filedialog.askdirectory(title="Choose your card library folder")
        if not d:
            return
        prog = state["last_img"][PROG_OFF:PROG_OFF + PROG_LEN]
        for f in glob.glob(os.path.join(d, "**", "*.syx"), recursive=True):
            b = parse_syx(open(f, "rb").read())
            if b.get(F_PROG) == prog:
                brand = os.path.basename(os.path.dirname(f))
                out("This card is: %s / %s" % (brand, os.path.splitext(os.path.basename(f))[0]))
                return
        out("Not found in that library.")
    cbtn = ttk.Frame(tab_c)
    cbtn.pack(fill="x", padx=8, pady=6)
    ttk.Button(cbtn, text="Read card", command=read_card).pack(side="left")
    ttk.Button(cbtn, text="Identify from library...", command=identify_card).pack(side="left", padx=4)
    ttk.Button(cbtn, text="Download...", command=download_card).pack(side="left", padx=4)

    log.pack(fill="both", expand=False, padx=12, pady=6)
    app.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("convert", "identify"):
        run_cli(sys.argv[1:])
    else:
        run_gui()
