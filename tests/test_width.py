"""Horizontal text width (D12): a translated line must not be wider than the source line."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import width  # noqa: E402


def test_cells_count_wide_one_ascii_half_codes_zero():
    assert width.cells('가나') == 2
    assert width.cells('가 나') == 2.5
    assert width.cells('@s18@r115@g115@b115가') == 1
    assert width.cells('%s@0가') == 1
    assert width.cells('ＡＢ12') == 3


def test_lines_split_on_break_code():
    assert width.lines('@s18게임을@n　계속할까요？') == [3, 7]


def test_text_part_drops_shared_prefix_and_suffix():
    src = 'comment,  34, 369, left, "子供の様子や写真などを見る"'
    ko = 'comment,  34, 369, left, "아이들의 모습이나 사진 등을 본다"'
    assert width.text_part(src, ko) == ('子供の様子や写真などを見る', '아이들의 모습이나 사진 등을 본다')


def test_check_reports_wider_line_and_extra_lines():
    assert width.check('082\t@s18ゲームを@n　続けますか？', '082\t@s18게임을@n　계속할까요？') == []
    errs = width.check('082\t@s18ゲームを@n　続けますか？', '082\t@s18게임을@n　계속하겠습니까？')
    assert errs and '8' in errs[0]
    assert width.check('"あいう"', '"가@n나"')        # more lines than the source
    assert width.check('"%sあいう"', '"%s가나다"') == []
