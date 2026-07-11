HEADER = bytes([0x4B, 0x4F, 0x52, 0x47, 0x10] + [0] * 11)
GLOBAL_OFF, GLOBAL_LEN = 16, 1225
COMBI_OFF, COMBI_LEN = 1241, 12400
PROG_OFF, PROG_LEN = 13641, 14300
CARD_SIZE = 32768
N_PROG = N_COMBI = 100
PROG_REC, COMBI_REC = 143, 124
TIMBRE_PTR_OFFSETS = [36, 47, 58, 69, 80, 91, 102, 113]
TIMBRE_CARD_BIAS = 100

FUNC_ALLPROG, FUNC_ALLCOMBI, FUNC_GLOBAL = 0x4C, 0x4D, 0x51
KORG_ID, M1_ID = 0x42, 0x19


def korg_unpack(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        msb = data[i]
        i += 1
        for k in range(7):
            if i >= len(data):
                break
            b = data[i]
            i += 1
            if msb & (1 << k):
                b |= 0x80
            out.append(b)
    return bytes(out)


def korg_pack(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        group = data[i : i + 7]
        i += 7
        msb = 0
        for k, b in enumerate(group):
            if b & 0x80:
                msb |= 1 << k
        out.append(msb)
        out.extend(b & 0x7F for b in group)
    return bytes(out)


def parse_syx(raw: bytes) -> dict:
    blocks = {}
    i = 0
    while i < len(raw):
        if raw[i] != 0xF0:
            i += 1
            continue
        j = raw.find(0xF7, i)
        if j < 0:
            break
        seg = raw[i : j + 1]
        if len(seg) >= 6 and seg[1] == KORG_ID and seg[3] == M1_ID:
            func = seg[4]

            blocks[func] = korg_unpack(seg[6:-1])
        i = j + 1
    return blocks


def build_card_from_blocks(
    prog: bytes, combi: bytes, global_template: bytes = None
) -> bytes:
    if len(prog) != PROG_LEN:
        raise ValueError(f"program block {len(prog)} != {PROG_LEN}")
    if len(combi) != COMBI_LEN:
        raise ValueError(f"combi block {len(combi)} != {COMBI_LEN}")
    card = bytearray(CARD_SIZE)
    card[0:16] = HEADER
    if global_template is not None:
        card[GLOBAL_OFF : GLOBAL_OFF + GLOBAL_LEN] = global_template[:GLOBAL_LEN]
    card[PROG_OFF : PROG_OFF + PROG_LEN] = prog
    cb = bytearray(combi)
    for n in range(N_COMBI):
        base = n * COMBI_REC
        for off in TIMBRE_PTR_OFFSETS:
            cb[base + off] = (cb[base + off] + TIMBRE_CARD_BIAS) & 0xFF
    card[COMBI_OFF : COMBI_OFF + COMBI_LEN] = cb
    return bytes(card)


def build_card(syx_paths, global_template: bytes = None) -> bytes:
    if isinstance(syx_paths, str):
        syx_paths = [syx_paths]
    b = {}
    for p in syx_paths:
        for func, payload in parse_syx(open(p, "rb").read()).items():
            b.setdefault(func, payload)
    prog = b.get(FUNC_ALLPROG)
    combi = b.get(FUNC_ALLCOMBI)
    if prog is None or combi is None:
        raise ValueError(
            "Need all-programs (0x4C) and all-combinations (0x4D) dumps across the "
            "given file(s); found funcs: " + ", ".join(f"0x{f:02x}" for f in b)
        )
    if len(prog) != PROG_LEN:
        raise ValueError(f"program block {len(prog)} != {PROG_LEN}")
    if len(combi) != COMBI_LEN:
        raise ValueError(f"combi block {len(combi)} != {COMBI_LEN}")

    card = bytearray(CARD_SIZE)
    card[0:16] = HEADER

    if global_template is not None:
        card[GLOBAL_OFF : GLOBAL_OFF + GLOBAL_LEN] = global_template[:GLOBAL_LEN]

    card[PROG_OFF : PROG_OFF + PROG_LEN] = prog

    cb = bytearray(combi)
    for n in range(N_COMBI):
        base = n * COMBI_REC
        for off in TIMBRE_PTR_OFFSETS:
            cb[base + off] = (cb[base + off] + TIMBRE_CARD_BIAS) & 0xFF
    card[COMBI_OFF : COMBI_OFF + COMBI_LEN] = cb

    return bytes(card)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("usage: m1card.py out.rom in.syx [more.syx ...]")
        sys.exit(1)
    out_path, ins = sys.argv[1], sys.argv[2:]
    out = build_card(ins)
    open(out_path, "wb").write(out)
    print(f"wrote {len(out)} bytes -> {out_path}")
