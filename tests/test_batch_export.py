import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import batch_export  # noqa: E402

SRC = [{'id': 'EVENT/m00h0a.mes/a', 'file': 'm00h0a.mes', 'head': 'a', 'src': 'x', 'sha1': '1'},
       {'id': 'EVENT/m01h0a.mes/b', 'file': 'm01h0a.mes', 'head': 'b', 'src': 'y', 'sha1': '2'},
       {'id': 'EVENT/g00h0a.mes/c', 'file': 'g00h0a.mes', 'head': 'c', 'src': 'z', 'sha1': '3'}]


def test_export_filters_by_glob_and_skips_translated():
    rows = batch_export.export(SRC, [{'id': 'EVENT/m00h0a.mes/a'}], 'm*')
    assert rows == [{'id': 'EVENT/m01h0a.mes/b', 'head': 'b', 'src': 'y'}]
