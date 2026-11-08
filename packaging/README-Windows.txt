BandTab Studio — Windows 使用说明

适用：Windows 10 1809 及以上 / Windows 11，x64 电脑。
本版使用 CPU 识别，包含 Python、Qt、FFmpeg、AI 引擎和模型。
普通使用者不需要自行安装这些依赖。

安装版：
运行 BandTabStudio-Windows-x64-Setup.exe，按提示安装到当前用户目录。
可以选择桌面快捷方式和 .bandtab 项目的“打开方式”注册。
安装不需要管理员权限。卸载在 Windows 的“已安装的应用”中完成。
升级使用相同安装目录；卸载不会删除用户曲库。

便携版：
完整解压 BandTabStudio-Windows-x64-Portable.zip。
打开 BandTabStudio 文件夹，双击 BandTabStudio.exe。
保留 _internal 等同目录文件，不要只复制一个 EXE。
便携版的曲库默认仍保存在用户目录，不写入程序文件夹。

第一次使用：
1. 点击“原创练习曲”，先体验动态跟谱和编辑。
2. 点击“导入音乐”或拖入音频。整曲混音选择“完整乐队”。
3. 核对调弦、变调夹、BPM、拍号，开始转写。
4. 逐句校正，使用慢放、A/B 循环、分轨静音/独奏排练。
5. “分享完整项目”导出 .bandtab，队友用 BandTab 打开即可。
6. “导出谱子”可保存 MIDI、MusicXML 或文本 TAB。

曲库及日志：
%LOCALAPPDATA%\BandTab Studio\
软件中也可点击“打开数据文件夹”。
不要把这个目录当作可重新生成的安装文件删除。
升级前可用“分享完整项目”备份重要歌曲。

离线与速度：
完整软件包包含模型，第一次运行会准备可写缓存。
模型准备好后可以离线识别；CPU 处理整曲可能很慢，先用短片段判断效果。
支持中文及含空格的音频路径。
当前没有断点续算；取消会等待当前推理片段结束。

没有声音：
检查 Windows 输出设备以及软件内的静音、独奏、音量。
显示“未检测到音频输出设备”时，请先连接扬声器或耳机。
自动转谱、指法、鼓点和重拍都需要人工复核。
示例曲是预先编写的谱子，不代表识别准确率。

如果 Windows 显示“未知发布者”：
预览版可能尚未进行商业代码签名，请核对来源和 SHA256SUMS.json。
不要关闭系统防护。遇到错误可附上 desktop.log 向项目反馈。
仓库：https://github.com/Jason-TongR/Muscic-change-to-Band-Tab
