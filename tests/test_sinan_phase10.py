from __future__ import annotations

import struct

import pytest

from nascente_brasil.validation.sinan_phase10 import FIELDS, _layout


def test_sinan_layout_rejects_wrong_header(tmp_path):
    path = tmp_path / "source.dbc"
    path.write_bytes(b"not a DBC")
    with pytest.raises(ValueError, match="Invalid SINAN DBC header"):
        _layout(path)


def test_sinan_layout_rejects_drift(tmp_path):
    path = tmp_path / "source.dbc"
    header = bytearray(32 + 32 + 1)
    header[0] = 3
    header[4:8] = struct.pack("<I", 89_934)
    header[8:10] = struct.pack("<H", len(header))
    header[-1] = 13
    header[32:36] = b"WRNG"
    path.write_bytes(header)
    with pytest.raises(ValueError, match="layout or volume differs"):
        _layout(path)


def test_sinan_has_ordered_schema():
    assert len(FIELDS) == 32
    assert FIELDS[-1] == "CLASSI_FIN"
