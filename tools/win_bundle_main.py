"""Windows single-file entry point: verify bundled resources, then run the player."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import runpy
import sys
import tempfile
import zipfile


def main():
    if sys.platform != 'win32':
        raise SystemExit('这个单文件播放器是 Windows 版；macOS 请使用 world-execute-mv.pyz。')
    if sys.version_info < (3, 9):
        raise SystemExit('需要 Python 3.9 或更新版本。')
    # Console output is UTF-16 on its own, but redirected output would otherwise
    # fall back to the ANSI code page (GBK on Chinese Windows).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    archive = Path(sys.argv[0]).resolve()
    sys.dont_write_bytecode = True
    with tempfile.TemporaryDirectory(prefix='world-execute-mv-') as directory:
        root = Path(directory)
        with zipfile.ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read('bundle-manifest.json'))
            for name, digest in manifest['files'].items():
                relative = PurePosixPath(name)
                if relative.is_absolute() or '..' in relative.parts:
                    raise SystemExit('程序包资源路径无效。')
                data = bundle.read(name)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise SystemExit('程序包资源校验失败：' + name)
                target = root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        sys.path.insert(0, str(root))
        sys.argv[0] = str(root/'player_win.py')
        runpy.run_path(str(root/'player_win.py'), run_name='__main__')


if __name__ == '__main__':
    main()
