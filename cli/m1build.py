import importlib.util, os

_spec = importlib.util.spec_from_file_location(
    "m1card", os.path.join(os.path.dirname(__file__), "m1card.py")
)
m1card = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m1card)

PROG_REC, COMBI_REC = 143, 124
N = 100
T_OFFS = [36, 47, 58, 69, 80, 91, 102, 113]
T_STRIDE = 11


def _name(rec):
    return "".join(chr(c) if 32 <= c < 127 else " " for c in rec[:10]).rstrip()


class Bank:
    def __init__(self, path):
        self.path = path
        self.title = os.path.splitext(os.path.basename(path))[0]
        b = m1card.parse_syx(open(path, "rb").read())
        prog, combi = b.get(0x4C), b.get(0x4D)
        if not prog or not combi:
            raise ValueError(f"{self.title}: not a full bank (needs 0x4C+0x4D)")
        self.progs = [prog[i * PROG_REC : (i + 1) * PROG_REC] for i in range(N)]
        self.combis = [combi[i * COMBI_REC : (i + 1) * COMBI_REC] for i in range(N)]

    def prog_name(self, i):
        return _name(self.progs[i])

    def combi_name(self, i):
        return _name(self.combis[i])

    def combi_timbres(self, i):
        rec = self.combis[i]
        out = []
        for t, off in enumerate(T_OFFS):
            status = rec[off + 10]
            if (status & 0x10) == 0:
                out.append((t, rec[off]))
        return out


class Builder:
    def __init__(self):
        self.progs = []
        self.combis = []
        self._prog_src = {}
        self.warnings = []

    def _add_prog(self, bank, idx):
        key = (bank.path, idx)
        if key in self._prog_src:
            return self._prog_src[key]
        if len(self.progs) >= N:
            self.warnings.append(f"program slots full; '{bank.prog_name(idx)}' dropped")
            return None
        slot = len(self.progs)
        self.progs.append(bytearray(bank.progs[idx]))
        self._prog_src[key] = slot
        return slot

    def add_program(self, bank, idx):
        return self._add_prog(bank, idx)

    def add_combi(self, bank, idx):
        if len(self.combis) >= N:
            self.warnings.append(f"combi slots full; '{bank.combi_name(idx)}' dropped")
            return
        rec = bytearray(bank.combis[idx])
        for t, srcprog in bank.combi_timbres(idx):
            slot = self._add_prog(bank, srcprog)
            if slot is not None:
                rec[T_OFFS[t]] = slot
        self.combis.append(rec)

    def image(self, global_template=None, init_prog=None, init_combi=None):
        if init_prog is None:
            init_prog = self.progs[0] if self.progs else bytes(PROG_REC)
        if init_combi is None:
            init_combi = bytes(COMBI_REC)
        prog_block = b"".join(
            bytes(self.progs[i]) if i < len(self.progs) else bytes(init_prog)
            for i in range(N)
        )
        combi_block = b"".join(
            bytes(self.combis[i]) if i < len(self.combis) else bytes(init_combi)
            for i in range(N)
        )
        return m1card.build_card_from_blocks(prog_block, combi_block, global_template)

    def summary(self):
        return f"{len(self.progs)}/100 programs, {len(self.combis)}/100 combis" + (
            "" if not self.warnings else "  [" + "; ".join(self.warnings) + "]"
        )
