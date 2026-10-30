"""Build the Windows single-file player and its download zip.

Code and resources come from this repository; the music is taken from the macOS
release bundle (world-execute-mv.pyz) when it exists, so both builds ship the
same audio.  No stale copy of player.py is ever bundled.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import zipapp
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_BUNDLE = ROOT/'world-execute-mv.pyz'
LOCAL_FILES = ('player.py', 'scenes.py', 'player_win.py', 'config.json', 'lyrics.json',
               'spectrum.json')


def assets():
    found = {}
    for name in LOCAL_FILES:
        path = ROOT/name
        if not path.is_file():
            raise SystemExit(f'缺少文件：{name}')
        found[name] = path.read_bytes()
    song = ROOT/'media/song.mp3'
    if SOURCE_BUNDLE.is_file():
        with zipfile.ZipFile(SOURCE_BUNDLE) as bundle:
            found['media/song.mp3'] = bundle.read('media/song.mp3')
    elif song.is_file():
        found['media/song.mp3'] = song.read_bytes()
    else:
        raise SystemExit('缺少音频：请放入 media/song.mp3，或提供 macOS 发布包 world-execute-mv.pyz')
    return found


def main():
    files = assets()
    output = ROOT/'dist'
    output.mkdir(exist_ok=True)
    (ROOT/'.build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='win-bundle-', dir=ROOT/'.build') as folder:
        stage = Path(folder)
        for name, data in files.items():
            target = stage/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (stage/'__main__.py').write_bytes((ROOT/'tools/win_bundle_main.py').read_bytes())
        manifest = {'format': 1, 'platform': 'Windows 10/11', 'python': '3.9+',
                    'files': {name: hashlib.sha256(data).hexdigest()
                              for name, data in files.items()}}
        (stage/'bundle-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        package = output/'world-execute-mv-win.pyz'
        # No shebang: Windows launches it as `python file.pyz` (or via run.cmd).
        zipapp.create_archive(stage, package, interpreter=None, compressed=True)

    bundle_dir = 'world-execute-mv-win'
    download = output/'world-execute-mv-windows.zip'
    with zipfile.ZipFile(download, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(package, f'{bundle_dir}/world-execute-mv-win.pyz')
        archive.write(ROOT/'tools/windows/run.cmd', f'{bundle_dir}/run.cmd')
        archive.write(ROOT/'README-Windows.md', f'{bundle_dir}/README-Windows.md')

    artifacts = [package, download]
    (output/'SHA256SUMS-win.txt').write_text(
        ''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n'
                for path in artifacts))
    print(json.dumps({'artifacts': [str(path) for path in artifacts], 'embedded_audio': True},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
