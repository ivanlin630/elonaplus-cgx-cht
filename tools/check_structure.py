"""Compare src/ with a translated tree: report lines whose top-level structure
(argument commas, bracket depth, open string) changed. Any hit is a bug in
the rewrite, not in the translation."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
BS = chr(92)


def shape(l):
    d, q, n, i = 0, False, 0, 0
    while i < len(l):
        c = l[i]
        if q:
            if c == BS:
                i += 1
            elif c == '"':
                q = False
        else:
            if c == '"':
                q = True
            elif c == ';':
                break
            elif c in '([':
                d += 1
            elif c in ')]':
                d -= 1
            elif c == ',' and d == 0:
                n += 1
        i += 1
    return n, d, q


def main(src, tree):
    bad = 0
    for f in sorted(os.listdir(src)):
        if not f.endswith('.hsp') or f.startswith('scene') or f == 'highdpi.hsp':
            continue
        a = open(os.path.join(src, f), 'rb').read().decode('cp932').splitlines()
        b = open(os.path.join(tree, f), 'rb').read().decode('cp932').splitlines()
        if f == 'main.hsp':
            b = [x for x in b if x.strip() not in ('#include "zh.hsp"', 'zh_load')]
        if len(a) != len(b):
            print('line count differs', f, len(a), len(b)); continue
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y and shape(x) != shape(y):
                bad += 1
                if bad <= 15:
                    print(f, i + 1, shape(x), '->', shape(y))
                    print('  -', x.strip()[:160]); print('  +', y.strip()[:160])
    print('lines with changed structure:', bad)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
