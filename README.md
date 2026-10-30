# world.execute(me); —ascii

![world.execute(me);](docs/images/mv-cover.png)

Mili《world.execute(me);》的字符动画。支持中英字幕、原曲同步播放和终端字符动画。

## 创作提示词

整理了这支 MV 从初始构想到逐段调整的 **25 轮提示词**，以及一份方便复用的合并版。

- **[在线阅读创作过程](docs/prompts/creation-prompts.md)**：按轮次查看需求、场景位置与修改方向，文内目录可直接跳转。
- **[直接查看合并提示词](docs/prompts/creation-prompts.md#combined-prompt)**：适合整体阅读和复制使用。
- **[纯文本版](docs/prompts/creation-prompts.txt)**：方便保存到本地或在文本编辑器中打开。

## 单文件运行（推荐）

从本仓库的 **Releases** 下载 `world-execute-mv-macos.zip` 并解压。音乐、动画、字幕、频谱数据和音频播放组件已经内嵌在 `world-execute-mv.pyz` 内，无需另外下载或指定 MP3。

需要 **macOS 12 或更新版本、Python 3.9 或更新版本**。音频组件同时包含 Apple Silicon 和 Intel 架构。终端播放器自身只使用 Python 标准库。

在 macOS「终端」中进入解压目录运行：

```sh
python3 world-execute-mv.pyz
```

也可双击 `运行单文件.command`，在系统终端中播放。按空格开始。推荐全屏，终端至少 64 列 × 24 行，128 列 × 44 行及以上效果更好。

```sh
# 从 2:38.7 开始直接播放
python3 world-execute-mv.pyz --start 158.7 --autoplay
```

内嵌音乐是随程序封装的资源，不是加密或 DRM。播放时会解包到当前用户的临时目录，正常退出后清理；不会读取旧电脑 Downloads 中的文件。运行过程无需联网。

## 在 Windows 上运行

Windows 10/11 版复用同一套渲染代码（`player.py` + `scenes.py`），只替换平台层：终端控制走 Win32 控制台 API，音频交给系统自带的 MCI/waveOut 播放（MP3 先由 ffmpeg 解码成临时 WAV，避免 DirectShow 把声音送到显示器）。不需要 Swift 音频组件，也不依赖第三方 Python 库。

需要 **Windows 10 1809+ / Windows 11、Python 3.9+**，推荐使用 Windows Terminal（F11 全屏）。建议安装 ffmpeg（`winget install Gyan.FFmpeg`），否则个别机器可能出现画面正常但没有声音的情况。

从 **Releases** 下载 `world-execute-mv-windows.zip` 并解压，双击 `run.cmd`，或在解压目录执行：

```bat
python world-execute-mv-win.pyz
```

从 2:38.7 开始直接播放：

```bat
python world-execute-mv-win.pyz --start 158.7 --autoplay
```

也可以直接从源码运行：

```bat
python player_win.py
```

没有声音输出设备时加 `--silent`，用系统时钟驱动画面。字体、全屏、按键和与 macOS 版的差异见 [README-Windows.md](README-Windows.md)。

## 操作

| 按键 | 功能 |
| --- | --- |
| 空格 | 开始／暂停 |
| 左／右 | 后退／前进 5 秒 |
| R | 从头播放 |
| Q | 退出 |
| H | 显示全部帮助 |
| 1–5 | 跳转章节 |

## 从源码运行

仓库不保存音频文件。从源码运行或重新打包前，请将自己的音频放到本地 `media/song.mp3`。使用 Release 播放包无需此步骤。

首次构建音频组件需要 Apple Command Line Tools（含 Swift 编译器）：

```sh
xcode-select --install
```

然后执行：

```sh
./run.sh
```

启动脚本在缺少 `audio-clock` 时自动编译本机架构。双击 `播放MV.command` 可在 macOS 系统终端中运行源码版。

## 重新打包

```sh
python3 tools/build_bundle.py
python3 tests/test_bundle.py
```

构建输出在 `dist/`：

- `world-execute-mv.pyz`：内嵌音乐的单文件播放器。
- `world-execute-mv-macos.zip`：包含播放器、启动器、说明的分发包。
- `SHA256SUMS.txt`：下载校验值。

Windows 单文件包（已有 macOS 包时直接复用其中的音乐与画面资源，保证两版内容一致）：

```bat
python tools/build_win_bundle.py
python -m unittest tests.test_win_bundle
```

输出 `dist/world-execute-mv-win.pyz`、`dist/world-execute-mv-windows.zip` 和
`dist/SHA256SUMS-win.txt`。

音频以 macOS 音频时钟驱动画面；暂停、跳转时字幕与动画跟随音频时间。构建会生成 universal 音频组件，并在单文件包内记录各资源 SHA-256 以检查完整性。

## 收录范围

本仓库为项目归档，包含当前播放器、字幕、频谱和构建工具。音乐仅内嵌于 Release 播放包。

原曲与歌词：Mili《world.execute(me);》。本项目是个人创作与备份，未对原曲、歌词或其他第三方素材授予额外使用许可。
