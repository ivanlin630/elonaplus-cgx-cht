"""Source patches applied to the translated tree (never to src/).

1. highdpi.hsp: after every font change, if the system code page is not
   Japanese (932), re-create the same font with DEFAULT_CHARSET and a
   Chinese face, so GDI decodes our Big5/GBK bytes with the system code page
   instead of Shift-JIS. Fonts are cached by height/weight/italic.

Usage: python -I patch_src.py <tree>
"""
import sys, os

FONT_HELPERS = ''


ANCHOR_FUNC = '#undef font'
ANCHOR_CALL = '\tfont@HSP fontname, _p1, _p2\n'


def main(tree):
    p = os.path.join(tree, 'highdpi.hsp')
    t = open(p, 'rb').read().decode('cp932').replace('\r\n', '\n')
    if 'zh_fontfix' in t:
        print('highdpi.hsp already patched'); return
    assert t.count(ANCHOR_CALL) == 1, 'anchors not found'
    # only a call: the function itself lives in zh.hsp at the end of the program,
    # so no variable or DLL import is added in front of the original ones
    t = t.replace(ANCHOR_CALL, ANCHOR_CALL + '\tzh_fontfix\n', 1)
    open(p, 'wb').write(t.replace('\n', '\r\n').encode('cp932'))
    print('highdpi.hsp patched: font follows system code page')


def patch_sound(tree):
    """sound.hsp sndstop: 'mmstop cnt' needs HSP >= 3.5 (channel argument); under
    HSP 3.4 it throws error 16 'too many parameters' whenever sound mode is 2
    (MCI) - e.g. every time a conversation ends. HSP 3.4 cannot stop a single
    MCI channel and a bare 'mmstop' would also stop the music, so do nothing."""
    p = os.path.join(tree, 'sound.hsp')
    t = open(p, 'rb').read().decode('cp932')
    old = '			mmstop cnt'
    if old not in t:
        print('sound.hsp: nothing to patch'); return
    assert t.count(old) == 1
    t = t.replace(old, '			; mmstop cnt  -- needs HSP 3.5+, error 16 under 3.4 (zh patch)')
    open(p, 'wb').write(t.encode('cp932'))
    print('sound.hsp patched: sndstop no longer calls mmstop with a channel')


if __name__ == '__main__':
    # font patch (main) is not needed with Shift-JIS text: HSP's own Japanese
    # font charset decodes it correctly on any system locale
    patch_sound(sys.argv[1])
