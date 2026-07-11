# Korg M1 RAM card — format & USB protocol

Reverse-engineered for the XMicron **m1Ram MC-02** USB card. Everything here was verified on real hardware.

## Card image (32768 bytes)

The card is a raw memory image:

| Offset | Size | Contents |
|--------|------|----------|
| `0x0000` | 16 | Header: `4B 4F 52 47` (`"KORG"`), then byte 4 = card marker, rest zero |
| `0x0010` | 1225 | Global + 4 drum-kits |
| `0x04D9` (1241) | 12400 | 100 combinations × 124 bytes |
| `0x3549` (13641) | 14300 | 100 programs × 143 bytes |
| `0x6D25` (27941) | … | zero padding |

- **Header byte 4:** `0x10` on a ROM card, `0x11` on a RAM card. The writer stamps `0x11`.
- **Program record** (143 bytes): bytes 0–9 = 10-char name.
- **Combination record** (124 bytes): bytes 0–9 = name; then common params; then **8 timbres × 11 bytes** starting at offset 36 (offsets 36, 47, 58, 69, 80, 91, 102, 113). In each timbre, byte 0 = program number, byte 10 = status (bit `0x10` set = timbre off).
- **Timbre program pointers on the card are biased by +100** relative to the SysEx dump: a combination that references internal program *n* (0–99) stores *n+100* on the card (pointing at the card's own program bank). The writer adds 100 to all 8 timbre bytes of every combination; a reader subtracts it.

## SysEx dump formats

A `.syx` bank is one or more Korg System Exclusive messages. Header: `F0 42 3g 19 <func> <fmt> …payload… F7` where `g` = MIDI channel, `19` = M1 model id. Payload is Korg 8→7-bit packed (one MSB byte carries bit 7 of the next 7 data bytes).

| Func | Meaning | Header len | Unpacked payload |
|------|---------|-----------|------------------|
| `0x4C` | All Programs | 6 bytes | 14300 (100 × 143) |
| `0x4D` | All Combinations | 6 bytes | 12400 (100 × 124) |
| `0x51` | Global | 6 bytes | ~861 |
| `0x50` | **All Data** (single message) | **8 bytes** | `[global 861][combi 12400][program 14300][seq…]` |
| `0x40` | single Program (current) | 5 bytes | 143 |
| `0x48` | Sequence data | — | — |

To build a card from a `0x50` All-Data dump: unpack after the 8-byte header, then take global `[0:861]`, combi `[861:13261]`, program `[13261:27561]`.

## USB HID protocol

- Device: USB HID, **VID `0x16C0` / PID `0x1770`** (V-USB gadget), 64-byte reports.
- All traffic uses **report id `0x14`** with a sub-command as the first data byte:
  - `14 02 <blkHi> <blkLo> <60 data bytes>` — **write** one 60-byte block. 547 blocks cover 32768.
  - `14 01 <blkHi> <blkLo>` — **set the read address** to a 64-byte block. Then read report `0x14` (512 blocks × 64 bytes = 32768).
- Report `0x15` (GET) returns a constant magic `AA BB CC` (polled as a handshake between write blocks).
- Report `0x16` (GET) returns device status.
- Write session: read `0x16`, write a `DE AD BE EF` probe to block 0 and read it back (writability test — an isolated block-0 write only succeeds if the write-protect switch is off), then stream all blocks from 0.

### Report type — the critical detail

**Writes must use report type Input**, not Feature:

- macOS (IOKit): `IOHIDDeviceSetReport(dev, kIOHIDReportTypeInput, 0x14, buf, len)`. Feature-type writes only stick intermittently; Input-type is reliable.
- Reads use `kIOHIDReportTypeFeature`.
- Cross-platform (libusb): a raw HID `SET_REPORT` control transfer with report type = **Input (1)** in `wValue` high byte: `bmRequestType=0x21, bRequest=0x09, wValue=(0x01<<8)|0x14`. Reads use `GET_REPORT` with Feature (3): `bmRequestType=0xA1, bRequest=0x01, wValue=(0x03<<8)|0x14`.

### Timing

The card's read timing drifts with connection quality. Reads need a settle delay **after** setting the address and **before** reading the block; 5 ms is usually enough, but escalate (5 → 12 → 30 → 70 ms) and retry the whole read until the header comes back as `KORG`, to ride out a marginal (hub/cable) link.

## Write-protect switch

Physical switch on the card. It only gates writes (reads always work). If a write is silently ignored, the switch is engaged. It is read by the M1 through the card edge connector and is **not exposed over USB**.
