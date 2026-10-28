"""Build the Chinese data\\*.txt/csv for Custom-GX.

Skeleton = Custom-GX's own Japanese data (cp932). Text = Chinese 2.30
translation (GBK, Simplified) matched section by section, converted to
Traditional (OpenCC s2twp), written in the table encoding (Big5 by default).
Sections with no Chinese counterpart keep Japanese and are listed in
work/data_untranslated.tsv (file, key, text) for machine translation; a
second pass (--fill) substitutes those from work/mt/sakura.tsv.

Usage: python -I merge_data.py <cgx_data_dir> <chs_data_dir> <out_dir> [--encoding cp950] [--fill]
"""
import sys, os, re, shutil, csv
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
import opencc
from inject import big5_safe, gbk_safe

cc = opencc.OpenCC('s2twp')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JPRX = re.compile('[぀-ヿ一-鿿]')


def rd(d, f, e):
    return open(os.path.join(d, f), 'rb').read().decode(e)


def sections(lines, ismark):
    secs, cur = [], ('__head__', [])
    for l in lines:
        if ismark(l):
            secs.append(cur); cur = (l, [l])
        else:
            cur[1].append(l)
    secs.append(cur)
    return secs


def main():
    a = sys.argv[1:]
    J, C, OUT = a[0], a[1], a[2]
    enc = a[a.index('--encoding') + 1] if '--encoding' in a else 'cp932'
    fill = '--fill' in a
    mt = {}
    if fill:
        for line in open(os.path.join(ROOT, 'work', 'mt', 'sakura.tsv'), encoding='utf-8'):
            k, _, v = line.rstrip('\n').partition('\t')
            if v: mt[k] = v
    lost, todo, report = {}, [], []

    def write(f, text, lines_are_zh=True):
        t = cc.convert(text) if lines_are_zh else text
        if enc == 'cp932':
            from sjis_map import sjis_safe
            t = sjis_safe(t, lost)
        else:
            t = big5_safe(t, lost) if enc == 'cp950' else gbk_safe(t)
        open(os.path.join(OUT, f), 'wb').write(t.encode(enc, errors='replace'))

    def jp_line(f, key, l):
        """Untranslated Japanese line: machine translation if we have it, else keep + list it."""
        if JPRX.search(l) and re.search('[぀-ヿ]', l):
            if l in mt:
                return mt[l]
            todo.append((f, key, l))
        return l

    pct = lambda l: l.startswith('%')
    mk = lambda k: re.sub(r'\s*/.*$', '', k).strip()
    for f in ('book.txt', 'talk.txt', 'exhelp.txt'):
        tj = rd(J, f, 'cp932'); tc = rd(C, f, 'gbk')
        sj = sections(tj.split('\r\n'), pct); sc = sections(tc.split('\r\n' if '\r\n' in tc else '\n'), pct)
        cmap = {}
        for k, body in sc: cmap.setdefault(mk(k), []).append(body)
        used, out, miss = {}, [], 0
        for k, body in sj:
            kk = mk(k); i = used.get(kk, 0); used[kk] = i + 1
            if kk in cmap and i < len(cmap[kk]):
                out += cmap[kk][i]
            else:
                out += [body[0]] + [jp_line(f, kk, l) for l in body[1:]] if body else []
                miss += 1 if any(JPRX.search(x) for x in body) else 0
        write(f, '\r\n'.join(out))
        report.append(f'{f}: sections {len(sj)}, no Chinese counterpart {miss}')
    # manual: chapters by order
    tj = rd(J, 'manual_JP.txt', 'cp932').splitlines(); tc = rd(C, 'manual_JP.txt', 'gbk').splitlines()
    sj = sections(tj, lambda l: l.startswith('{}')); sc = sections(tc, lambda l: l.startswith('{}'))
    out = []
    for i, (k, body) in enumerate(sj):
        out += sc[i][1] if i < len(sc) else body
    for k, body in sc[len(sj):]: out += body
    write('manual_JP.txt', '\r\n'.join(out) + '\r\n')
    report.append(f'manual_JP.txt: chapters cgx {len(sj) - 1} / chs {len(sc) - 1}')
    # line-aligned files
    for f in ('board.txt', 'name.csv', 'ndata.csv', 'ndata-e.csv'):
        lj = rd(J, f, 'cp932').splitlines(); lc = rd(C, f, 'gbk').splitlines()
        out = [lc[i] if i < len(lc) else lj[i] for i in range(len(lj))]
        write(f, '\r\n'.join(out) + '\r\n')
        report.append(f'{f}: lines cgx {len(lj)} / chs {len(lc)}')
    # autopick.txt: Custom-GX only, no Chinese source
    # autopick.txt is a rules sample whose Japanese words are matcher keywords
    # used by the code: copy it unchanged.
    if os.path.exists(os.path.join(J, 'autopick.txt')):
        shutil.copy(os.path.join(J, 'autopick.txt'), os.path.join(OUT, 'autopick.txt'))
        report.append('autopick.txt: copied unchanged (matcher keywords)')
    with open(os.path.join(ROOT, 'work', 'data_untranslated.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        for f, k, l in todo: w.write(f'{f}\t{k}\t{l}\n')
    print('\n'.join(report))
    print(f'untranslated Japanese lines: {len(todo)} -> work/data_untranslated.tsv')
    if lost: print('substituted:', ' '.join(f'{k}->{v}' for k, v in sorted(lost.items())))


if __name__ == '__main__':
    main()
