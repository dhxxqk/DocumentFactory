"""Private atomic output primitives shared by formatting pipelines.

Writing a new DOCX is itself a deterministic operation: unchanged ZIP parts
are copied byte for byte, changed XML parts are serialized from the in-memory
document model, and every output lands via a temp file plus os.replace so a
partial result can never be observed.
"""
from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


def write_package(source, destination, document, changed_parts):
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{destination.stem}_", suffix=".tmp", dir=destination.parent)
    os.close(handle)
    temp = Path(temp_name)
    try:
        if not changed_parts:
            temp.write_bytes(source.read_bytes())
        else:
            with zipfile.ZipFile(source, "r") as incoming, zipfile.ZipFile(temp, "w") as outgoing:
                for info in incoming.infolist():
                    payload = incoming.read(info.filename)
                    if info.filename in changed_parts:
                        payload = etree.tostring(document.parts[info.filename], encoding="UTF-8", xml_declaration=True)
                    outgoing.writestr(info, payload)
        os.replace(temp, destination)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.stem}_", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temp = Path(temp_name)
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
