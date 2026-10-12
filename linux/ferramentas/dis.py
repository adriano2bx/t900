import sys
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
f = open(sys.argv[1], 'rb'); e = ELFFile(f)
start, size = int(sys.argv[2], 16), int(sys.argv[3])
for seg in e.iter_segments():
    if seg['p_type'] == 'PT_LOAD' and seg['p_vaddr'] <= start < seg['p_vaddr'] + seg['p_filesz']:
        data = seg.data()[start - seg['p_vaddr']: start - seg['p_vaddr'] + size]
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
# PLT -> símbolo
plt = {}
rela = e.get_section_by_name('.rela.plt'); dyn = e.get_section_by_name('.dynsym')
pltsec = e.get_section_by_name('.plt')
if rela and pltsec:
    for i, r in enumerate(rela.iter_relocations()):
        plt[pltsec['sh_addr'] + 32 + 16 * i] = dyn.get_symbol(r['r_info_sym']).name
for ins in md.disasm(data, start):
    extra = ''
    if ins.mnemonic in ('bl', 'b') and ins.op_str.startswith('#'):
        t = int(ins.op_str[1:], 16); extra = '   ; ' + plt.get(t, hex(t))
    if ins.mnemonic in ('bl', 'blr', 'ret') or sys.argv[4:] == ['all']:
        print(hex(ins.address), ins.mnemonic, ins.op_str, extra)
