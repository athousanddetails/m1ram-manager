# M1 RAM Manager — Linux

> ⚠️ **UNTESTED ON LINUX HARDWARE.** The Linux build shares the exact same code
> as the Windows app, which is fully hardware-verified (read, write+verify,
> marker `0x10`, cold-card read, identify-from-library). The Linux USB path has
> **not yet been tested on a real card**. It should behave the same over hidraw,
> but treat it as beta until someone confirms a read and a write+verify on
> Linux hardware — and please report the result back.

Same app as macOS/Windows (the SysEx→card converter is byte-identical).

## Setup

1. Install libusb, hidapi, Python, and Tkinter:
   ```
   sudo apt install libusb-1.0-0 libhidapi-hidraw0 python3 python3-tk
   pip install -r requirements.txt
   ```
2. Allow non-root access to the card (udev rule), or run with `sudo`:
   ```
   echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="1770", MODE="0666"' \
     | sudo tee /etc/udev/rules.d/99-m1ram.rules
   echo 'KERNEL=="hidraw*", ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="1770", MODE="0666"' \
     | sudo tee -a /etc/udev/rules.d/99-m1ram.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
   (Replug the card afterward.)
3. Run:
   ```
   python3 m1ram_manager.py
   ```

## Notes

- The converter/organizer works identically to macOS.
- Read and write both use plain HID feature reports over the built-in hidraw
  driver — no special driver, no Input-type reports (the Windows vendor app and
  our verified Windows build both work this way). It tries libusb first only if
  a WinUSB/libusb device happens to be bound; otherwise it uses hidraw.
- Writes verify by reading the card back and re-writing any dropped blocks.
- On a cold/reinserted card, block 0 (the header) reads `0xFF`; the app reads
  all blocks and rebuilds the `KORG` header (same as the vendor app).
- If a write is silently ignored, check the card's physical **write-protect switch**.
