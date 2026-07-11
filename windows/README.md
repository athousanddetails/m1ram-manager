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

## Writing (one-click driver install)

Reads work with no driver. A reliable **write** uses libusb, which on Windows needs the card bound to the **WinUSB** driver. You don't have to hunt for anything: when you press **Write** and no WinUSB driver is found, the app asks:

> No WinUSB driver was found for the card. Install it now?

Click **Yes** and it launches the bundled **Zadig** installer already pointed at the card (`m1Ram MC-02`, `16C0:1770`). Click **Install Driver**, approve the Windows prompt, then replug the card and press **Write** again — the backend now shows `libusb` and writes are verified. (Click **No** to try writing over the built-in driver anyway; **Cancel** to do nothing.)

The compiled `.exe` from [Releases](../../releases) has Zadig bundled inside it. If you run from source instead, the button opens the [Zadig download page](https://zadig.akeo.ie/) so you can install it manually (select `16C0:1770`, install WinUSB). You can revert the driver in Device Manager later.

## Notes

- The converter/organizer works identically to macOS.
- The USB read path uses raw HID feature reports; the reliable write path uses libusb `SET_REPORT` control transfers with the **Input** report type, exactly as the card requires (mirrors the verified macOS implementation).
- If a write is silently ignored, also check the card's physical **write-protect switch**.

## For developers

Full protocol, timings, backend logic, and every quirk we hit are documented in [`../docs/WINDOWS_AGENT.md`](../docs/WINDOWS_AGENT.md). Read it before changing the USB code.
