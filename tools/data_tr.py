"""Our own translation of the Custom-GX data\\*.txt / *.csv (no third-party text).

  collect : write work/data_units.txt - unique Japanese units to machine-translate
            (markup like {だ} {player} <emp1> [*] is replaced by {0} {1}... so the
            MT step protects it; it is restored on build)
  build   : write translated files (Shift-JIS) into <out dir> using work/mt/sakura.tsv

Per file:
  talk / exhelp / board / manual_JP : lines inside ",JP" sections (%..,JP .. %END)
      (manual_JP has no sections: every Japanese line). Header notes are kept.
  book      : paragraphs inside %N,JP sections are joined, translated, re-wrapped
              to 20 full-width characters; titles in %DEFINE are translated.
  name.csv  : katakana syllables transliterated with a fixed table (no MT).
  ndata.csv : every Japanese field except the last (category key) is translated.
  ndata-e.csv and anything else : copied unchanged.

Usage: python -I data_tr.py collect <cgx data dir> | build <cgx data dir> <out dir>
"""
import sys, os, re, shutil
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
JP = re.compile('[぀-ヿ一-鿿]')
TAG = re.compile(r'\{[^{}]*\}|<[a-z0-9_]+>|\[[^\]]{1,8}\]|%[A-Za-z_]+')
SECTIONED = ('talk.txt', 'exhelp.txt', 'board.txt')
BOOK_WIDTH = 20
KATA_ONLY = re.compile('^[゠-ヿー・]+$')


def protect(s):
    tags = []

    def rep(m):
        tags.append(m.group(0)); return '{%d}' % (len(tags) - 1)
    return TAG.sub(rep, s), tags


def restore(s, tags):
    return re.sub(r'\{(\d+)\}', lambda m: tags[int(m.group(1))] if int(m.group(1)) < len(tags) else m.group(0), s)


def read(d, f):
    return open(os.path.join(d, f), 'rb').read().decode('cp932').split('\r\n')


def jp_sections(lines):
    """yield (index, in_jp_section) for each line"""
    on = False
    for i, l in enumerate(lines):
        if l.startswith('%'):
            on = l.split('/')[0].rstrip().endswith(',JP')
            yield i, None
            continue
        yield i, on


def book_paragraphs(lines):
    """[(start, end_exclusive, lead, text)] for Japanese paragraphs in %N,JP sections"""
    paras, on, i = [], False, 0
    while i < len(lines):
        l = lines[i]
        if l.startswith('%'):
            on = l.rstrip().endswith(',JP') and l[1:2].isdigit()
            i += 1; continue
        if on and JP.search(l):
            j = i
            while j < len(lines) and lines[j].strip() and not lines[j].startswith('%') \
                    and not (j > i and lines[j].startswith('　')) and not lines[j].startswith('\t'):
                j += 1
            if j == i:
                j = i + 1
            lead = '　' if l.startswith('　') else ''
            paras.append((i, j, lead, ''.join(x.strip() for x in lines[i:j])))
            i = j; continue
        i += 1
    return paras


def wrap(text, width):
    out, cur, n = [], '', 0
    for ch in text:
        w = 1 if ord(ch) < 128 else 2
        if n + w > width * 2 and ch not in '。、，」』！？…）':
            out.append(cur); cur, n = '', 0
        cur += ch; n += w
    if cur:
        out.append(cur)
    return out


KANA = {'ア': '阿', 'イ': '伊', 'ウ': '烏', 'エ': '艾', 'オ': '奧', 'カ': '卡', 'キ': '基', 'ク': '庫', 'ケ': '克',
        'コ': '科', 'サ': '薩', 'シ': '希', 'ス': '斯', 'セ': '塞', 'ソ': '索', 'タ': '塔', 'チ': '奇', 'ツ': '茨',
        'テ': '特', 'ト': '托', 'ナ': '納', 'ニ': '尼', 'ヌ': '努', 'ネ': '涅', 'ノ': '諾', 'ハ': '哈', 'ヒ': '希',
        'フ': '弗', 'ヘ': '赫', 'ホ': '霍', 'マ': '瑪', 'ミ': '米', 'ム': '姆', 'メ': '梅', 'モ': '莫', 'ヤ': '亞',
        'ユ': '尤', 'ヨ': '約', 'ラ': '拉', 'リ': '里', 'ル': '魯', 'レ': '雷', 'ロ': '羅', 'ワ': '瓦', 'ヲ': '沃',
        'ン': '恩', 'ガ': '加', 'ギ': '吉', 'グ': '古', 'ゲ': '格', 'ゴ': '戈', 'ザ': '札', 'ジ': '吉', 'ズ': '茲',
        'ゼ': '澤', 'ゾ': '佐', 'ダ': '達', 'ヂ': '吉', 'ヅ': '茲', 'デ': '德', 'ド': '多', 'バ': '巴', 'ビ': '比',
        'ブ': '布', 'ベ': '貝', 'ボ': '波', 'パ': '帕', 'ピ': '皮', 'プ': '普', 'ペ': '佩', 'ポ': '波', 'ヴ': '維',
        'ァ': '亞', 'ィ': '伊', 'ゥ': '烏', 'ェ': '艾', 'ォ': '奧', 'ャ': '亞', 'ュ': '尤', 'ョ': '約', 'ッ': '',
        'ー': '', 'ヮ': '瓦'}


def translit(s):
    s = ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)   # hiragana -> katakana
    out = []
    for i, c in enumerate(s):
        if c in 'ァィゥェォャュョ' and i > 0 and s[i - 1] in KANA:
            continue                      # small vowel merges into the previous sound
        out.append(KANA.get(c, c))
    return ''.join(out)


def units(d):
    """[(file, key, protected_text, tags)] in a stable order"""
    out = []
    for f in SECTIONED:
        L = read(d, f)
        for i, on in jp_sections(L):
            if on and JP.search(L[i]):
                p, t = protect(L[i].strip()); out.append((f, i, p, t))
    L = read(d, 'manual_JP.txt')
    for i, l in enumerate(L):
        if JP.search(l):
            p, t = protect(l.strip()); out.append(('manual_JP.txt', i, p, t))
    L = read(d, 'book.txt')
    on_def = False
    for i, l in enumerate(L):
        if l.startswith('%'):
            on_def = l.startswith('%DEFINE'); continue
        if on_def and JP.search(l) and l.count(',') >= 2:
            out.append(('book.txt', ('title', i), l.split(',')[1], []))
    for a, b, lead, text in book_paragraphs(L):
        p, t = protect(text); out.append(('book.txt', ('para', a), p, t))
    L = read(d, 'ndata.csv')
    for i, l in enumerate(L):
        fs = l.split(',')
        for k, v in enumerate(fs[:-1]):
            if JP.search(v) and not KATA_ONLY.match(v):
                out.append(('ndata.csv', (i, k), v, []))
    return out


def collect(d):
    seen, lines = set(), []
    for f, k, p, t in units(d):
        if p not in seen:
            seen.add(p); lines.append(p)
    open(os.path.join(W, 'data_units.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print(f'{len(lines)} unique units -> work/data_units.txt')


def build(d, out):
    from sjis_map import sjis_safe
    mt = {}
    for line in open(os.path.join(W, 'mt', 'sakura.tsv'), encoding='utf-8'):
        k, _, v = line.rstrip('\n').partition('\t')
        if v: mt[k] = v
    hand = os.path.join(W, 'mt', 'data_hand.json')    # hand translations (lines the MT failed)
    if os.path.isfile(hand):
        import json
        mt.update(json.load(open(hand, encoding='utf-8')))
    os.makedirs(out, exist_ok=True)
    U = units(d)
    by = {}
    for f, k, p, t in U:
        by.setdefault(f, {})[k] = (p, t)
    miss, lost = {}, {}

    def tr(f, p, t):
        z = mt.get(p)
        if z is None:
            miss[f] = miss.get(f, 0) + 1
            return None
        return restore(z, t)

    def write(f, lines):
        txt = '\r\n'.join(lines)
        open(os.path.join(out, f), 'wb').write(sjis_safe(txt, lost).encode('cp932', errors='replace'))

    for f in SECTIONED + ('manual_JP.txt',):
        L = read(d, f)
        for i, (p, t) in by.get(f, {}).items():
            z = tr(f, p, t)
            if z is not None:
                lead = L[i][:len(L[i]) - len(L[i].lstrip())]
                L[i] = lead + z
        write(f, L)
    L = read(d, 'book.txt')
    paras = {a: (a, b, lead, text) for a, b, lead, text in book_paragraphs(L)}
    for key, (p, t) in by.get('book.txt', {}).items():
        if key[0] == 'title':
            i = key[1]; z = tr('book.txt', p, t)
            if z is not None:
                fs = L[i].split(','); fs[1] = z; L[i] = ','.join(fs)
    new = []
    i = 0
    while i < len(L):
        if i in paras:
            a, b, lead, text = paras[i]
            p, t = by['book.txt'][('para', a)]
            z = tr('book.txt', p, t)
            if z is None:
                new += L[a:b]
            else:
                new += wrap(lead + z.lstrip('　'), BOOK_WIDTH)
            i = b; continue
        new.append(L[i]); i += 1
    write('book.txt', new)
    L = read(d, 'name.csv')
    for i, l in enumerate(L):
        fs = l.split(',')
        if len(fs) >= 4:
            fs[0], fs[2] = translit(fs[0]), translit(fs[2]); L[i] = ','.join(fs)
    write('name.csv', L)
    L = read(d, 'ndata.csv')
    for (i, k), (p, t) in by.get('ndata.csv', {}).items():
        z = tr('ndata.csv', p, t)
        if z is not None:
            fs = L[i].split(','); fs[k] = z.replace(',', '，'); L[i] = ','.join(fs)
    for i, l in enumerate(L):
        fs = l.split(',')
        for k in range(len(fs) - 1):
            if KATA_ONLY.match(fs[k]):
                fs[k] = translit(fs[k])        # katakana loanword column: transliterate
        L[i] = ','.join(fs)
    write('ndata.csv', L)
    for f in os.listdir(d):
        if f not in SECTIONED + ('manual_JP.txt', 'book.txt', 'name.csv', 'ndata.csv') and os.path.isfile(os.path.join(d, f)):
            shutil.copy(os.path.join(d, f), os.path.join(out, f))
    print('untranslated units:', miss or 'none')
    if lost: print('substituted:', ' '.join(f'{a}->{b}' for a, b in sorted(lost.items())))


if __name__ == '__main__':
    collect(sys.argv[2]) if sys.argv[1] == 'collect' else build(sys.argv[2], sys.argv[3])
