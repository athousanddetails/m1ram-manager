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

## Build / run from source

**macOS** (`mac/`, needs the Xcode command-line tools):

```bash
cd mac
./build.sh          # produces "M1 RAM Manager.app"
```

**Windows** (`windows/`) and **Linux** (`linux/`) — Python 3 + libusb. Each folder has the app plus a per-OS `README.md` with the exact setup (Zadig driver on Windows; libusb + udev rule on Linux):

```bash
pip install pyusb
python m1ram_manager.py
```

The converter is byte-identical across all three; the USB read/write path is faithfully ported from the verified macOS version and should be validated once on real Windows/Linux hardware.

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
mac/              macOS SwiftUI app (main.swift) + build.sh + AppIcon
windows/          Windows app (Python + libusb) + setup README
linux/            Linux app (Python + libusb) + setup README
cli/              Python converter + USB tools + global template
docs/PROTOCOL.md  the reverse-engineered card format and USB protocol
```

## Notes

- `global_template.bin` / the embedded global block is a neutral global + drum-kit block used as the default for the card's global area (the M1 card format has no per-bank global that the writer reconstructs). It comes from a factory card layout.
- The card stores no "card name" — the Identify feature recovers a name by matching program content against a library.
- Full technical details of the format and USB protocol are in [`docs/PROTOCOL.md`](docs/PROTOCOL.md).
