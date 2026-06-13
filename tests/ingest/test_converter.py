from __future__ import annotations

import ipaddress
import socket
from pathlib import Path

import pytest

from src.ingest import converter


def _write_pdf(path: Path, text: str) -> None:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length "
            + str(len(f"BT /F1 24 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii"))).encode("ascii")
            + b" >>\nstream\n"
            + f"BT /F1 24 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
            + b"\nendstream"
        ),
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_at = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(out))


def _block_non_loopback(monkeypatch):
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo
    seen: list[tuple[str, object]] = []

    def is_loopback(host: str) -> bool:
        if host.lower() in {"localhost", "127.0.0.1", "::1"}:
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def guarded_connect(self, address):
        seen.append(("connect", address))
        host = address[0] if isinstance(address, tuple) else str(address)
        if not is_loopback(str(host)):
            raise AssertionError(f"non-loopback connect attempted: {address}")
        return original_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        seen.append(("getaddrinfo", host))
        if host is not None and not is_loopback(str(host)):
            raise AssertionError(f"non-loopback DNS attempted: {host}")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    return seen


def test_pdf_converts_local(tmp_path, monkeypatch):
    seen = _block_non_loopback(monkeypatch)
    pdf = tmp_path / "local.pdf"
    _write_pdf(pdf, "Synthetic PDF Local Conversion")

    md = converter.to_markdown(pdf)

    assert md.startswith("---\ntier: S3\n---")
    assert "Synthetic PDF Local Conversion" in md
    non_loopback = [peer for kind, peer in seen if kind in {"connect", "getaddrinfo"}]
    assert not non_loopback


def test_txt_converts_plain_read(tmp_path, monkeypatch):
    seen = _block_non_loopback(monkeypatch)
    txt = tmp_path / "note.txt"
    txt.write_text("Plain text drop-in note.\nSecond line.", encoding="utf-8")

    md = converter.to_markdown(txt)

    assert md.startswith("---\ntier: S3\n---")
    assert "Plain text drop-in note." in md
    assert "Second line." in md
    non_loopback = [peer for kind, peer in seen if kind in {"connect", "getaddrinfo"}]
    assert not non_loopback


def test_unsupported_raises(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"synthetic")

    with pytest.raises(ValueError, match="Unsupported: .mp4"):
        converter.to_markdown(media)


def test_tier_frontmatter_default_s3(tmp_path):
    src = tmp_path / "numbers.csv"
    src.write_text("amount\n123\n", encoding="utf-8")

    assert converter.to_markdown(src).startswith("---\ntier: S3")


def test_tier_frontmatter_explicit(tmp_path):
    src = tmp_path / "public.csv"
    src.write_text("ticker\nABC\n", encoding="utf-8")

    assert converter.to_markdown(src, tier="S1").startswith("---\ntier: S1")


def test_no_overwrite(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "statement.csv"
    src.write_text("metric,value\nrevenue,42\n", encoding="utf-8")

    converter.convert_to_vault(src, inbox)
    with pytest.raises(FileExistsError, match="Delete manually to re-convert"):
        converter.convert_to_vault(src, inbox)


def test_no_cloud_features():
    assert converter._md.llm_client is None
    assert converter._md.enable_plugins is False
    assert getattr(converter._md, "_llm_client", None) is None
    assert getattr(converter._md, "_plugins_enabled", False) is False

