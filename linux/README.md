# M1 RAM Manager — Linux

Same app as macOS/Windows (the SysEx→card converter is byte-identical). Python + libusb.

## Setup

1. Install libusb, Python, and Tkinter:
   ```
   sudo apt install libusb-1.0-0 python3 python3-tk
   pip install pyusb
   ```
2. Allow non-root access to the card (udev rule), or run with `sudo`:
   ```
   echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="1770", MODE="0666"' \
     | sudo tee /etc/udev/rules.d/99-m1ram.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
   (Replug the card afterward.)
3. Run:
   ```
   python3 m1ram_manager.py
   ```

## Notes

- The converter/organizer works identically to macOS.
- The USB **read/write** path uses raw libusb `SET_REPORT`/`GET_REPORT` control transfers (Input-type for writes, as the card requires). It mirrors the verified macOS implementation but should be **validated once on real hardware** on Linux.
- If a write is silently ignored, check the card's physical **write-protect switch**.
