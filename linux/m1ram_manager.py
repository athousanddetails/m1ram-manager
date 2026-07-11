import sys, os, struct, glob, hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

VID, PID = 0x16C0, 0x1770
CARD_SIZE = 32768
REPORT = 0x14
SUB_SETADDR, SUB_WRITE = 0x01, 0x02
REPORT_ACK, REPORT_STATUS = 0x15, 0x16
WRITE_CHUNK, READ_CHUNK = 60, 64
RAM_MARKER = 0x11
GLOBAL_OFF, GLOBAL_LEN = 16, 1225
COMBI_OFF, COMBI_LEN = 1241, 12400
PROG_OFF, PROG_LEN = 13641, 14300
N_COMBI, COMBI_REC = 100, 124
TIMBRE_PTRS = [36, 47, 58, 69, 80, 91, 102, 113]
TIMBRE_BIAS = 100
F_PROG, F_COMBI = 0x4C, 0x4D
GLOBAL_TEMPLATE = "AAABAAEAAAABBwAAAAAAAM4AAAAAAADOAQAAGAUAGAAAAAABABoFABoAAAAAAgAcBQAcAAAAAAMAHQUAHQAAAAAEAB8FAB8AAAAABQAhBQAhAAAAAAYAIwUAIwAAAAAHACQHACQAAAAACAAmAxQnAAAAAAkAKAcUKgAAAAAKACkEACkAAAAACwArBAArAAAAAAwALQQALQAAAAANAC8EAC8AAAAADgAwBwAwAADdAA8AMgJGMgAAAAAQADQIADQAAAAAEQA1ASg1AAAAABIANwkANwAAAAATADkGADkAAAAAFAA7BgA7AAAAABUAPAYAPAAAAAAdAD4FAD4AAAAAFwBABQBAAAAAABgAQQEAQQAAAAAZAEMJAEMAAAAAGgBFBABFAAAAABsARwEARwAAAAAcAEgJAEgAAAAAFgBUBbBXAAAAAAAAGAUAGQAAEQAFABoF7BoAAAAAGgAcCBQe3wAAAAoAHQIAHfEAAAALAB8CAB8AAOoACgAeAgAeAADzAAIAGQXYGQAAAQAGABsF9hvdAAAACAAmAuwlAAAAAAkALAUoLmMAAAAJADAIHi4AAAAACgAyBwAyAADtAAsAIAIAIAAAnQAPADQD9jkAAAAADwA1BwA1AAAAABAANwfsLwAAAAAQADYFADYAAAAAEQA4AABEAAAAABEAOQIAOQAAAAASADoKAEYAAAAAEgA7CB48AABjABMAPAYAPAAAAAAUAD8E2EHrAGMAFQBACABA5wCdABUAQQcAQWMAAAAXAEID2EIAAAAAFgBKBRRMAAAAABwASwT2QgAAAAAkAEwHAE4AAOQAHABzBSh7AADDAAAAGAUAGewADAAHABkFKBsAABQABgAaBQAaRgAAABQAGwgyGu0AAAAIAB0KAB4jAAAACgAeCPYdxwAAABoAIAUeJDIAAAAJACEFACEAAAAACwAiCeIh1gAAAAkAJAD2IgAAAAAOACUAAB4yAM4ADgAmCOwkAADmABcAKAn2J80AIAAWACkKADXOAAAADwAqAAAqAAAAABYALQXsMOIAAAAQAC4AAC4AAAAAFgAwAOIqzgAyACEAOwXYOwAAYwAgAEIF7EUAAAAAEwA9BQBCAAAAAB0ARwXsSgAAAAAeAE4F7FAAAAAAAgBIBQBIYwAIAAMASgUATGMAAAAEAEwFAExjAAAAGABUBQBUAAAAAP//DAUADAAAAAD//w0FAA0AAAAA//8OBQAOAAAAAP//MAUAMAAAAAD//zIFADIAAAAA//80BQA0AAAAAP//NQUANQAAAAD//zcFADcAAAAA//85BQA5AAAAAP//OwUAOwAAAAD//zwFADwAAAAA//8+BQA+AAAAAP//QAUAQAAAAAD//0EFAEEAAAAA//9DBQBDAAAAAP//RQUARQAAAAD//0cFAEcAAAAA//9IBQBIAAAAAP//SgUASgAAAAD//0wFAEwAAAAA//9NBQBNAAAAAP//TwUATwAAAAD//1EFAFEAAAAA//9TBQBTAAAAAP//VAUAVAAAAAD//1YFAFYAAAAA//9YBQBYAAAAAP//WQUAWQAAAAD//1sFAFsAAAAA//9dBQBdAAAAAP//XwUAXwAAAAD//2AFAGAAAAAA//9iBQBiAAAAAA=="


def korg_unpack(data):
    out = bytearray()
    i = 0
    while i < len(data):
        msb = data[i]; i += 1
        for k in range(7):
            if i >= len(data): break
            b = data[i]; i += 1
            if msb & (1 << k): b |= 0x80
            out.append(b)
    return bytes(out)


def korg_pack(data):
    out = bytearray()
    i = 0
    while i < len(data):
        group = data[i:i + 7]; i += 7
        msb = 0
        for k, b in enumerate(group):
            if b & 0x80: msb |= (1 << k)
        out.append(msb)
        out.extend(b & 0x7F for b in group)
    return bytes(out)


def parse_syx(raw):
    blocks = {}; i = 0
    while i < len(raw):
        if raw[i] != 0xF0:
            i += 1; continue
        j = raw.find(0xF7, i)
        if j < 0: break
        seg = raw[i:j + 1]
        if len(seg) >= 6 and seg[1] == 0x42 and seg[3] == 0x19 and seg[4] not in blocks:
            blocks[seg[4]] = korg_unpack(seg[6:-1])
        i = j + 1
    return blocks


def build_card(paths):
    if isinstance(paths, str): paths = [paths]
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


def assemble(prog, combi):
    import base64
    card = bytearray(CARD_SIZE)
    card[0:5] = b"KORG\x10"
    t = base64.b64decode(GLOBAL_TEMPLATE)
    card[GLOBAL_OFF:GLOBAL_OFF + GLOBAL_LEN] = t[:GLOBAL_LEN]
    card[PROG_OFF:PROG_OFF + PROG_LEN] = prog
    cb = bytearray(combi)
    for n in range(N_COMBI):
        base = n * COMBI_REC
        for off in TIMBRE_PTRS:
            cb[base + off] = (cb[base + off] + TIMBRE_BIAS) & 0xFF
    card[COMBI_OFF:COMBI_OFF + COMBI_LEN] = cb
    return bytes(card)


class CardUSB:
    def __init__(self):
        import usb.core, usb.util
        self.usb = usb.util
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise RuntimeError("No m1RAM card found on USB (%04x:%04x)." % (VID, PID))
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
        except Exception:
            pass
        try:
            self.dev.set_configuration()
        except Exception:
            pass
        self.iface = 0

    def _set(self, payload, delay=0.0):
        self.dev.ctrl_transfer(0x21, 0x09, (0x01 << 8) | REPORT, self.iface, bytes(payload))
        if delay: __import__("time").sleep(delay)

    def _get(self, report_id, length):
        return bytes(self.dev.ctrl_transfer(0xA1, 0x01, (0x03 << 8) | report_id, self.iface, length))

    def status(self):
        return self._get(REPORT_STATUS, 8)

    def _set_addr(self, blk):
        self._set([REPORT, SUB_SETADDR, (blk >> 8) & 0xFF, blk & 0xFF])

    def read(self, progress=None):
        for delay in (0.005, 0.015, 0.03, 0.07):
            out = bytearray()
            for blk in range(CARD_SIZE // READ_CHUNK):
                self._set_addr(blk); __import__("time").sleep(delay)
                out += self._get(REPORT, READ_CHUNK)[:READ_CHUNK]
                if progress and blk % 16 == 0: progress(blk / (CARD_SIZE // READ_CHUNK))
            if bytes(out[:4]) == b"KORG":
                return bytes(out[:CARD_SIZE])
        return bytes(out[:CARD_SIZE])

    def write(self, image, progress=None):
        img = bytearray(image); img[4] = RAM_MARKER
        self._set([REPORT, SUB_WRITE, 0, 0] + list(b"\xde\xad\xbe\xef") + [0] * (WRITE_CHUNK - 4), 0.002)
        try: self._get(REPORT_ACK, 8)
        except Exception: pass
        n = (CARD_SIZE + WRITE_CHUNK - 1) // WRITE_CHUNK
        for blk in range(n):
            chunk = bytes(img[blk * WRITE_CHUNK:(blk + 1) * WRITE_CHUNK])
            chunk = chunk + bytes(WRITE_CHUNK - len(chunk))
            self._set([REPORT, SUB_WRITE, (blk >> 8) & 0xFF, blk & 0xFF] + list(chunk), 0.002)
            try: self._get(REPORT_ACK, 8)
            except Exception: pass
            if progress and blk % 16 == 0: progress(blk / n)

    def write_verify(self, image):
        self.write(image, None)
        back = self.read(None)
        intended = bytearray(image); intended[4] = RAM_MARKER
        return back == bytes(intended)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("M1 RAM Manager")
        self.geometry("560x420")
        self.files = []
        ttk.Label(self, text="M1 RAM Manager", font=("Helvetica", 16, "bold")).pack(pady=6)
        f = ttk.Frame(self); f.pack(fill="x", padx=12)
        ttk.Button(f, text="Choose .SYX bank(s)...", command=self.pick).pack(side="left")
        ttk.Button(f, text="Write to card", command=self.write).pack(side="right")
        self.lst = tk.Listbox(self, height=8); self.lst.pack(fill="both", expand=True, padx=12, pady=8)
        self.log = tk.Text(self, height=8); self.log.pack(fill="both", expand=True, padx=12, pady=6)

    def out(self, s):
        self.log.insert("end", s + "\n"); self.log.see("end"); self.update()

    def pick(self):
        fs = filedialog.askopenfilenames(filetypes=[("Korg SysEx", "*.syx *.SYX"), ("All", "*.*")])
        for x in fs:
            self.files.append(x); self.lst.insert("end", os.path.basename(x))

    def write(self):
        if not self.files:
            self.out("Pick a .SYX file first."); return
        try:
            img = build_card(list(self.files))
        except Exception as e:
            self.out("Convert error: %s" % e); return
        try:
            self.out("Connecting to card...")
            io = CardUSB()
            self.out("Writing + verifying (this can take ~20s)...")
            ok = io.write_verify(img)
            self.out("DONE - verified OK. Put the card in your M1." if ok else "Write done but verify FAILED.")
        except Exception as e:
            self.out("USB error: %s" % e)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "convert":
        open(sys.argv[3], "wb").write(bytes(build_card(sys.argv[2])))
        print("wrote", sys.argv[3])
    else:
        App().mainloop()
