"""Write translations from strings.tsv back into a copy of the HSP source.

For every lang(JP, EN) row with a non-empty zh column, the JP argument is
rebuilt from the zh template: text becomes string literals, {n} becomes the
n-th original code piece. Rows with empty zh are left untouched.

Usage: python -I inject.py <src_dir> <strings.tsv> <out_dir> [--encoding gbk|cp932] [--selftest]
  --selftest : use the jp template as zh for every row and check that each
               rebuilt expression is token-equal to the original.
"""
import sys, os, re, csv, json, hashlib, shutil
sys.path.insert(0, os.path.dirname(__file__))
from extract import split_args, template, concat_parts, JP, LIT

csv.field_size_limit(10 ** 9)


def unesc(x):
    """Undo extract.esc: \\\\ -> \\, \\n -> newline, \\t -> tab."""
    out, i = [], 0
    while i < len(x):
        if x[i] == '\\' and i + 1 < len(x):
            out.append({'n': '\n', 't': '\t', '\\': '\\'}.get(x[i + 1], '\\' + x[i + 1]))
            i += 2
        else:
            out.append(x[i])
            i += 1
    return ''.join(out)


def hsp_lit(s):
    """Make translated text safe inside an HSP "..." literal."""
    s = re.sub(r'(?<!\\)"', r'\\"', s)          # bare quotes from a translator
    return s.replace('\r', '').replace('\n', '\\n').replace('\t', '\\t')


EMPTY = '∅'   # zh cell meaning: replace with an empty string
DATA_FILES = {'scene1.hsp', 'scene2.hsp'}   # #pack'ed story data read at runtime
TABLE = None          # table mode: {escaped text: index}; None = inline literals


def text_ref(lit):
    """An HSP expression yielding this text: a literal, or zh(N) in table mode."""
    esc = hsp_lit(lit)
    if TABLE is None:
        return '"' + esc + '"'
    if esc not in TABLE:
        TABLE[esc] = len(TABLE)
    return 'zh(%d)' % TABLE[esc]


def rebuild(tpl, args, orig_first=None):
    """zh template + original code args -> HSP expression."""
    pieces = re.split(r'(\{\{|\}\}|\{\d+\})', tpl)
    out, lit = [], ''
    for p in pieces:
        if p == '{{':
            lit += '{'
        elif p == '}}':
            lit += '}'
        elif re.fullmatch(r'\{\d+\}', p or ''):
            if lit:
                out.append(text_ref(lit))
                lit = ''
            out.append(args[int(p[1:-1])])
        else:
            lit += p
    if lit or not out:
        out.append(text_ref(lit))
    # HSP: an expression starting with a numeric value adds numerically.
    # Prefix "" unless the original started with this very same code piece.
    if not out[0].startswith(('"', 'zh(')) and out[0] != orig_first:
        out.insert(0, '""')
    return ' + '.join(out)


GBK_MAP = {'・': '·', '･': '·', '♪': '～', '｢': '「', '｣': '」'}


def gbk_safe(text):
    """Map symbols GBK lacks; half-width katakana -> full-width (NFKC)."""
    import unicodedata
    # whole runs of half-width kana, so voiced marks compose (ｶﾞ -> ガ)
    text = re.sub('[｡-ﾟ]+', lambda m: unicodedata.normalize('NFKC', m.group(0)), text)
    out = []
    for ch in text:
        ch = GBK_MAP.get(ch, ch)
        if ord(ch) > 127 and not ch.encode('gbk', errors='ignore'):
            alt = unicodedata.normalize('NFKC', ch)            # ㌧ -> トン
            alt = ''.join(c for c in alt if not unicodedata.combining(c))
            ch = alt if alt and all(c.encode('gbk', errors='ignore') for c in alt) else '?'
        out.append(ch)
    return ''.join(out)


def hsp_unescape(t):
    """HSP literal escapes -> real characters (\\n is CR LF in HSP)."""
    out, i = [], 0
    while i < len(t):
        if t[i] == '\\' and i + 1 < len(t):
            out.append({'n': '\r\n', 't': '\t', '"': '"', '\\': '\\', 'r': '\r'}.get(t[i + 1], t[i + 1]))
            i += 2
        else:
            out.append(t[i])
            i += 1
    return ''.join(out)


BIG5_MAP = {'・': '‧', '･': '‧', '♪': '～', '｢': '「', '｣': '」',
            '嘞': '咧', '獁': '瑪', '獣': '獸', '険': '險', 'С': 'C', '䴉': '鷺', '鰕': '蝦', '鱝': '魟',
            'ー': '－', '咔': '卡', '哐': '匡', '嘭': '砰', '噔': '登', '嚯': '霍', '獏': '貘', '坂': '坡',
            '蟎': '蟲', '辻': '街', '鱂': '魚', '狛': '狗', '​': ''}


def big5_safe(text, lost):
    """Characters Big5 (cp950) lacks -> nearest substitute; record what changed."""
    import unicodedata
    text = re.sub('[｡-ﾟ]+', lambda m: unicodedata.normalize('NFKC', m.group(0)), text)
    out = []
    for ch in text:
        if ord(ch) > 127 and not ch.encode('cp950', errors='ignore'):
            alt = BIG5_MAP.get(ch)
            if alt == '':
                lost[ch] = ''
                continue
            if not alt:
                alt = ''.join(c for c in unicodedata.normalize('NFKC', ch) if not unicodedata.combining(c))
            if not alt or not all(c.encode('cp950', errors='ignore') or ord(c) < 128 for c in alt):
                alt = '?'
            lost[ch] = alt
            ch = alt
        out.append(ch)
    return ''.join(out)


def norm(e):
    """Compare expressions modulo whitespace and string-only concatenation:
    "a"+"b" == "ab", and +"" in the middle/end is a no-op."""
    e = re.sub(r'\s+', '', e)
    e = re.sub(r'(?<!\\)"\+"', '', e)
    e = e.replace('+""+', '+')
    if e.endswith('+""'):
        e = e[:-3]
    return e


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    src, tsv, out = a[0], a[1], a[2]
    enc = a[a.index('--encoding') + 1] if '--encoding' in a else 'cp932'
    selftest = '--selftest' in a
    global TABLE
    table_path = a[a.index('--table') + 1] if '--table' in a else None
    if table_path:
        TABLE = {}
    rows = {}
    with open(tsv, encoding='utf-8') as fh:
        r = csv.reader(fh, delimiter='\t', quoting=csv.QUOTE_NONE)
        next(r)
        for row in r:
            rows[row[0]] = row
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(src, out)
    done = bad = 0
    problems = []
    for f in sorted(os.listdir(src)):
        if not f.endswith('.hsp'):
            continue
        if TABLE is not None and f in DATA_FILES:
            continue                  # packed runtime data, not code: translated separately
        text = open(os.path.join(src, f), 'rb').read().decode('cp932')
        edits = []
        for m in re.finditer(r'\blang\s*\(', text):
            args, _ = split_args(text, m.end())
            if not args or len(args) < 2:
                continue
            s, e = args[0]
            jp_expr = text[s:e]
            if not JP.search(jp_expr):
                continue
            rid = hashlib.md5(f'{f}:{s}:{jp_expr}'.encode('utf-8')).hexdigest()[:10]
            row = rows.get(rid)
            if row is None:
                problems.append(f'{f}:{s} no row')
                continue
            jt, ja = template(jp_expr)
            zh = unesc(row[5]) if selftest else unesc(row[8])
            if not zh:
                continue
            need = set(re.findall(r'(?<!\{)\{(\d+)\}', jt))
            have = set(re.findall(r'(?<!\{)\{(\d+)\}', zh))
            if need != have:
                bad += 1
                problems.append(f'{f}:{row[2]} placeholder mismatch jp={sorted(need)} zh={sorted(have)}')
                continue
            first = concat_parts(jp_expr)[0]
            orig_first = first[1].strip() if first[0] == 'code' else None
            new = rebuild(zh, ja, orig_first)
            if selftest and norm(new) != norm(jp_expr):
                bad += 1
                problems.append(f'{f}:{row[2]} rebuild differs\n   old {jp_expr.strip()[:120]}\n   new {new[:120]}')
                continue
            lead = jp_expr[:len(jp_expr) - len(jp_expr.lstrip())]
            trail = jp_expr[len(jp_expr.rstrip()):]
            edits.append((s, e, lead + new + trail))
            done += 1
        # direct Japanese literals (kind=lit): replace the text between the quotes
        for m in LIT.finditer(text):
            v = m.group(1)
            if not JP.search(v):
                continue
            row = rows.get(hashlib.md5(f'{f}:{m.start()}:{v}'.encode('utf-8')).hexdigest()[:10])
            if row is None or row[3] != 'lit':
                continue                      # inside lang(), skipped, or unknown
            zh = unesc(row[5]) if selftest else unesc(row[8])
            if not zh:
                continue
            if zh == EMPTY:
                edits.append((m.start(), m.end(), '""'))           # translation is "nothing"
                done += 1
                continue
            if TABLE is not None:
                edits.append((m.start(), m.end(), text_ref(zh)))   # whole "..." -> zh(N)
                done += 1
                continue
            new = hsp_lit(zh) if not selftest else zh
            if selftest and new != v:
                bad += 1
                problems.append(f'{f}:{row[2]} literal differs')
                continue
            edits.append((m.start() + 1, m.end() - 1, new))
            done += 1
        for s, e, new in sorted(edits, reverse=True):
            text = text[:s] + new + text[e:]
        if TABLE is not None and f == 'main.hsp':
            anchor = '#cmpopt varname 1'
            k = text.index(anchor) + len(anchor)
            # call first, define last: zh.hsp's variables/imports must not shift
            # the indices of any original variable (ADDT plugin relies on them)
            text = text[:k] + '\n\tzh_load\n' + text[k:].rstrip() + '\n#include "zh.hsp"\n'
        if enc.lower() in ('gbk', 'cp936'):
            text = gbk_safe(text)
        try:
            data = text.encode(enc)
        except UnicodeEncodeError as ex:
            problems.append(f'{f}: cannot encode in {enc}: {ex}')
            data = text.encode(enc, errors='replace')
        open(os.path.join(out, f), 'wb').write(data)
    if TABLE is not None:
        import struct
        shutil.copy(os.path.join(os.path.dirname(__file__), 'zh.hsp'), os.path.join(out, 'zh.hsp'))
        tenc = a[a.index('--table-encoding') + 1] if '--table-encoding' in a else 'cp932'
        entries = [t for t, _ in sorted(TABLE.items(), key=lambda kv: kv[1])]
        blob, offs, lost = bytearray(), [], {}
        for t in entries:
            v = hsp_unescape(t)
            if tenc == 'cp932':
                from sjis_map import sjis_safe
                v = sjis_safe(v, lost)
            else:
                v = big5_safe(v, lost) if tenc == 'cp950' else gbk_safe(v)
            offs.append(len(blob))
            blob += v.encode(tenc, errors='replace') + b'\0'
        offs.append(len(blob))                       # end sentinel
        os.makedirs(os.path.dirname(table_path) or '.', exist_ok=True)
        base = os.path.splitext(table_path)[0]
        open(base + '.bin', 'wb').write(bytes(blob))
        open(base + '.idx', 'wb').write(struct.pack('<%di' % (len(offs) + 1), len(entries), *offs))
        print(f'table: {len(entries)} entries, {len(blob)} bytes, {tenc} -> {base}.bin/.idx')
        if lost:
            print('  substituted:', ' '.join(f'{k}->{v}' for k, v in sorted(lost.items())))
    print(f'rewritten {done}  rejected {bad}  problems {len(problems)}')
    for p in problems[:30]:
        print('  ' + p)


if __name__ == '__main__':
    main()
