---
name: "auto-demo-recorder"
description: "全自动演示视频录制器，模拟TRAE界面输入指令调用SKILL，依次展示输出结果（新窗口置顶覆盖），支持自动/手动两种录制模式。Invoke when the user asks to make a demo video for a SKILL or record an automated workflow showcase."
---

# Auto Demo Recorder (自动演示录屏 SKILL)

**版本**: v2.0
**适用系统**: Windows 10/11
**触发条件**: 用户要求为某个 SKILL 制作演示视频、录制操作展示、生成自动演示 MP4

---

## 核心特性

| 功能 | 说明 |
|------|------|
| ✅ 模拟 TRAE 指令输入 | 在任务界面展示 "用户输入：XXX" 的效果，然后才执行脚本 |
| ✅ 窗口自动置顶 | 每打开一个新结果窗口，自动置顶覆盖在上一个窗口之上 |
| ✅ 双模式切换 | **自动模式**：每步按配置时间停留；**手动模式**：按回车键切换下一步 |
| ✅ 可扩展步骤 | 支持自定义「源数据 → 执行SKILL → 展示结果」的所有步骤 |
| ✅ 高画质 MP4 | 1920×1080 @ 15fps，可按需调整 |

---

## 一、调用方式

```
制作一个演示视频
帮我录制XX SKILL的演示视频
生成一个自动演示MP4
```

## 二、工作流程（固定步骤）

```
┌──────────────┐
│  步骤1       │  开场画面（桌面）
└──────────────┘
       │
┌──────────────┐
│  步骤2       │  展示源数据目录（4G/5G）
└──────────────┘
       │
┌──────────────┐
│  步骤3       │  TRAE 界面输入指令 → 回车确认 → 运行 SKILL
└──────────────┘
       │
┌──────────────┐
│  步骤4       │  依次打开所有输出结果（新窗口置顶覆盖）
│              │    4G总表 → 4G计算 → 5G总表 → 5G计算
│              │    → 各小区组看板 → 汇总看板 → 合并大图 → 文字通报
└──────────────┘
       │
┌──────────────┐
│  步骤5       │  结束录制保存 MP4
└──────────────┘
```

## 三、模式选择

| 模式 | 交互方式 | 适用场景 |
|------|----------|----------|
| **自动模式** `[1]` | 每步按 DELAY_* 配置秒数自动停留 | 无人值守录制、快速生成成片 |
| **手动模式** `[2]` | 每步需按回车键进入下一步；也可输入数字N自动等待N秒 | 需要配合鼠标操作、讲解、特写某画面 |

## 四、依赖库

```bash
pip install opencv-python mss numpy pillow pandas matplotlib openpyxl
```

（如权限受限，可使用 `--target ./libs` 安装到本地目录，并设置 `PYTHONPATH`）

## 五、核心入口脚本

### `record_demo.py`

```python
# -*- coding: utf-8 -*-
"""
Auto Demo Recorder v2.0
使用：python record_demo.py
"""
```

### 配置项（脚本顶部可直接修改）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TARGET_SCRIPT` | - | 目标 SKILL 的核心脚本路径（如 `full_process.py`） |
| `TARGET_COMMAND` | - | 模拟输入的指令文字（如 `执行4G5G指标自动通报`） |
| `OUTPUT_DIR` | - | 输出结果所在目录（用于监控和展示） |
| `FPS` | 15 | 视频帧率 |
| `DELAY_INTRO` | 3 | 开场停留时间（秒） |
| `DELAY_SOURCE_DIR` | 4 | 源数据目录停留 |
| `DELAY_TRAE_INPUT` | 3 | TRAE 指令输入展示停留 |
| `DELAY_WAIT_SKILL_RUNNING` | 2 | 按回车后短暂停留 |
| `DELAY_PER_RESULT` | 5 | 每个结果文件停留 |
| `DELAY_END` | 3 | 结束画面停留 |

## 六、关键 API 函数

| 函数 | 作用 |
|------|------|
| `ScreenRecorder(path, fps)` | 屏幕录制器，含 start/stop 方法 |
| `open_folder_on_top(path)` | 打开文件夹并置顶 |
| `open_file_on_top(path)` | 打开任意文件（Excel/PNG/TXT）并置顶 |
| `run_skill_in_cmd()` | 新开 cmd 模拟 TRAE 界面显示指令后运行脚本 |
| `wait_for_user_or_auto(label, delay, manual_mode)` | 统一调度：自动等待 or 手动回车 |
| `bring_window_to_front(pid=None)` | 用 Win32 API 将窗口置顶（HWND_TOPMOST） |
| `find_latest_file(dir, prefix, suffix)` | 从目录中找最新匹配的输出文件 |

## 七、视频输出

- **命名格式**: `演示视频_YYYYMMDD_HHMMSS.mp4`
- **输出路径**: `{OUTPUT_DIR}/`（默认为 `C:\zhibiao\pic_result\`）
- **编码格式**: MP4V / H.264 兼容
- **分辨率**: 与主显示器一致（通常 1920×1080）

## 八、常见问题

| 问题 | 解决 |
|------|------|
| 新窗口没有覆盖在上一个上 | 增加 `open_file_on_top` 中的 `time.sleep` 到 1.5~2 秒 |
| 视频帧数过多/体积过大 | 降低 FPS 到 10，或缩短 DELAY 时间 |
| 手动模式时无法输入 | 确保控制终端处于焦点状态；如果仍不可用，脚本会自动回退到等待默认秒数 |
| SKILL 执行时间超过 3 分钟 | 修改 `max_wait`（默认 180 秒）参数 |

## 九、二次开发指南

1. **新增展示步骤**: 在 `run_demo()` 函数的 result_steps 列表里追加 `(标签, 文件路径)` 即可
2. **替换目标 SKILL**: 修改顶部 `TARGET_SCRIPT` 与 `TARGET_COMMAND` 两个常量
3. **添加文字水印**: 在 `ScreenRecorder._capture_loop` 里调 `cv2.putText` 在 frame 上写文字
4. **自定义录屏区域**: 把 `sct.monitors[1]` 换成 `{"left":0,"top":0,"width":1280,"height":720}`

---

项目仓库: https://github.com/your-username/auto-demo-recorder
