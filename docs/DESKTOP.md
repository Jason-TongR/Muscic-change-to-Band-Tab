# BandTab Studio 桌面版

原生 Qt 桌面程序，使用本机文件和识别进程，不启动网页服务，不依赖浏览器。普通用户使用打包后的应用，不需要安装 Python、命令行依赖或配置端口。

## 使用

1. 启动 BandTab Studio，先打开「原创练习曲」体验跟谱。这是预先编写的合成演示，不代表自动识别准确度。
2. 拖入音频，或点「导入音乐」。完整歌曲选「完整乐队」；已分离的吉他等音轨选「单乐器多音」；干净单音可用基础模式。
3. 设置调弦和变调夹。有已知 BPM 时手动填写。完成后核对拍号、重拍与指法。
4. 点击音符修改；也可在「音符清单」双击/回车编辑。支持新增、删除、撤销和保存。
5. 播放时跟谱，设置 A/B 循环，调整速度，使用 M 静音 / S 独奏分轨。变速保调由 Qt Multimedia 后端提供。
6. 「导出谱子」导出 MIDI、MusicXML 或文本六线谱。「分享完整项目」生成 `.bandtab` 文件，包含当前谱子、原曲及分离音轨；接收方在桌面版中打开即可排练和编辑，不必再次识别。

可以打开旧版网页项目的 `project.json`，前提是它的音频仍在原项目目录。桌面版会复制音频到自己的曲库，不修改原项目。

## 下载模型与离线使用

完整版打包包含 AI 运行库、Basic Pitch ONNX 模型、音频解码器和六轨分离模型。第一次使用时从随包模型恢复到可写缓存；也可在「引擎与离线模型」手动准备，缺失时从 Demucs 官方地址下载约 55 MB，并校验文件哈希。模型已准备后识别可离线运行。

首次 librosa/Numba 编译缓存及 CPU 分轨可能较慢。处理放在独立进程，窗口可继续操作；取消操作会等待当前推理片段结束，分离子进程会收到停止请求。任务运行时关闭窗口可以选择取消后退出，不强行留下后台识别任务。

无论网页或桌面界面，识别准确度取决于同一套模型：失真、叠录、主音/节奏吉他混合、推弦、闷音、滑音、鼓组分类仍需人工校正。鼓谱只有底鼓/军鼓/踩镲参考。和弦为大/小三和弦参考。

## 用户数据位置

- Windows：`%LOCALAPPDATA%\BandTab Studio\`
- macOS：`~/Library/Application Support/BandTab Studio/`
- Linux：`~/.local/share/bandtab-studio/`（遵循 XDG_DATA_HOME）

其中 `projects/` 是曲库，`models/` 是模型缓存，`cache/` 是计算缓存。软件升级不会覆盖曲库。也可用环境变量 `BANDTAB_HOME` 指定整个数据目录。项目包不是可执行程序；导入会检查路径、音符数据和解压大小。

## 开发环境

现有开发环境：Linux 可运行 `bash scripts/start_desktop.sh`；Windows 可双击 `scripts/start_desktop.bat`。

新电脑进行源码开发时使用 Python 3.11：

```text
python scripts/setup_desktop.py
```

此脚本创建 `.venv-desktop`，安装 CPU PyTorch、Qt、ONNX 和转写依赖。普通接收方不运行此脚本，直接使用发行包。

## 三个平台的打包

在目标系统的 `.venv-desktop` 环境中运行：

```text
python scripts/build_desktop.py --archive
```

- Windows x64：`dist/BandTabStudio/` 便携目录及 ZIP；装有 Inno Setup 6.5 及以上时额外生成 `.exe` 安装包，按当前用户安装、无需管理员权限。分享整个目录或安装包，不要只复制单个 EXE。
- macOS：生成 `BandTabStudio.app`、ZIP 和 DMG；Intel 与 Apple Silicon 在对应架构分别构建，最低 macOS 13。Intel Mac 使用仍提供 x86_64 轮子的 PyTorch 2.2.2，其他目标使用 2.5.1。正式面向公众分发还需要开发者证书签名、公证；未签名测试版不声称可绕过系统安全检查。
- Linux x64：生成便携目录及 `.tar.gz`；解压后运行其中的 `BandTabStudio`。便携包仍依赖目标发行版的系统图形/音频库和 glibc，不是任意 Linux 通用二进制。建议在支持范围最旧的发行版上构建。

PyInstaller 不跨操作系统生成可执行程序。本仓库提供 `.github/workflows/desktop-build.yml`，手动触发后在 Windows、Linux、macOS Apple Silicon、macOS Intel 四种 runner 上分别构建，并运行打包程序的自检，产物留在 Actions artifacts。Windows 另有专用构建流程与 `build-windows.cmd` 一键入口，会检查便携运行、试装、离线模型、重复安装及卸载，详见 [Windows 说明](WINDOWS.md)。以每次实际报告为准；工作流不会自动发布发行版。

## 验证

```text
python -m unittest discover -s tests -v
python desktop.py --self-test
python desktop.py --self-test --ai
```

CI 下可设置 `QT_QPA_PLATFORM=offscreen`，无须实体显示器。自检会验证原生窗口、项目包往返、独立识别进程，并在 `BANDTAB_HOME` 写入截图和 `self-test-report.json`。`--ai` 额外运行真实六轨模型。检查结果不等于真实歌曲的准确率。

## 技术依据

- Qt 官方原生界面与多媒体文档：https://doc.qt.io/qtforpython-6/
- PyInstaller 的独立程序与平台限制：https://pyinstaller.org/en/stable/operating-mode.html
- 支持的平台构建机：https://docs.github.com/en/actions/reference/runners/github-hosted-runners

第三方组件声明和许可证随应用放在 `licenses/`，详见 `packaging/THIRD_PARTY.md`。

若「未检测到音频输出设备」，仍能识别与改谱，但无法从该运行环境验证扬声器发声。请检查系统的输出设备。

## 本轮验证范围

本机为 Ubuntu 26.04 / x86_64 / glibc 2.43。已完成原生界面、音符编辑与指法、保存撤销、混音音量控制、项目包迁移测试，以及独立可执行文件的完整 AI 分离与转谱自检。自检使用原创合成短音频，不代表真实歌曲识别准确率。

当前运行环境没有实体显示会话和可用音频输出设备，窗口通过 Qt 离屏渲染验证。真实扬声器/耳机发声与 macOS 安装运行还需对应设备验证。Windows 安装测试结果单独记录在 `Windows-validation.json`。此处产生的 Linux 便携包标注 glibc 版本，不宣称可运行在较旧的发行版；跨平台工作流以 Ubuntu 22.04 构建更广泛兼容的 Linux 包。
