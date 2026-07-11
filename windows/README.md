# M1 RAM Manager — Windows

Same app as macOS/Linux (the SysEx→card converter is byte-identical). Python + libusb.

## Setup

1. Install **Python 3** (python.org). Tkinter ships with it.
2. Install the USB dependency:
   ```
   pip install pyusb
   ```
3. Install a libusb backend + bind it to the card:
   - Plug in the card.
   - Run **[Zadig](https://zadig.akeo.ie/)**, select the device **`16C0:1770` (m1Ram MC-02)**, and install the **WinUSB** (or libusb-win32) driver for it.
   - This lets libusb talk to the card. (You can revert the driver in Device Manager later if needed.)
4. Run:
   ```
   python m1ram_manager.py
   ```

## Notes

- The converter/organizer works identically to macOS.
- The USB **read/write** path uses raw libusb `SET_REPORT`/`GET_REPORT` control transfers (Input-type for writes, as the card requires). It mirrors the verified macOS implementation but should be **validated once on real hardware** on Windows.
- If a write is silently ignored, check the card's physical **write-protect switch**.
