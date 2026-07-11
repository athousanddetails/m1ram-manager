import sys, os, time, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1card

VID, PID = 0x16C0, 0x1770
CARD_SIZE = 32768

REPORT = 0x14
SUB_SETADDR, SUB_WRITE = 0x01, 0x02
REPORT_ACK = 0x15
REPORT_STATUS = 0x16
WRITE_CHUNK = 60
READ_CHUNK = 64
N_WRITE = (CARD_SIZE + WRITE_CHUNK - 1) // WRITE_CHUNK
N_READ = CARD_SIZE // READ_CHUNK
RAM_MARKER = 0x11
GLOBAL_TEMPLATE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "global_template.bin"
)


def _open():
    try:
        import hid
    except ImportError:
        sys.exit("Missing dependency. Run:  pip3 install hidapi")
    d = hid.device()
    try:
        d.open(VID, PID)
    except (OSError, IOError):
        sys.exit(
            f"No m1RAM card found (looking for USB {VID:#06x}:{PID:#06x}). "
            "Plug it in; on macOS grant Input Monitoring if prompted."
        )
    d.set_nonblocking(0)
    return d


def read_status(d):
    return bytes(d.get_feature_report(REPORT_STATUS, 8))


def _ack(d):
    try:
        d.get_feature_report(REPORT_ACK, 8)
    except Exception:
        pass


def _set_addr(d, blk):
    d.send_feature_report(bytes([REPORT, SUB_SETADDR, (blk >> 8) & 0xFF, blk & 0xFF]))


def read_card(d):
    data = bytearray()
    for blk in range(N_READ):
        _set_addr(d, blk)
        rep = bytes(d.get_feature_report(REPORT, READ_CHUNK + 1))

        payload = rep[1 : 1 + READ_CHUNK] if len(rep) > READ_CHUNK else rep[:READ_CHUNK]
        data.extend(payload)
        if blk % 64 == 0:
            print(
                f"\r  reading {min(len(data),CARD_SIZE)}/{CARD_SIZE}",
                end="",
                flush=True,
            )
    print()
    return bytes(data[:CARD_SIZE])


def write_card(d, image, probe=True):
    assert len(image) == CARD_SIZE
    image = bytearray(image)
    image[4] = RAM_MARKER
    if probe:
        d.send_feature_report(
            bytes([REPORT, SUB_WRITE, 0, 0])
            + b"\xde\xad\xbe\xef"
            + bytes(WRITE_CHUNK - 4)
        )
        _ack(d)
        _set_addr(d, 0)
        d.get_feature_report(REPORT, READ_CHUNK + 1)
    for blk in range(N_WRITE):
        chunk = bytes(image[blk * WRITE_CHUNK : (blk + 1) * WRITE_CHUNK])
        chunk = chunk + bytes(WRITE_CHUNK - len(chunk))
        d.send_feature_report(
            bytes([REPORT, SUB_WRITE, (blk >> 8) & 0xFF, blk & 0xFF]) + chunk
        )
        _ack(d)
        if blk % 64 == 0:
            print(
                f"\r  writing {min((blk+1)*WRITE_CHUNK,CARD_SIZE)}/{CARD_SIZE}",
                end="",
                flush=True,
            )
    print()


def cmd_info(_):
    d = _open()
    print(f"Found m1RAM card at USB {VID:#06x}:{PID:#06x}")
    try:
        print("  manufacturer:", d.get_manufacturer_string())
        print("  product     :", d.get_product_string())
    except Exception:
        pass
    st = read_status(d)
    print("  status report 0x16:", st[:8].hex(" "))
    print("  write-protected   :", "YES" if st and st[0] else "no (best-guess reading)")
    d.close()


def cmd_dump(a):
    d = _open()
    img = read_card(d)
    d.close()
    open(a.out, "wb").write(img)
    print(f"Saved {len(img)} bytes -> {a.out}   (header {img[:4]!r})")


def _build_image(paths, raw):
    if isinstance(paths, str):
        paths = [paths]
    if raw:
        img = open(paths[0], "rb").read()
        if len(img) != CARD_SIZE:
            sys.exit(f"{paths[0]} is {len(img)} bytes, expected {CARD_SIZE}")
        return img
    tmpl = (
        open(GLOBAL_TEMPLATE, "rb").read() if os.path.exists(GLOBAL_TEMPLATE) else None
    )
    return m1card.build_card(paths, global_template=tmpl)


def cmd_convert(a):
    img = _build_image(a.syx, a.raw)
    open(a.out, "wb").write(img)
    print(f"Built card image {len(img)} bytes -> {a.out}")


def cmd_merge(a):
    tmpl = (
        open(GLOBAL_TEMPLATE, "rb").read() if os.path.exists(GLOBAL_TEMPLATE) else None
    )
    img = m1card.build_card(a.syx, global_template=tmpl)
    open(a.out, "wb").write(img)
    print(f"Merged {len(a.syx)} files -> {len(img)}-byte image -> {a.out}")


def cmd_write(a):
    img = _build_image(a.src, a.raw)
    d = _open()
    print("Card status 0x16:", read_status(d)[:4].hex(" "))
    if not a.yes:
        label = a.src[0] if isinstance(a.src, list) else a.src
        print(f"About to overwrite the card with {label} ({len(img)} bytes).")
        if input("Type 'write' to proceed: ").strip() != "write":
            d.close()
            sys.exit("Aborted.")
    print("Writing...")
    write_card(d, img)
    print("Verifying (reading back)...")
    back = read_card(d)
    d.close()
    intended = bytearray(img)
    intended[4] = RAM_MARKER
    if back == bytes(intended):
        print(
            "VERIFIED OK - card matches the image byte-for-byte. Insert it in the M1."
        )
    else:
        diff = sum(1 for x, y in zip(back, intended) if x != y)
        first = next((i for i, (x, y) in enumerate(zip(back, intended)) if x != y), -1)
        sys.exit(
            f"VERIFY FAILED: {diff}/{len(img)} bytes differ (first at {first}). "
            "Card is rewritable so no harm done - tell me and I'll adjust."
        )


def main():
    p = argparse.ArgumentParser(description="Korg M1 RAM USB card tool")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info").set_defaults(fn=cmd_info)
    d = sub.add_parser("dump")
    d.add_argument("out")
    d.set_defaults(fn=cmd_dump)
    c = sub.add_parser("convert")
    c.add_argument("syx")
    c.add_argument("out")
    c.add_argument("--raw", action="store_true")
    c.set_defaults(fn=cmd_convert)
    mg = sub.add_parser(
        "merge",
        help="combine separate AllPrograms/AllCombis/GlobalSetup .SYX into one image",
    )
    mg.add_argument("out")
    mg.add_argument("syx", nargs="+")
    mg.set_defaults(fn=cmd_merge)
    w = sub.add_parser("write")
    w.add_argument(
        "src",
        nargs="+",
        help="one full .SYX, several .SYX to merge, or a .rom with --raw",
    )
    w.add_argument("--raw", action="store_true", help="src is a .rom image, not a .SYX")
    w.add_argument("--yes", action="store_true", help="skip confirmation")
    w.set_defaults(fn=cmd_write)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
