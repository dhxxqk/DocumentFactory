from pathlib import Path
from .models import DocumentFactoryError


def checked_output(path, root, category, source=None):
    root = Path(root).resolve()
    allowed = (root / category).resolve()
    if not allowed.is_relative_to(root):
        raise DocumentFactoryError(f"输出目录符号链接越界：{allowed}")
    path = Path(path).resolve()
    if not path.is_relative_to(allowed):
        raise DocumentFactoryError(f"所有生成文件必须位于 {allowed} 内：{path}")
    if source is not None and path == Path(source).resolve():
        raise DocumentFactoryError("输出路径不得覆盖输入文件")
    return path
