# M1 RAM Manager — Linux

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
- The app tries libusb first (reliable Input-type writes, mirroring the verified macOS path) and falls back to the built-in HID driver. The write log shows which backend is active.
- If a write is silently ignored, check the card's physical **write-protect switch**.
- Validate a write/read once on real hardware; the converter itself is byte-identical to the macOS build.
