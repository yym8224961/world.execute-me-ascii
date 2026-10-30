#!/usr/bin/env python3
"""Windows terminal player for world.execute(me);.

The macOS build (player.py + the Swift audio-clock helper) stays untouched.
This module only replaces the platform layer and reuses the shared renderer:

  * player.Film / scenes.py : unchanged
  * terminal                : Win32 console mode + msvcrt + ANSI/VT output
  * audio timeline          : Windows MCI (winmm.dll), no extra install

Source checkout:  python player_win.py [--start 158.7 --autoplay]
Single file:      python world-execute-mv-win.pyz
Headless render:  python player_win.py --snapshot 67.3 --plain
"""
from __future__ import annotations

import argparse
import bisect
import ctypes
import json
import msvcrt
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_posix_stubs():
    """player.py imports termios/tty at module level; stub them on Windows."""
    if os.name != 'nt':
        return
    if 'termios' not in sys.modules:
        shell = types.ModuleType('termios')
        shell.TCSADRAIN = 0
        shell.tcgetattr = lambda fd: None
        shell.tcsetattr = lambda fd, when, attrs: None
        sys.modules['termios'] = shell
    if 'tty' not in sys.modules:
        shell = types.ModuleType('tty')
        shell.setcbreak = lambda fd: None
        sys.modules['tty'] = shell


_install_posix_stubs()
import player  # noqa: E402  (needs the stubs installed first)

# --------------------------------------------------------------------------- #
# Windows console
# --------------------------------------------------------------------------- #
ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080


class Console:
    """Minimal Win32 console wrapper: VT output, alternate screen, raw keys."""

    def __init__(self):
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self._kernel32 = kernel32
        self._out = kernel32.GetStdHandle(-11)
        self._in = kernel32.GetStdHandle(-10)
        self._old_out = wintypes.DWORD()
        self._old_in = wintypes.DWORD()
        if not kernel32.GetConsoleMode(self._out, ctypes.byref(self._old_out)):
            raise RuntimeError('需要真实的 Windows 控制台：请在 Windows Terminal 或 PowerShell 窗口中运行。')
        kernel32.GetConsoleMode(self._in, ctypes.byref(self._old_in))
        # Alternate screen buffer needs VT sequences; QuickEdit would freeze output
        # whenever the user clicks in the window, so it goes away while playing.
        kernel32.SetConsoleMode(self._out, self._old_out.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
        kernel32.SetConsoleMode(self._in,
                                (self._old_in.value | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE)
        self.active = False

    def size(self):
        try:
            size = shutil.get_terminal_size()
            return max(20, size.columns), max(10, size.lines)
        except OSError:
            return 100, 36

    def write(self, text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def enter(self):
        self.write('\x1b]0;world.execute(me);\x07\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J')
        self.active = True

    def leave(self):
        if not self.active:
            return
        self.active = False
        try:
            self.write('\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l')
        finally:
            self._kernel32.SetConsoleMode(self._out, self._old_out.value)
            self._kernel32.SetConsoleMode(self._in, self._old_in.value)


ARROWS = {'K': '\x1b[D', 'M': '\x1b[C'}


def read_keys(timeout):
    """Wait up to timeout seconds, returning whatever keys were typed.

    Left/right arrows become the same ESC [ C / ESC [ D sequences player.py
    expects.  Other arrows and function keys are dropped so that a stray ESC
    byte can never be mistaken for "quit".
    """
    buffered = ''
    deadline = time.monotonic() + timeout
    while True:
        while msvcrt.kbhit():
            key = msvcrt.getwch()
            if key in ('\x00', '\xe0'):
                code = msvcrt.getwch()
                buffered += ARROWS.get(code, '')
            elif key == '\x03':
                raise KeyboardInterrupt
            else:
                buffered += key
        if buffered or time.monotonic() >= deadline:
            return buffered
        time.sleep(0.004)


# --------------------------------------------------------------------------- #
# Audio: Windows MCI drives the clock, exactly like the AVFoundation helper does
# on macOS.  The device position is the timeline; the terminal only consumes it.
# --------------------------------------------------------------------------- #
_winmm = ctypes.WinDLL('winmm', use_last_error=True)
_winmm.mciSendStringW.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HWND)
_winmm.mciSendStringW.restype = wintypes.UINT
_winmm.mciGetErrorStringW.argtypes = (wintypes.UINT, wintypes.LPWSTR, wintypes.UINT)
_winmm.mciGetErrorStringW.restype = wintypes.BOOL


def _mci(command):
    buffer = ctypes.create_unicode_buffer(512)
    code = _winmm.mciSendStringW(command, buffer, 512, None)
    if code:
        text = ctypes.create_unicode_buffer(256)
        _winmm.mciGetErrorStringW(code, text, 256)
        raise RuntimeError(f'{text.value}（MCI 命令：{command}）')
    return buffer.value.strip()


def _mci_seconds(command):
    value = _mci(command)
    return int(value) / 1000.0 if value else 0.0


def _find_ffmpeg():
    """Locate ffmpeg; decoding to WAV is the reliable audio path (see below)."""
    found = shutil.which('ffmpeg')
    if found:
        return found
    candidates = [
        Path(os.environ.get('ProgramFiles', r'C:\Program Files'))/'ffmpeg'/'bin'/'ffmpeg.exe',
        Path(os.environ.get('LOCALAPPDATA', ''))/'Microsoft'/'WinGet'/'Links'/'ffmpeg.exe',
        ROOT/'tools'/'ffmpeg.exe',
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def prepare_audio(path):
    """Return (file_to_play, temp_dir_to_clean, MCI device type).

    MCI's mpegvideo device hands MP3 playback to DirectShow, which may pick an
    audio endpoint of its own (on some machines the HDMI monitor) instead of the
    system default.  waveOut follows the default device, so MP3 is decoded to a
    temporary WAV first when ffmpeg is available; otherwise the original file is
    played by mpegvideo as before.
    """
    if path.suffix.lower() == '.wav':
        return path, None, 'waveaudio'
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return path, None, 'mpegvideo'
    folder = Path(tempfile.mkdtemp(prefix='world-execute-mv-audio-'))
    wav = folder/'audio.wav'
    try:
        result = subprocess.run(
            [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(path),
             '-vn', '-ac', '2', '-ar', '44100', '-f', 'wav', str(wav)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode == 0 and wav.is_file() and wav.stat().st_size > 44:
            return wav, folder, 'waveaudio'
    except OSError:
        pass
    shutil.rmtree(folder, ignore_errors=True)
    return path, None, 'mpegvideo'


class MciAudio:
    """Audio device owns the timeline, as the AVFoundation helper does on macOS."""

    def __init__(self, path, volume=0.75, device='mpegvideo', cleanup=None):
        self.alias = f'wem{os.getpid()}'
        self.path = str(path)
        self.volume = volume
        self._cleanup = cleanup
        try:
            _mci(f'open "{self.path}" type {device} alias {self.alias}')
        except RuntimeError as error:
            self.close()
            raise RuntimeError(f'无法打开音频：{self.path}\n{error}') from error
        try:
            _mci(f'set {self.alias} time format milliseconds')
            self.duration = _mci_seconds(f'status {self.alias} length')
        except RuntimeError as error:
            self.close()
            raise RuntimeError(f'无法读取音频时长：{error}') from error
        if self.duration <= 0:
            self.close()
            raise RuntimeError(f'无法读取音频时长：{self.path}\n请用 --audio 指定其它音频文件。')
        self.set_volume(volume)

    def _mode(self):
        return _mci(f'status {self.alias} mode').lower()

    def state(self):
        return {'time': _mci_seconds(f'status {self.alias} position'),
                'duration': self.duration,
                'playing': self._mode() == 'playing'}

    def play(self):
        _mci(f'play {self.alias}')

    def pause(self):
        _mci(f'pause {self.alias}')

    def seek(self, seconds):
        seconds = min(max(0.0, seconds), max(0.0, self.duration - 0.05))
        playing = self._mode() == 'playing'
        _mci(f'seek {self.alias} to {int(round(seconds * 1000))}')
        if playing:
            # MCI stops the device when seeking; resume from the new position.
            _mci(f'play {self.alias}')

    def set_volume(self, value):
        self.volume = min(1.0, max(0.0, value))
        try:
            _mci(f'setaudio {self.alias} volume to {int(round(self.volume * 1000))}')
        except RuntimeError:
            pass  # not every MCI device exposes volume control

    def close(self):
        for command in (f'stop {self.alias}', f'close {self.alias}'):
            try:
                _mci(command)
            except RuntimeError:
                pass
        if self._cleanup:
            shutil.rmtree(self._cleanup, ignore_errors=True)
            self._cleanup = None


class SilentClock:
    """Wall-clock stand-in used by --silent (no audio device / recording)."""

    def __init__(self, duration):
        self.duration = float(duration)
        self.time = 0.0
        self.playing = False
        self._mark = time.monotonic()

    def state(self):
        now = time.monotonic()
        if self.playing:
            self.time = min(self.duration, self.time + (now - self._mark))
            if self.time >= self.duration:
                self.playing = False
        self._mark = now
        return {'time': self.time, 'duration': self.duration, 'playing': self.playing}

    def play(self):
        self._mark = time.monotonic()
        self.playing = True

    def pause(self):
        self.state()
        self.playing = False

    def seek(self, seconds):
        self.time = min(max(0.0, float(seconds)), self.duration)
        self._mark = time.monotonic()

    def set_volume(self, value):
        pass

    def close(self):
        pass


# --------------------------------------------------------------------------- #
# Playback loop (mirrors player.run, with the platform bits swapped out)
# --------------------------------------------------------------------------- #
def _audio_path(args, film):
    if args.audio:
        return Path(args.audio).expanduser().resolve()
    path = Path(film.config['audio'])
    return path if path.is_absolute() else ROOT / path


def run(args, film):
    if not sys.stdout.isatty():
        raise RuntimeError('请在 Windows Terminal / PowerShell 窗口中运行（当前输出被重定向）。')
    console = Console()
    audio = None
    # Kept outside the try block so the report still gets written when the
    # audio device fails before the first frame.
    current = args.start
    frames = 0
    max_render = 0.
    report = []
    try:
        path = _audio_path(args, film)
        if args.silent:
            audio = SilentClock(film.config['duration'])
        else:
            if not path.is_file():
                raise RuntimeError(f'找不到音频：{path}\n请用 --audio 指定音频文件。')
            if path.suffix.lower() != '.wav' and _find_ffmpeg():
                # Decoding takes about a second for a full song; say so instead
                # of showing a blank window before the ready screen.
                console.write('正在解码音频，请稍候…')
            source, cleanup, device = prepare_audio(path)
            audio = MciAudio(source, device=device, cleanup=cleanup)
        console.enter()

        offset = args.offset if args.offset is not None else film.config.get('subtitle_offset', 0.)
        started = args.autoplay or args.paused
        paused = not args.autoplay
        help_on = False
        volume = 0.75
        ready = not started
        playing_seen = False
        size_last = None
        stalling = 0.

        audio.seek(args.start)
        if args.autoplay:
            audio.play()

        next_frame = time.monotonic()
        last_position = -1.
        while True:
            begin = time.monotonic()
            state = audio.state()
            current = state['time']
            duration = state['duration'] or film.config['duration']

            if state['playing']:
                playing_seen = True
                if abs(current - last_position) < 1e-6:
                    stalling += 1.0 / args.fps
                    if stalling > 3:
                        raise RuntimeError('音频时钟没有前进：请检查系统声音输出设备，'
                                           '或使用 --silent 观看无声版。')
                else:
                    stalling = 0.
            last_position = current

            if playing_seen and not state['playing'] and not paused and current < .05:
                current = duration
                paused = True
                audio.seek(duration - .02)
            elif started and not paused and not state['playing'] and current >= duration - .05:
                paused = True

            # Resizing the window is reported by the console itself, so the
            # player can follow it instead of trusting stale COLUMNS/LINES.
            width, height = console.size()
            w = min(width, 240)
            h = min(height, 85)
            # Leave the last column unused. This avoids autowrap artifacts.
            canvas = film.render(current, max(1, w - 1), h, paused, offset, help_on, ready)
            if (w, h) != size_last:
                console.write('\x1b[2J')
                size_last = (w, h)
            console.write(canvas.ansi())
            frames += 1
            max_render = max(max_render, time.monotonic() - begin)
            if frames % 30 == 0:
                report.append({'audio_time': current, 'playing': state['playing'],
                               'width': w, 'height': h, 'frames': frames})
            if args.stop_after is not None and current >= args.stop_after:
                break

            next_frame += 1.0 / args.fps
            delay = max(0., next_frame - time.monotonic())
            if delay == 0:
                next_frame = time.monotonic()
            keys = read_keys(delay)
            while keys:
                if keys.startswith('\x1b[C') or keys.startswith('\x1b[D'):
                    right = keys[2] == 'C'
                    keys = keys[3:]
                    audio.seek(min(duration - .05, max(0., current + (5 if right else -5))))
                    continue
                key, keys = keys[0], keys[1:]
                if key in ('q', 'Q', '\x1b', '\x03'):
                    return
                if key in (' ', '\r', '\n'):
                    if not started:
                        started = True
                        ready = False
                        paused = False
                        audio.play()
                    else:
                        paused = not paused
                        (audio.pause if paused else audio.play)()
                elif key in ('r', 'R'):
                    audio.seek(0)
                    audio.play()
                    started = True
                    ready = False
                    paused = False
                elif key in '12345':
                    audio.seek(player.CHAPTERS[int(key) - 1][0])
                    audio.play()
                    started = True
                    ready = False
                    paused = False
                elif key == '[':
                    offset = round(offset + .1, 2)
                elif key == ']':
                    offset = round(offset - .1, 2)
                elif key in ',.':
                    index = bisect.bisect_right(film.times, current + .03) - 1
                    index = min(len(film.times) - 1, max(0, index + (1 if key == '.' else -1)))
                    audio.seek(film.times[index])
                    started = True
                    ready = False
                elif key in 'hH':
                    help_on = not help_on
                elif key in '+=':
                    volume = min(1., volume + .05)
                    audio.set_volume(volume)
                elif key == '-':
                    volume = max(0., volume - .05)
                    audio.set_volume(volume)
    finally:
        if audio is not None:
            audio.close()
        console.leave()
        if args.report:
            Path(args.report).write_text(
                json.dumps({'frames': frames, 'last_time': current,
                            'max_frame_render_seconds': max_render, 'samples': report},
                           indent=2), encoding='utf-8')


def main(argv=None):
    if sys.version_info < (3, 9):
        raise SystemExit('需要 Python 3.9 或更新版本。')
    parser = argparse.ArgumentParser(description='world.execute(me); / bilingual terminal MV (Windows)')
    parser.add_argument('--audio')
    parser.add_argument('--start', type=float, default=0.)
    parser.add_argument('--autoplay', action='store_true')
    parser.add_argument('--fps', type=int, default=24)
    parser.add_argument('--paused', action='store_true')
    parser.add_argument('--offset', type=float)
    parser.add_argument('--snapshot', type=float)
    parser.add_argument('--width', type=int, default=120)
    parser.add_argument('--height', type=int, default=40)
    parser.add_argument('--plain', action='store_true')
    parser.add_argument('--report')
    parser.add_argument('--stop-after', type=float)
    parser.add_argument('--silent', action='store_true', help='不播放声音，用系统时钟驱动画面')
    args = parser.parse_args(argv)
    if not 5 <= args.fps <= 60:
        parser.error('--fps must be between 5 and 60')

    film = player.Film()
    if args.snapshot is not None:
        canvas = film.render(args.snapshot, args.width, args.height, True)
        print(canvas.plain() if args.plain else canvas.ansi())
        return 0
    try:
        run(args, film)
    except KeyboardInterrupt:
        pass
    except RuntimeError as error:
        print(f'播放失败：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    if not sys.stdout.isatty():
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
