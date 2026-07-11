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

That is it. The app talks to the card over the built-in Windows HID driver, so **no Zadig / no driver install is needed** — for reading *or* writing.

## Reading and writing

Both read and write run over the built-in Windows HID driver. Use the **Card** tab to read the card, and the **Write bank** tab to write a `.SYX`; the write is verified by reading the card back and comparing byte-for-byte. The log shows the backend in use (normally `hid`).

## Notes

- The converter/organizer works identically to macOS.
- The USB path uses raw HID feature reports, padded to the card's full 64-byte report length (Windows `HidD_SetFeature` rejects shorter reports, which is why an earlier build failed to read on Windows).
- If a write does not verify, check the card's physical **write-protect switch** and that it is fully seated.
