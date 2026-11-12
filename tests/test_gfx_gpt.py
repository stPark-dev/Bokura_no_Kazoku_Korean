"""D13 GPT round trip: prepare enlarged inputs + prompts, merge only the text areas of the GPT result back."""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import gfx_gpt  # noqa: E402

KEY = gfx_gpt.KEY


def test_targets_are_icons_and_book_covers_only():
    spec = {'MENURES.XAP/sysicn06.tm2': [], 'INTERF.XAP/a_onsei.tm2': [], 'MENU.XAP/mu1.tm2': [],
            'MENU.XAP/gen0_04.tm2': [], 'MENU.XAP/kok3_11.tm2': [], 'MINIG/MINIG1.XAP/a.tm2': [],
            'TITLE.XAP/title.tm2': {'generator': 'title_logo'}}
    assert gfx_gpt.targets(spec) == ['INTERF.XAP/a_onsei.tm2', 'MENU.XAP/mu1.tm2', 'MENURES.XAP/sysicn06.tm2']


def test_flat_name_round_trip():
    assert gfx_gpt.flat('MENURES.XAP/sysicn06.tm2') == 'MENURES.XAP__sysicn06.png'
    assert gfx_gpt.unflat('MENURES.XAP__sysicn06.png') == 'MENURES.XAP/sysicn06.tm2'


def test_enlarge_fills_transparency_with_key_colour():
    im = Image.new('RGBA', (4, 2), (0, 0, 0, 0))
    im.putpixel((0, 0), (10, 20, 30, 255))
    big = gfx_gpt.enlarge(im)
    assert big.size == (4 * gfx_gpt.SCALE, 2 * gfx_gpt.SCALE) and big.mode == 'RGB'
    assert big.getpixel((big.width - 1, big.height - 1)) == KEY
    assert big.getpixel((1, 1)) == (10, 20, 30)


def test_merge_takes_only_rects_and_keys_out_magenta():
    orig = Image.new('RGBA', (20, 10), (0, 0, 255, 255))
    gpt = Image.new('RGB', (80, 40), (0, 255, 0))                  # GPT changed everything (4x)
    for x in range(8 * 4, 12 * 4):
        for y in range(2 * 4, 6 * 4):
            gpt.putpixel((x, y), KEY)                              # background inside the text area
    out = gfx_gpt.merge(orig, gpt, [[4, 2, 12, 4]], pad=0)
    assert out.size == orig.size
    assert out.getpixel((0, 0)) == (0, 0, 255, 255)                # outside the rect: original
    assert all(abs(a - b) <= 3 for a, b in zip(out.getpixel((5, 3)), (0, 255, 0, 255)))   # inside: GPT (resampled)
    assert out.getpixel((9, 3))[3] == 0                            # magenta -> transparent


def test_merge_rejects_other_aspect_ratio():
    import pytest
    with pytest.raises(ValueError):
        gfx_gpt.merge(Image.new('RGBA', (20, 10)), Image.new('RGB', (40, 40)), [[0, 0, 2, 2]])


def test_rects_book_cover_uses_bounding_box_icons_use_each_rect():
    items = [{'rect': [10, 10, 5, 5]}, {'rect': [30, 12, 4, 4]}]
    assert gfx_gpt.rects('MENU.XAP/mu1.tm2', items) == [[10, 10, 24, 6]]
    assert gfx_gpt.rects('MENURES.XAP/sysicn06.tm2', items) == [[10, 10, 5, 5], [30, 12, 4, 4]]


def test_prompt_lists_replacements():
    p = gfx_gpt.prompt('MENURES.XAP/sysicn06.tm2', [('家計簿', '가계부'), ('日記', '일기')])
    assert '家計簿 → 가계부' in p and '日記 → 일기' in p and '자홍색' in p


def _covers(n):
    out = []
    for k in range(n):
        im = Image.new('RGBA', (216, 160), (20 * k, 100, 200 - 20 * k, 255))
        out.append(im)
    return out


def test_bundle_canvas_is_3_to_2_and_cells_do_not_overlap():
    canvas, cells = gfx_gpt.bundle(_covers(6))
    assert abs(canvas.width / canvas.height - 1.5) < 0.01
    assert len(cells) == 6
    for i, a in enumerate(cells):
        x, y, w, h = a
        assert x >= 0 and y >= 0 and x + w <= canvas.width and y + h <= canvas.height
        assert abs(w / h - 216 / 160) < 0.01
        for b in cells[i + 1:]:
            assert x + w <= b[0] or b[0] + b[2] <= x or y + h <= b[1] or b[1] + b[3] <= y


def test_unbundle_returns_each_cover_from_a_result_of_another_size():
    covers = _covers(5)
    canvas, cells = gfx_gpt.bundle(covers)
    result = canvas.resize((1536, 1024), Image.LANCZOS)            # GPT answers in its own size
    parts = gfx_gpt.unbundle(result, canvas.size, cells)
    assert len(parts) == 5
    for cover, part in zip(covers, parts):
        c = part.resize(cover.size).getpixel((100, 80))
        assert all(abs(a - b) <= 6 for a, b in zip(c, cover.getpixel((100, 80))[:3]))


def test_unbundle_rejects_other_aspect_ratio():
    import pytest
    canvas, cells = gfx_gpt.bundle(_covers(6))
    with pytest.raises(ValueError):
        gfx_gpt.unbundle(Image.new('RGB', (1024, 1024)), canvas.size, cells)


def test_bundle_prompt_numbers_positions():
    p = gfx_gpt.bundle_prompt('책묶음01.png', [('あ', '가'), ('い', '나'), ('う', '다'), ('え', '라')])
    assert '1번(위 왼쪽): あ → 가' in p and '4번(아래 왼쪽): え → 라' in p and '3:2' in p


def test_merge_book_cover_keeps_original_alpha_and_removes_magenta_fringe():
    orig = Image.new('RGBA', (20, 10), (0, 0, 0, 0))
    for x in range(2, 18):
        for y in range(10):
            orig.putpixel((x, y), (200, 200, 200, 255))          # opaque cover, transparent margins
    gpt = Image.new('RGB', (80, 40), KEY)
    for x in range(8, 72):
        for y in range(40):
            gpt.putpixel((x, y), (10, 10, 200))
    out = gfx_gpt.merge(orig, gpt, [[0, 0, 20, 10]], pad=0, keep_alpha=True)
    assert out.getpixel((0, 5))[3] == 0                            # margin stays transparent
    assert out.getpixel((10, 5))[:3] == (10, 10, 200) or max(abs(a - b) for a, b in zip(out.getpixel((10, 5))[:3], (10, 10, 200))) <= 3
    edge = out.getpixel((2, 5))                                    # resampled next to magenta: no pink tint
    assert edge[3] == 255 and not (edge[0] > 120 and edge[2] > 120 and edge[1] < 80)


def test_merge_decontaminates_partly_keyed_pixels():
    mixed = tuple((a + b) // 2 for a, b in zip(KEY, (0, 0, 0)))   # half magenta, half black
    orig = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    out = gfx_gpt.merge(orig, Image.new('RGB', (4, 4), mixed), [[0, 0, 1, 1]], pad=0)
    r, g, b, a = out.getpixel((0, 0))
    assert 0 < a < 255 and max(r, g, b) <= 20


def test_take_skips_a_bad_result_and_reports_it(tmp_path, monkeypatch):
    spec = {'MENURES.XAP/sysicn06.tm2': [], 'MENURES.XAP/sysicn11.tm2': []}
    (tmp_path / '결과').mkdir()
    for n in ('MENURES.XAP__sysicn06.png', 'MENURES.XAP__sysicn11.png'):
        Image.new('RGB', (8, 4)).save(tmp_path / '결과' / n)

    def fake(read, spec, path, result, *a):
        if path.endswith('sysicn11.tm2'):
            raise ValueError('aspect ratio')
    monkeypatch.setattr(gfx_gpt, '_take_one', fake)
    monkeypatch.setattr(gfx_gpt, '_book_titles', lambda: {})
    done, failed = gfx_gpt.take(None, spec, str(tmp_path), str(tmp_path / 'imp'), str(tmp_path / 'cmp'))
    assert done == ['MENURES.XAP/sysicn06.tm2']
    assert [n for n, _ in failed] == ['MENURES.XAP__sysicn11.png']


def test_unbundle_finds_a_cover_that_gpt_moved_and_resized():
    import random
    rnd = random.Random(1)
    covers = []
    for k in range(2):
        im = Image.new('RGBA', (60, 80))
        im.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255) for _ in range(60 * 80)])
        covers.append(im.resize((120, 160), Image.NEAREST))
    canvas, cells = gfx_gpt.bundle(covers)
    x, y, w, h = cells[0]
    moved = canvas.copy()
    moved.paste((128, 128, 128), (x, y, x + w, y + h))
    piece = canvas.crop((x, y, x + w, y + h)).resize((int(w * 0.9), int(h * 0.9)), Image.LANCZOS)
    moved.paste(piece, (x + 15, y - 10 if y >= 10 else y + 5))
    part = gfx_gpt.unbundle(moved, canvas.size, cells, ref=canvas)[0]
    a = part.resize((60, 80), Image.LANCZOS).convert('RGB')
    b = covers[0].resize((60, 80), Image.LANCZOS).convert('RGB')
    diff = sum(abs(p - q) for u, v in zip(a.getdata(), b.getdata()) for p, q in zip(u, v)) / (60 * 80 * 3)
    assert diff < 25


def test_take_areas_cover_takes_whole_image_icons_take_rects():
    items = [{'rect': [10, 10, 5, 5]}]
    assert gfx_gpt.take_areas('MENU.XAP/mu1.tm2', items, (108, 128)) == [[0, 0, 108, 128]]
    assert gfx_gpt.take_areas('MENURES.XAP/sysicn06.tm2', items, (240, 176)) == [[10, 10, 5, 5]]


def test_unbundle_keeps_the_grid_cell_when_the_cover_cannot_be_found():
    import random
    rnd = random.Random(2)
    im = Image.new('RGBA', (40, 30))
    im.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255) for _ in range(40 * 30)])
    canvas, cells = gfx_gpt.bundle([im.resize((160, 120), Image.NEAREST)])
    other = Image.new('RGB', canvas.size)
    other.putdata([(rnd.randrange(256),) * 3 for _ in range(canvas.width * canvas.height)])
    assert gfx_gpt._locate(other, canvas, cells[0]) == tuple(cells[0])


def test_guide_boxes_copied_by_gpt_are_detected():
    orig = Image.new('RGBA', (20, 10), (0, 0, 0, 0))
    clean = gfx_gpt.enlarge(orig)
    boxed = gfx_gpt._guide(orig, [[2, 2, 10, 6]])
    assert not gfx_gpt.has_guide_box(clean, orig.size, [[2, 2, 10, 6]])
    assert gfx_gpt.has_guide_box(boxed.resize((200, 100)), orig.size, [[2, 2, 10, 6]])


def test_guide_box_moved_elsewhere_is_still_detected():
    from PIL import ImageDraw
    im = Image.new('RGB', (200, 100), KEY)
    ImageDraw.Draw(im).rectangle((3, 3, 196, 80), outline=(250, 10, 10), width=4)
    assert gfx_gpt.has_guide_box(im, (20, 10), [[5, 3, 4, 4]])
