# M1 RAM Manager

Read, write, organize, and identify **Korg M1** USB RAM cards (XMicron m1Ram MC-02) directly from a computer — no Korg M1 hardware needed for the transfer.

Feed it a standard Korg M1 SysEx bank (`.syx`) and it writes a ready-to-play card. It also builds custom cards by cherry-picking presets across many backups, reads a card back, and identifies which card is loaded by matching its contents against a library.

## Features

- **Write** any Korg M1 `.syx` bank (100 programs + 100 combinations) straight to the card, with read-back verification.
- **Merge** split dumps (separate All-Programs / All-Combinations / Global files) into one card.
- **Build custom cards** — pick programs and combinations from any backups; picking a combination automatically pulls in the programs it uses and rewrites the references so it plays correctly.
- **Read / download** a card, list its program and combination names.
- **Identify** a loaded card by matching its sounds against a folder of `.syx` banks.

## Download & run (macOS)

Grab the app from [Releases](../../releases). It is ad-hoc signed (not notarized), so macOS Gatekeeper quarantines downloaded copies. To open it:

```bash
xattr -dr com.apple.quarantine "M1 RAM Manager.app"
```

then double-click it. (Or right-click the app → **Open** → **Open** the first time.)

On first card access, macOS may ask for **Input Monitoring** permission for the app — allow it (needed to talk to the USB HID device).

## Build from source

**macOS** (Xcode command-line tools):

```bash
cd macos
./build.sh          # produces "M1 RAM Manager.app"
```

**Windows / Linux** (Python 3, libusb):

```bash
pip install pyusb            # plus a libusb backend (see below)
python cross-platform/m1ram_manager.py
```

- Linux: `sudo apt install libusb-1.0-0`, and add a udev rule for `16c0:1770` (or run with sudo).
- Windows: install a libusb-compatible driver for the device with [Zadig](https://zadig.akeo.ie/) (WinUSB or libusb-win32).
- The converter is byte-identical to the macOS app; the USB read/write path is faithfully ported but should be validated on real Windows/Linux hardware.

## Command-line tools (`cli/`)

Cross-platform helpers (Python + `hidapi` for the macOS USB path):

```bash
python cli/m1ram.py convert bank.syx out.rom        # SYX -> card image
python cli/m1ram.py merge  out.rom a.syx b.syx c.syx
python cli/m1card.py out.rom in.syx [more.syx ...]  # low-level converter
```

`cli/capture_hid.py` is an lldb script used during reverse-engineering to log the original app's HID traffic — kept for reference.

## Repository layout

```
macos/            SwiftUI app (main.swift) + build.sh + AppIcon
cross-platform/   Python (Tkinter + pyusb) app for Windows/Linux/macOS
cli/              Python converter + USB tools + global template
docs/PROTOCOL.md  the reverse-engineered card format and USB protocol
```

## Notes

- `global_template.bin` / the embedded global block is a neutral global + drum-kit block used as the default for the card's global area (the M1 card format has no per-bank global that the writer reconstructs). It comes from a factory card layout.
- The card stores no "card name" — the Identify feature recovers a name by matching program content against a library.
- Full technical details of the format and USB protocol are in [`docs/PROTOCOL.md`](docs/PROTOCOL.md).
