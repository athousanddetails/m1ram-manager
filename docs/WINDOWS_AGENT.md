# Windows agent handoff — M1 RAM Manager

Everything you need to make the Windows app read and write a Korg M1 RAM card
reliably, plus the non-obvious things that cost us time. Read this before
touching `windows/m1ram_manager.py`. The macOS Swift app is the ground truth;
the Python app is a faithful port of it and is byte-identical to Linux.

The single most important fact is at the top of the USB section: **writes must
be sent as HID report type "Input", not Output or Feature.** That one detail is
the whole reason the write works. If a rewrite ever "sends data but nothing
sticks", it is almost always this.

---

## 1. The device

- USB HID device, `VID 0x16C0` / `PID 0x1770`, product string `m1Ram MC-02`
  (XMicron). Vendor VID 0x16C0 is the shared "Van Ooijen / V-USB" pool, so do
  not identify the card by VID alone; match VID+PID.
- One HID interface (interface 0). No bulk endpoints are used; all traffic is
  control transfers (SET_REPORT / GET_REPORT).
- The card holds a single 32768-byte image (`CARD_SIZE`). That image is the
  whole product: 1 global block + 100 combinations + 100 programs.
- There is a physical **write-protect switch** on the card. If a write is
  silently ignored and the code looks correct, this is the first thing to check
  physically. A protected card still reads fine.

---

## 2. Two USB backends, and why

On Windows a USB device is owned by exactly one driver at a time, and that
choice decides which library can talk to it:

| Card is bound to        | `hidapi` sees it | `libusb`/`pyusb` sees it |
|-------------------------|:----------------:|:------------------------:|
| Built-in HID driver (default, no install) | yes | **no** |
| WinUSB (after Zadig)    | no               | **yes**                  |

So the two backends are mutually exclusive by which driver is bound. The app
tries them in this order (`class CardUSB.__init__`):

1. **libusb first.** If the card is bound to WinUSB, `usb.core.find(...)`
   returns it and we use raw control transfers. This is the reliable path,
   identical to macOS. We pass `libusb_package.get_libusb1_backend()` so no
   system libusb DLL needs to be installed.
2. **hidapi fallback.** If libusb finds nothing (fresh Windows, card still on
   the built-in HID driver), we open it with `hid.device()`. This needs **no
   driver install at all** and is how reads work out of the box.

`io.backend` is the string `"libusb"` or `"hid"`. The GUI prints it in the log
on every read/write so you always know which path ran.

### The catch that decides everything

`hidapi` can only send **Output** and **Feature** reports. It **cannot send
Input reports.** The card's reliable write requires an Input-type SET_REPORT
(see section 4). Therefore:

- **Reads are reliable over HID** (reads are Feature-type GET_REPORTs; HID does
  those fine).
- **Writes over HID are best-effort** (we fall back to sending them as Feature
  reports, which the card may or may not honor).
- **Writes are only guaranteed over libusb (WinUSB).**

This is why the app, on Windows with the HID backend, prompts the user to
install WinUSB before writing (section 5). Whether HID-only writes actually
stick is the one thing still unconfirmed on real Windows hardware — if you get a
box, test it and record the result here.

---

## 3. Card image layout (the 32768 bytes)

All offsets are into the raw card image. Constants live at the top of the file.

| Field   | Offset  | Length | Notes |
|---------|---------|--------|-------|
| Magic   | 0       | 4      | ASCII `KORG`. A blank/unwritten card does **not** have this. |
| Marker  | 4       | 1      | `0x10` = ROM/header card, `0x11` = RAM. The writer **forces `0x11`** (`RAM_MARKER`) into byte 4 before writing and when verifying. |
| Global  | 16      | 1225   | One global settings + drum-kit block. |
| Combis  | 1241    | 12400  | 100 combinations, `124` bytes each (`COMBI_REC`). |
| Programs| 13641   | 14300  | 100 programs, `143` bytes each (`PROG_REC`). |

Combi → program references: inside each 124-byte combi there are 8 timbres. The
program-pointer byte of each timbre sits at combi offsets
`[36, 47, 58, 69, 80, 91, 102, 113]` (`TIMBRE_PTRS`). On the **card**, a combi
that references an on-card program must have its pointer biased by `+100`
(`TIMBRE_BIAS`) relative to the SysEx numbering. The "build custom card" path
rewrites these pointers so a combi keeps playing the right programs after being
moved onto the card. If combis on a built card play the wrong sounds, this
rebasing is the place to look.

The global block: the M1 card format has no per-bank global that a writer can
reconstruct from an all-programs/all-combis dump, so the app ships a neutral
global+drum-kit block (`GLOBAL_TEMPLATE`, base64 at the top of the file, taken
from a factory card). Do not "clean this up" — it is real captured data.

---

## 4. USB protocol

### Report IDs and subcommands

```
REPORT        = 0x14   main data report (address + block payloads)
  SUB_SETADDR = 0x01   set the current block address
  SUB_WRITE   = 0x02   write a block (also used for the probe, see below)
REPORT_ACK    = 0x15   GET after a write returns an ack/status blob
REPORT_STATUS = 0x16   GET returns 8-byte device status
WRITE_CHUNK   = 60     payload bytes per write block
READ_CHUNK    = 64     payload bytes per read block
```

### Report TYPE — the load-bearing detail

HID report types are numbered differently in the two APIs we touch, which is
exactly how we burned a day. Keep both in your head:

| Type    | USB SET_REPORT/GET_REPORT `wValue` high byte | macOS IOKit `IOHIDReportType` |
|---------|:--------------------------------------------:|:-----------------------------:|
| Input   | 1                                            | 0 |
| Output  | 2                                            | 1 |
| Feature | 3                                            | 2 |

The vendor app, captured under lldb, issued its writes as IOKit type `0` =
**Input**. In USB terms that is a `SET_REPORT` with `wValue = (1 << 8) | 0x14`.
That is unusual — normally hosts SET Output/Feature and GET Input — and it is
the reason a "correct-looking" Feature/Output write silently does nothing.

**Writes (libusb):**
```python
dev.ctrl_transfer(0x21, 0x09, (0x01 << 8) | REPORT, iface, payload)
#                  ^bmReqType ^bRequest  ^Input type|report id
#  0x21 = Host->Device | Class | Interface
#  0x09 = SET_REPORT
#  0x01 << 8 = report type Input
```

**Reads (libusb):**
```python
dev.ctrl_transfer(0xA1, 0x01, (0x03 << 8) | report_id, iface, length)
#  0xA1 = Device->Host | Class | Interface
#  0x01 = GET_REPORT
#  0x03 << 8 = report type Feature
```

**HID backend equivalents:** `h.send_feature_report(payload)` for `_set` (note:
Feature, because HID has no Input-send — this is the compromise) and
`h.get_feature_report(report_id, length + 1)` for `_get`. hidapi prepends the
report ID byte on the returned buffer, so we request `length + 1` and strip the
first byte.

### Set-address then transfer

The card is addressed by **block index**, not byte offset. Address is a 16-bit
big-endian block number split across two payload bytes:

```python
def _set_addr(self, blk):
    self._set([REPORT, SUB_SETADDR, (blk >> 8) & 0xFF, blk & 0xFF])
```

### Read algorithm

512 blocks of 64 bytes (`512 * 64 = 32768`). For each block: set address, wait a
settle delay, GET 64 bytes on report `0x14`.

The card needs time to present each block, and how much time it needs drifts. We
do the **whole read** at one settle delay, and if the result does not start with
`KORG`, we retry the whole read at a longer delay, escalating:

```python
for delay in (0.005, 0.015, 0.03, 0.07):   # 5, 15, 30, 70 ms per block
    ... read all 512 blocks with time.sleep(delay) after each set_addr ...
    if out[:4] == b"KORG":
        return out
```

A card that reads all `0xFF` or all `0x00` almost always means the settle delay
was too short (or the card is blank). The escalation is what fixed the
"reads come back as garbage" bug — do not remove it, and do not assume a single
fixed delay is enough on every host.

### Write algorithm

`ceil(32768 / 60) = 547` blocks of up to 60 bytes, last block zero-padded.

1. **Probe / write-enable handshake first.** Before the real blocks we send one
   `SUB_WRITE` to address 0 whose payload begins `DE AD BE EF` then zero-fill,
   and read the ack. This is the observed unlock/handshake the vendor app does;
   send it before the data blocks.
2. Force `img[4] = 0x11` (RAM marker).
3. For each block: `SET_REPORT` (Input) with `[REPORT, SUB_WRITE, hi, lo, ...60
   payload bytes]`, then GET `REPORT_ACK` (ignore failures), ~2 ms between
   blocks (`delay=0.002`).

```python
self._set([REPORT, SUB_WRITE, (blk >> 8) & 0xFF, blk & 0xFF] + list(chunk), 0.002)
```

### Verify

`write_verify` writes, then reads the card back and compares against the
intended image with byte 4 forced to `0x11`. Equality → the write is confirmed
on-card. The GUI treats a failed verify as "did not stick" and (on the HID
backend) points the user at the WinUSB install. Verify is cheap insurance —
keep it on by default.

### Status

`status()` GETs 8 bytes on `REPORT_STATUS` (0x16). The libusb init also does one
throwaway status GET as a liveness probe so a dead handle fails fast at connect
rather than mid-write.

---

## 5. Windows driver flow (what the user sees)

Reading needs nothing. Writing reliably needs the card on WinUSB. The app does
not (and on Windows cannot) install a driver silently — Windows requires a UAC
elevation prompt to bind a USB driver. So instead it **asks**:

1. On **Write**, `open_card_for_write()` runs on the main thread (Tk dialogs
   from the worker thread crash — keep this on the main thread). If the backend
   is `hid` and we're on `win32`, it shows a Yes/No/Cancel dialog.
2. **Yes** → `install_winusb_driver()` launches the **bundled Zadig** (packed
   into the exe via PyInstaller `--add-data "zadig.exe;."`, found at runtime via
   `sys._MEIPASS`). We write a `zadig.ini` (`default_driver=0` = WinUSB,
   `list_all=true`, `advanced_mode=true`) and a preset `m1ram.cfg`
   (`Description=m1Ram MC-02`, `VID=0x16C0`, `PID=0x1770`) into a temp dir and
   launch `zadig.exe m1ram.cfg` with `cwd` set to that dir, so Zadig opens
   already pointed at the card. User clicks Install Driver, approves UAC.
3. After install the device leaves the HID driver and binds WinUSB, so the
   existing handle is stale — the user must **replug and press Write again**.
   Next time, libusb finds it and the write is reliable.
4. If Zadig is not bundled (running from source, not the release exe), the
   button opens `https://zadig.akeo.ie/` for a manual install.

Zadig source: `pbatard/libwdi` release `v1.5.1`, asset `zadig-2.9.exe`. It is
the signed upstream tool; do not ship an unsigned repack.

---

## 6. SysEx → card conversion (context)

Input files are standard Korg M1 SysEx dumps. Function IDs we handle:

- `0x4C` all programs (`F_PROG`), `0x4D` all combinations (`F_COMBI`),
  `0x51` global, `0x50` all-data (single message, 8-byte header, contains
  global+combi+program back to back), `0x40` single program (5-byte header),
  `0x48` sequence.
- Korg packs 8-bit data as 7-bit MIDI: groups of 7 data bytes preceded by one
  byte holding their high bits. `korg_unpack` / `korg_pack` do this. Get the
  MSB-byte-first ordering right or every value is subtly corrupt.

The converter is byte-identical across macOS/Windows/Linux; if a card built on
Windows differs from one built on macOS from the same `.syx`, that is a bug in
the port, not the card.

---

## 7. Known quirks and gotchas

- **Input-type write** (section 4) — the #1 thing. `type=0` in the macOS capture
  = Input = `(0x01<<8)` in USB.
- **HID cannot send Input reports**, so HID-backend writes degrade to Feature
  and may not stick. Reads over HID are fine.
- **Read pacing drifts** — the escalating 5/15/30/70 ms retry is required; a
  fixed delay fails on some hosts/cards.
- **Backends are mutually exclusive by bound driver** — libusb only sees the
  card after Zadig; hidapi only sees it before. Try libusb first, fall back.
- **Stale handle after driver change** — installing WinUSB detaches the HID
  handle. Always replug + reconnect after a Zadig install.
- **Tk dialogs must be on the main thread.** The USB work runs in a worker
  thread (`usb_job`); the driver prompt is deliberately done before spawning it.
- **Write-protect switch** — a physical switch can silently defeat every write.
  Check it before debugging software.
- **Blank card has no `KORG` header** — `read()` returning non-`KORG` after all
  retries can just mean an unwritten card, not a failure.
- **`libusb-package`** supplies the libusb backend so users don't install a
  system DLL; on Windows the card still must be on WinUSB for libusb to see it.
- **Do not add code comments.** The repo owner wants source comment-free; put
  rationale in commit messages, not in the source.

---

## 8. What is verified vs not

- **macOS:** read, write, write-verify, build-custom, identify — all
  hardware-verified on a real card. This is the reference behavior.
- **Converter (all OSes):** byte-identical output, verified.
- **Windows/Linux USB path:** ported faithfully from macOS and compiles in CI,
  but the read/write has **not** been confirmed on real Windows/Linux hardware
  yet. Specifically unconfirmed: whether an HID-only (no-WinUSB) write sticks,
  and whether the escalating read delays are enough on Windows timing. When you
  test on hardware, write the result into this section.

---

## 9. Quick troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| "No m1RAM card found" | not plugged / not enumerated | replug; confirm `16C0:1770` in Device Manager |
| Reads return all `0xFF`/`0x00` | settle delay too short, or blank card | rely on the escalation; confirm card actually has data |
| Write log says backend `hid`, verify fails | no WinUSB driver | click Yes on the prompt → install via bundled Zadig → replug → Write again |
| Write does nothing at all, backend `libusb` | wrong report type in a rewrite | writes must be SET_REPORT type **Input** `(0x01<<8)` |
| Combis play wrong programs on a built card | timbre pointer `+100` rebase | check `TIMBRE_PTRS` / `TIMBRE_BIAS` handling |
| Zadig button does nothing from source | exe not bundled | expected outside the release build; it opens the Zadig site instead |
