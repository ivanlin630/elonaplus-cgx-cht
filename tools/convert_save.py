"""Convert an Elona+ save made with the Simplified-Chinese (GBK) build so it
displays in the Traditional/Shift-JIS translation.

Only text files are touched (names, map names, quest names, logs); binary
data files are left alone. The whole save folder is copied to
<save>.gbk-backup first (refuses to run if that backup already exists).

Usage: python -I convert_save.py <save folder> [--from gbk]
"""
import sys, os, re, shutil
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
import opencc
from sjis_map import sjis_safe

cc = opencc.OpenCC('s2twp')
LINE_FILES = re.compile(r'^(cdatan.*\.s[12]|mdatan.*\.s2|qname\.s1|gdatan\.s1|art\.log|news\.log)$')


def conv(s, src, lost):
    t = s.decode(src, errors='replace')
    return sjis_safe(cc.convert(t), lost).encode('cp932', errors='replace')


def main(d, src='gbk'):
    d = d.rstrip('/\\')
    bk = d + '.gbk-backup'
    if os.path.exists(bk):
        sys.exit(f'backup {bk} already exists - this save was converted before, aborting')
    shutil.copytree(d, bk)
    lost, files = {}, 0
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        b = open(p, 'rb').read()
        if not any(c > 127 for c in b):
            continue
        if LINE_FILES.match(f):
            out = b'\r\n'.join(conv(x, src, lost) if any(c > 127 for c in x) else x for x in b.split(b'\r\n'))
        elif f == 'header.txt':
            i = b.find(b'\0')
            i = len(b) if i < 0 else i
            t = conv(b[:i], src, lost)[:len(b) - 1]
            out = t + b'\0' * (len(b) - len(t))
        else:
            continue
        open(p, 'wb').write(out)
        files += 1
    print(f'converted {files} files in {d}; backup at {bk}')
    if lost:
        print('substituted:', ' '.join(f'{k}->{v}' for k, v in sorted(lost.items())))


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[a.index('--from') + 1] if '--from' in a else 'gbk')
