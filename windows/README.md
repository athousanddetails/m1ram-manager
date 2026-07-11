# M1 RAM Manager — Windows

Same app as macOS/Linux (the SysEx→card converter is byte-identical).

## Setup

1. Install **Python 3** (python.org). Tkinter ships with it.
2. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   python m1ram_manager.py
   ```

That is it. The app talks to the card over the built-in Windows HID driver, so **no Zadig / no driver install is needed** for reading a card. When you write, the log shows the backend in use (`hid` or `libusb`).

## If a write does not verify

Reads are reliable over the built-in HID driver. A reliable **write** path uses libusb, which on Windows needs the card bound to the WinUSB driver:

- Plug in the card.
- Run **[Zadig](https://zadig.akeo.ie/)**, select the device **`16C0:1770` (m1Ram MC-02)**, and install the **WinUSB** driver for it.
- Re-run the app. The write backend will now show `libusb` and writes are verified.
- (You can revert the driver in Device Manager later if you want the card back as plain HID.)

## Notes

- The converter/organizer works identically to macOS.
- The USB read path uses raw HID feature reports; the reliable write path uses libusb `SET_REPORT` control transfers with the **Input** report type, exactly as the card requires (mirrors the verified macOS implementation).
- If a write is silently ignored, also check the card's physical **write-protect switch**.
