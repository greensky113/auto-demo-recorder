# Auto Demo Recorder

> 为 TRAE SKILL 自动生成演示视频的一键录屏工具

| 特性 | 说明 |
|------|------|
| 🎯 **模拟 TRAE 任务界面** | 真实展示「用户输入指令 → 回车确认 → SKILL执行」的完整画面 |
| 🔝 **结果窗口自动置顶** | 每打开一个新文件（Excel/PNG/TXT），自动覆盖在上一个窗口之上 |
| 👆 **双模式录制** | **自动模式**按秒停留、**手动模式**按回车切换，可自由掌控节奏 |
| 🎥 **高画质 MP4** | 1920×1080 @ 15fps，原生 OpenCV 编码，体积小巧 |
| 🔧 **高度可定制** | 替换 2 个常量即可适配任意目标 SKILL |

## 安装

```bash
pip install opencv-python mss numpy
```

> 如果遇到权限问题，可使用本地安装：
> ```bash
> pip install --target ./libs opencv-python mss numpy
> ```
> 并在运行前设置 `PYTHONPATH=./libs`

## 快速开始

```bash
cd auto-demo-recorder
python record_demo.py
```

运行后会提示选择模式：

```
[1] 自动模式 - 每步自动停留
[2] 手动模式 - 按回车切下一步
```

## 自定义你的目标 SKILL

只需要修改 `record_demo.py` 顶部 **2 个常量**：

```python
TARGET_SCRIPT = r"C:\path\to\your\skill_script.py"   # 目标脚本路径
TARGET_COMMAND = "执行XXX指标自动通报"                  # TRAE界面展示的用户输入文字
```

## 视频输出

- **默认位置**：`C:\zhibiao\pic_result\演示视频_YYYYMMDD_HHMMSS.mp4`
- **分辨率**：自动匹配主显示器（通常 1920×1080）
- **大小参考**：30秒约 8-12 MB

## 工作流程

```
1. 开场画面
2. 展示源数据目录（4G/5G）
3. TRAE任务界面 → 输入指令 → 运行SKILL
4. 依次展示输出结果（新窗口置顶覆盖）
   4G总表 → 4G计算 → 5G总表 → 5G计算
   → 小区组看板 → 汇总看板 → 合并大图 → 文字通报
5. 结束保存MP4
```

## 许可证

MIT License

## 作者

由 TRAE SKILL 自动录屏工具生成
