"""Converte imagem para o formato PAR da Bluetrum emulando a função original
raw_to_par() de libabpartool.so (ARM64, extraída do app LaxasFit) com Unicorn.

Uso: venv/bin/python par.py entrada.png saida.par [largura altura]
Entrada do raw_to_par: pixels ARGB (4 bytes/pixel), como ImageUtils.getRawImageData.
Assinatura (do wrapper JNI): int raw_to_par(uint8 *saida, uint8 *entrada, int w, int h,
                                         bool, bool, bool)   saída alocada com w*h*4.
"""
import os
import struct
import sys

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from PIL import Image
from unicorn import UC_ARCH_ARM64, UC_HOOK_CODE, UC_MODE_ARM, Uc
from unicorn.arm64_const import (UC_ARM64_REG_LR, UC_ARM64_REG_PC, UC_ARM64_REG_SP,
                                 UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2,
                                 UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X5,
                                 UC_ARM64_REG_X6, UC_ARM64_REG_TPIDR_EL0)

# Biblioteca proprietária da Bluetrum: NÃO vem no repositório. Extraia do APK oficial
# (config.arm64_v8a.apk -> lib/arm64-v8a/libabpartool.so) para linux/vendor/ ou use T900_ABPARTOOL.
SO = os.environ.get("T900_ABPARTOOL", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                                   "vendor", "libabpartool.so"))
RAW_TO_PAR = 0x15F40
BASE = 0x0
STUBS = 0x1000000      # endereços falsos das funções importadas
HEAP = 0x2000000
HEAP_SIZE = 0x4000000
STACK = 0x8000000
STACK_SIZE = 0x200000
TLS = 0x9000000
FIM = 0xA000000        # endereço de retorno sentinela


class Emu:
    def __init__(self):
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.heap_ptr = HEAP
        self.stubs = {}
        elf = ELFFile(open(SO, "rb"))
        topo = 0
        for seg in elf.iter_segments():
            if seg["p_type"] == "PT_LOAD":
                topo = max(topo, seg["p_vaddr"] + seg["p_memsz"])
        self.uc.mem_map(BASE, (topo + 0xFFFF) & ~0xFFFF)
        for seg in elf.iter_segments():
            if seg["p_type"] == "PT_LOAD":
                self.uc.mem_write(BASE + seg["p_vaddr"], seg.data())
        for mem, size in ((STUBS, 0x10000), (HEAP, HEAP_SIZE), (STACK, STACK_SIZE),
                          (TLS, 0x10000), (FIM, 0x1000)):
            self.uc.mem_map(mem, size)
        self.uc.mem_write(STUBS, b"\xc0\x03\x5f\xd6" * (0x10000 // 4))  # ret
        self.uc.reg_write(UC_ARM64_REG_TPIDR_EL0, TLS)  # canário em [tpidr+0x28]
        dynsym = elf.get_section_by_name(".dynsym")
        for sec in elf.iter_sections():
            if not isinstance(sec, RelocationSection):
                continue
            for r in sec.iter_relocations():
                tipo, off = r["r_info_type"], r["r_offset"]
                if tipo == 1027:  # R_AARCH64_RELATIVE
                    self.uc.mem_write(BASE + off, struct.pack("<Q", BASE + r["r_addend"]))
                elif tipo in (1025, 1026, 257):  # GLOB_DAT, JUMP_SLOT, ABS64
                    nome = dynsym.get_symbol(r["r_info_sym"]).name
                    sym = dynsym.get_symbol(r["r_info_sym"])
                    if sym["st_shndx"] != "SHN_UNDEF":
                        alvo = BASE + sym["st_value"]
                    else:
                        alvo = STUBS + 4 * len(self.stubs)
                        self.stubs[alvo] = nome
                    self.uc.mem_write(BASE + off, struct.pack("<Q", alvo + r["r_addend"]))
        self.uc.hook_add(UC_HOOK_CODE, self._stub, begin=STUBS, end=STUBS + 0xFFFF)

    def malloc(self, n):
        p = (self.heap_ptr + 15) & ~15
        self.heap_ptr = p + max(n, 16)
        if self.heap_ptr > HEAP + HEAP_SIZE:
            raise MemoryError("heap da emulação esgotado")
        return p

    def _stub(self, uc, addr, size, _):
        nome = self.stubs.get(addr)
        if nome is None:
            return
        x0, x1, x2 = (uc.reg_read(r) for r in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2))
        if nome in ("_Znam", "_Znwm", "malloc"):
            uc.reg_write(UC_ARM64_REG_X0, self.malloc(x0))
        elif nome in ("_ZdaPv", "_ZdlPv", "free"):
            pass
        elif nome in ("memcpy", "memmove", "__memmove_chk"):
            uc.mem_write(x0, bytes(uc.mem_read(x1, x2)))
        elif nome == "memset":
            uc.mem_write(x0, bytes([x1 & 0xFF]) * x2)
        elif nome == "__stack_chk_fail":
            raise RuntimeError("stack_chk_fail na emulação")
        else:
            raise RuntimeError(f"função importada não emulada: {nome}")

    def raw_to_par(self, argb, w, h, a=False, b=False, c=False):
        entrada = self.malloc(len(argb))
        self.uc.mem_write(entrada, argb)
        saida = self.malloc(w * h * 4)
        sp = STACK + STACK_SIZE - 0x1000
        regs = (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3,
                UC_ARM64_REG_X4, UC_ARM64_REG_X5, UC_ARM64_REG_X6)
        for reg, v in zip(regs, (saida, entrada, w, h, int(a), int(b), int(c))):
            self.uc.reg_write(reg, v)
        self.uc.reg_write(UC_ARM64_REG_SP, sp)
        self.uc.reg_write(UC_ARM64_REG_LR, FIM)
        self.uc.emu_start(BASE + RAW_TO_PAR, FIM)
        n = self.uc.reg_read(UC_ARM64_REG_X0) & 0xFFFFFFFF
        if n == 0 or n > w * h * 4:
            raise RuntimeError(f"raw_to_par retornou {n}")
        return bytes(self.uc.mem_read(saida, n))


def imagem_para_argb(caminho, w, h):
    img = Image.open(caminho).convert("RGBA").resize((w, h), Image.LANCZOS)
    out = bytearray()
    for r, g, b, a in img.getdata():
        out += bytes((a, r, g, b))
    return bytes(out)


def main():
    entrada, saida = sys.argv[1], sys.argv[2]
    w, h = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (240, 286)
    par = Emu().raw_to_par(imagem_para_argb(entrada, w, h), w, h)
    open(saida, "wb").write(par)
    print(f"PAR {w}x{h}: {len(par)} bytes; início {par[:16].hex(' ')}")


if __name__ == "__main__":
    main()
