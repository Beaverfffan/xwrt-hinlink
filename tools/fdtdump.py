import struct, sys

def parse(path):
    d = open(path, 'rb').read()
    (magic, totalsize, off_dt_struct, off_dt_strings, off_mem_rsvmap,
     ver, lastcomp, boot_cpuid, size_strings, size_struct) = struct.unpack('>10I', d[:40])
    strings = d[off_dt_strings:off_dt_strings + size_strings]
    st = d[off_dt_struct:off_dt_struct + size_struct]
    i = 0
    stack = []
    out = []  # (path, prop, value-bytes)

    def sname(n):
        e = strings.index(b'\0', n)
        return strings[n:e].decode()

    while i < len(st):
        tok = struct.unpack('>I', st[i:i + 4])[0]
        i += 4
        if tok == 1:  # BEGIN_NODE
            e = st.index(b'\0', i)
            stack.append(st[i:e].decode())
            i = (e + 4) & ~3
        elif tok == 2:  # END_NODE
            stack.pop()
        elif tok == 3:  # PROP
            ln, noff = struct.unpack('>II', st[i:i + 8])
            i += 8
            val = st[i:i + ln]
            i += (ln + 3) & ~3
            out.append(('/'.join(stack), sname(noff), val))
        elif tok == 4:  # NOP
            pass
        elif tok == 9:  # END
            break
    return out


def show(rows, want):
    for pn, name, val in rows:
        if want and want not in pn:
            continue
        try:
            s = val.decode('ascii')
            printable = all(32 <= ord(c) < 127 or c == '\0' for c in s)
        except Exception:
            printable = False
        if printable:
            print('%-70s %-22s = "%s"' % (pn, name, s.replace('\0', '|')))
        elif len(val) % 4 == 0 and len(val) <= 64:
            print('%-70s %-22s = %s' % (pn, name, ' '.join('%08x' % x for x in struct.unpack('>%dI' % (len(val) // 4), val))))
        else:
            print('%-70s %-22s = %s' % (pn, name, val.hex()))


if __name__ == '__main__':
    show(parse(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None)
