"""跨平台文本文件读写辅助。"""

from pathlib import Path

UTF8_READ_ENCODING = "utf-8-sig"
UTF8_WRITE_ENCODING = "utf-8"


def read_text(path: str | Path) -> str:
    """以 UTF-8（兼容 BOM）读取文本文件。"""
    return Path(path).read_text(encoding=UTF8_READ_ENCODING)


def write_text(path: str | Path, content: str) -> None:
    """以 UTF-8 写入文本文件。"""
    Path(path).write_text(content, encoding=UTF8_WRITE_ENCODING)
