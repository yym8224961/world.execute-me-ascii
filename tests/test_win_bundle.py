"""Check the built Windows single-file player runs outside the project directory."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT/'dist/world-execute-mv-win.pyz'


@unittest.skipUnless(sys.platform == 'win32', 'Windows only')
class WindowsBundleTests(unittest.TestCase):
    def test_embedded_resources_match_manifest(self):
        with zipfile.ZipFile(BUNDLE) as archive:
            manifest = json.loads(archive.read('bundle-manifest.json'))
            self.assertEqual(manifest['platform'], 'Windows 10/11')
            self.assertIn('media/song.mp3', manifest['files'])
            self.assertNotIn('audio-clock', manifest['files'])
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
            for name in ('player.py', 'player_win.py', 'scenes.py', 'config.json'):
                self.assertEqual(archive.read(name), (ROOT/name).read_bytes())
            config = json.loads(archive.read('config.json'))
            self.assertEqual(config['audio'], 'media/song.mp3')

    def test_runs_from_an_empty_directory_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            work = base/'unrelated working directory'
            work.mkdir()
            scratch = base/'scratch'
            scratch.mkdir()
            # Reproduce a plain `python file.pyz` launch: no UTF-8 mode or
            # Python-specific environment from the developer's shell.
            env = {key: value for key, value in os.environ.items()
                   if key not in ('PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONPATH')}
            env.update(TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch))
            for t, expected, chinese in [(67.3, 'If I can make you happy', '如果我能让你快乐'),
                                         (124.2, 'Then maybe', None),
                                         (159.85, 'TROIS', None),
                                         (183.2, 'Question me', None)]:
                result = subprocess.run([sys.executable, str(BUNDLE), '--snapshot', str(t),
                                         '--plain', '--width', '125', '--height', '45'],
                                        cwd=work, env=env, capture_output=True, text=True,
                                        encoding='utf-8', check=True)
                self.assertIn(expected, result.stdout)
                if chinese:
                    self.assertIn(chinese, result.stdout)
                self.assertEqual(list(work.iterdir()), [])
                self.assertEqual(list(scratch.iterdir()), [])

    def test_corrupt_resource_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder)/'corrupt.pyz'
            with zipfile.ZipFile(BUNDLE) as original, zipfile.ZipFile(bad, 'w') as changed:
                for name in original.namelist():
                    data = original.read(name)
                    changed.writestr(name, b'{}' if name == 'config.json' else data)
            result = subprocess.run([sys.executable, str(bad), '--snapshot', '67.3', '--plain'],
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('资源校验失败', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
