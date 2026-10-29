"""Extract translatable Japanese text from Custom-GX HSP source.

Every lang(JP, EN) call becomes one row. The JP argument is turned into a
template: string literals are kept as text, any non-literal piece of the
concatenation becomes {0}, {1}, ... so the translator sees whole sentences.

Output: strings.tsv  (UTF-8, tab separated)
  id  file  line  jp_template  en_template  jp_args(json)  zh
Japanese literals that are NOT inside lang() are listed in loose.tsv for review.

Usage: python -I extract.py <src_dir> <out_dir>
"""
import sys, os, re, json, hashlib

JP = re.compile('[\u3040-\u30ff\u4e00-\u9fff\uff66-\uff9d]')   # incl. half-width katakana


def split_args(s, i):
    """s[i] is just after 'lang('. Return (args[(start,end)], close_index)."""
    depth, args, start, j, n = 0, [], i, i, len(s)
    while j < n:
        c = s[j]
        if c == '"':
            j += 1
            while j < n and s[j] != '"':
                if s[j] == '\\':
                    j += 1
                j += 1
        elif c == '{' and j + 1 < n and s[j + 1] == '"':      # {" multi-line "}
            k = s.find('"}', j + 2)
            j = k + 1 if k >= 0 else n
        elif c == '(':
            depth += 1
        elif c == ')':
            if depth == 0:
                args.append((start, j))
                return args, j
            depth -= 1
        elif c == ',' and depth == 0:
            args.append((start, j))
            start = j + 1
        elif c == ';' and depth == 0 and s.rfind('\n', 0, j) >= s.rfind('"', 0, j):
            pass
        j += 1
    return None, n


def concat_parts(expr):
    """Split an HSP expression on top-level '+' into literal / code parts."""
    parts, depth, cur, j, n = [], 0, '', 0, len(expr)
    while j < n:
        c = expr[j]
        if c == '"':
            k = j + 1
            while k < n and expr[k] != '"':
                if expr[k] == '\\':
                    k += 1
                k += 1
            cur += expr[j:k + 1]
            j = k + 1
            continue
        if c in '([':
            depth += 1
        elif c in ')]':
            depth -= 1
        if c == '+' and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += c
        j += 1
    parts.append(cur)
    out = []
    for p in parts:
        t = p.strip()
        if len(t) >= 2 and t[0] == '"' and t[-1] == '"' and t.count('"') == 2 + t.count('\\"'):
            out.append(('lit', t[1:-1]))
        else:
            out.append(('code', t))
    return out


def template(expr):
    parts = concat_parts(expr)
    tpl, args = '', []
    for kind, v in parts:
        if kind == 'lit':
            tpl += v.replace('{', '{{').replace('}', '}}')
        else:
            tpl += '{%d}' % len(args)
            args.append(v)
    return tpl, args


LIT = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
# literals that the game stores as data and compares later (gender etc.): never replace
KEY_LITERALS = {'男性', '女性', 'なし', '両性具有', '自称男性', '自称女性'}
# body-part layouts: chara.hsp *set_figure reads them 3 bytes at a time and compares
# each piece with "頭" "首"... - they must stay Japanese, byte for byte
BODY_PARTS = re.compile(r'^(?:[頭首体背手指腕腰足]\|)+$')


def is_key(text):
    return text.strip() in KEY_LITERALS or bool(BODY_PARTS.match(text.strip()))


def line_ctx(text, pos):
    """What the text on this line is given to: 'description', 'txt', 'cdatan(CDATAN_NAME,rc)'..."""
    ls = text.rfind('\n', 0, pos) + 1
    head = text[ls:pos].strip()
    m = re.match(r'([A-Za-z_][\w@]*(?:\s*\([^=]*?\))?)\s*(?:\+?=)', head)
    if m:
        return re.sub(r'\s+', '', m.group(1))
    m = re.match(r'([A-Za-z_][\w@]*)', head)
    return m.group(1) if m else ''


def comment_start(text, ls):
    """Index where a ';' or '//' comment starts on the line beginning at ls, or -1."""
    i, n, inq = ls, len(text), False
    while i < n and text[i] != '\n':
        c = text[i]
        if inq:
            if c == '\\':
                i += 1
            elif c == '"':
                inq = False
        elif c == '"':
            inq = True
        elif c == ';' or text.startswith('//', i):
            return i
        i += 1
    return -1


def main(src, out):
    """kind: lang = JP argument of lang(JP, EN); lit = Japanese string literal
    used directly (item names, descriptions, lists...).  Excluded and listed
    in skipped.tsv: literals compared with ==/!= (logic keys), Japanese
    speech-tone tables (locvar__yoro*), literals inside comments."""
    os.makedirs(out, exist_ok=True)
    rows, skipped = [], []
    for f in sorted(os.listdir(src)):
        if not f.endswith('.hsp'):
            continue
        text = open(os.path.join(src, f), 'rb').read().decode('cp932')
        covered = []
        for m in re.finditer(r'\blang\s*\(', text):
            args, close = split_args(text, m.end())
            if not args or len(args) < 2:
                continue
            jp_expr = text[args[0][0]:args[0][1]]
            if not JP.search(jp_expr):
                continue
            en_expr = text[args[1][0]:args[1][1]]
            jt, ja = template(jp_expr)
            et, _ = template(en_expr)
            line = text.count('\n', 0, m.start()) + 1
            if not ja and is_key(jt):
                covered.append((args[0][0], args[0][1]))
                continue                      # data key (gender, body parts): keep Japanese
            rid = hashlib.md5(f'{f}:{args[0][0]}:{jp_expr}'.encode('utf-8')).hexdigest()[:10]
            rows.append([rid, f, str(line), 'lang', line_ctx(text, m.start()), jt, et,
                         json.dumps(ja, ensure_ascii=False), ''])
            covered.append((args[0][0], args[0][1]))
        for m in LIT.finditer(text):
            v = m.group(1)
            if not JP.search(v) or any(a <= m.start() < b for a, b in covered):
                continue
            line = text.count('\n', 0, m.start()) + 1
            ls = text.rfind('\n', 0, m.start()) + 1
            cs = comment_start(text, ls)
            before = text[ls:m.start()].rstrip()
            after = text[m.end():m.end() + 4].lstrip()
            ctx = line_ctx(text, m.start())
            why = None
            if cs != -1 and cs < m.start():
                why = 'comment'
            elif before.endswith(('==', '!=')) or after.startswith(('==', '!=')):
                why = 'compare'
            elif ctx in ('case', 'font') or re.search(r'\binstr\s*\(', before):
                why = 'compare'                       # case labels, instr() keys, font names
            elif is_key(v):
                why = 'key-value'                     # stored and compared elsewhere
            if why:
                skipped.append([f, str(line), why, ctx, v])
                continue
            rid = hashlib.md5(f'{f}:{m.start()}:{v}'.encode('utf-8')).hexdigest()[:10]
            rows.append([rid, f, str(line), 'lit', ctx, v, '', '[]', ''])
    loose = skipped

    def esc(x):
        # backslash first, so HSP escapes like \n (two chars) survive as \\n
        return x.replace('\\', '\\\\').replace('\t', '\\t').replace('\r', '').replace('\n', '\\n')

    with open(os.path.join(out, 'strings.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('id\tfile\tline\tkind\tctx\tjp\ten\tjp_args\tzh\n')
        for r in rows:
            w.write('\t'.join(esc(x) for x in r) + '\n')
    with open(os.path.join(out, 'skipped.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('file\tline\twhy\tctx\tjp\n')
        for r in loose:
            w.write('\t'.join(esc(x) for x in r) + '\n')
    by = lambda k: [r for r in rows if r[3] == k]
    for k in ('lang', 'lit'):
        rs = by(k)
        print(f'{k}: rows {len(rs)}  unique {len({r[5] for r in rs})}  chars {sum(len(r[5]) for r in rs)}')
    from collections import Counter
    print('skipped:', dict(Counter(r[2] for r in loose)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
