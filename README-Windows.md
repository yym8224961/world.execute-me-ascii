# world.execute(me); — Windows 版

Mili《world.execute(me);》的终端字符 MV，Windows 10/11 版。

画面、字幕、频谱和音乐与 macOS 版完全一致；只有平台层不同：Windows 版用 Win32 控制台
输出画面，音频交给系统自带的 MCI/waveOut 播放，不需要 Swift 音频组件，也不需要安装
第三方 Python 库。

## 需要什么

- Windows 10（1809 及以上）或 Windows 11
- Python 3.9 或更新版本（推荐 3.12），安装时勾选 **Add python.exe to PATH**
  - 下载：<https://www.python.org/downloads/windows/>
  - 已装 Microsoft Store 版 Python 也可以
- 推荐使用 **Windows Terminal**（Windows 11 自带），支持真彩色、Unicode 和 F11 全屏；
  旧版控制台（conhost）也能运行，全屏用 Alt+Enter
- 建议安装 **ffmpeg**（只用于解码音频，见下面「声音」一节）

## 声音

Windows 版会用 ffmpeg 把 MP3 解码成临时 WAV，再交给 MCI 的 waveaudio 设备播放，
这样音频走 waveOut，也就是系统默认输出设备。

之所以要多这一步：MCI 直接播 MP3 时会交给 DirectShow，而 DirectShow 在部分机器上会把
声音送到**另一个设备**（例如显示器 HDMI），表现就是「画面在动、进度在走，但没声音」。
解码成 WAV 后走 waveOut 就不会跑偏。

- 检测到 ffmpeg 时会自动解码，启动多花约 0.2–1 秒，退出时删除临时文件
- 没装 ffmpeg 时退回 MCI 直放：多数机器正常，少数机器可能没声音
- 安装 ffmpeg：`winget install Gyan.FFmpeg`，或从 <https://www.gyan.dev/ffmpeg/builds/>
  下载后把 `bin` 目录加入 PATH，确认 `ffmpeg -version` 可用
- 也可以直接播 WAV：`python world-execute-mv-win.pyz --audio 你的文件.wav`，不依赖 ffmpeg
- 播放为满音量，请在系统音量里调节；`+` / `-` 在 WAV 路径上不生效

## 运行

双击 `run.cmd`，或在本目录的终端里执行：

```bat
python world-execute-mv-win.pyz
```

推荐全屏。终端至少 64 列 × 24 行，128 列 × 44 行及以上效果更好。

从 2:38.7 开始直接播放：

```bat
python world-execute-mv-win.pyz --start 158.7 --autoplay
```

`run.cmd` 会把参数原样传下去，所以也可以：

```bat
run.cmd --start 158.7 --autoplay
```

## 操作

| 按键 | 功能 |
| --- | --- |
| 空格 / 回车 | 开始／暂停 |
| 左／右 | 后退／前进 5 秒 |
| R | 从头播放 |
| 1–5 | 跳转五个章节 |
| `[` / `]` | 字幕提前／延后 0.1 秒 |
| `,` / `.` | 上一句／下一句 |
| `+` / `-` | 音量 |
| H | 显示／关闭帮助 |
| Q / Esc | 退出 |

## 没有声音或没有输出设备

用系统时钟驱动画面（不出声）：

```bat
python world-execute-mv-win.pyz --silent
```

如果启动后画面停在原地并提示「音频时钟没有前进」，通常是系统没有可用的声音输出设备，
插上耳机/音箱或改用 `--silent` 即可。

## 中文显示成方块

控制台字体要同时覆盖中文和方块字符。Windows Terminal 使用默认字体一般正常；旧版
控制台请在窗口属性 → 字体里选择 **新宋体 (NSimSun)** 或 **Cascadia Mono**，
不要用只含西文的点阵字体。

## 资源与校验

音乐、动画、字幕和频谱数据都打包在 `world-execute-mv-win.pyz` 里。首次运行会把资源
解包到 `%TEMP%\world-execute-mv-*`，按 `bundle-manifest.json` 里的 SHA-256 逐个校验，
正常退出后删除。运行过程无需联网。

也可以直接用源码运行（在仓库根目录）：

```bat
python player_win.py
```

## 与 macOS 版的差异

- 音频：ffmpeg 解码 → MCI waveaudio 播放，时间轴取自音频设备位置，暂停、跳转、
  结尾判定与 macOS 版行为一致；跳转精度约 10ms。没有 ffmpeg 时退回 MCI 直放。
- 音量：以系统音量控制为准，播放器内的 `+` / `-` 不再改变音量。
- 画面：完全复用同一套 `player.py` + `scenes.py` 渲染代码。
- 打包：Windows 版不含 `audio-clock`（macOS 的 Swift 组件）。
