---
name: "auto-demo-recorder"
description: "演示录屏工具。当用户明确要求「并完成自动录屏」时调用：先正常运行SKILL生成输出，再自动录屏展示全过程。Invoke ONLY when user explicitly says '录屏' or '并完成自动录屏' alongside a SKILL execution request."
---

# Auto Demo Recorder (演示录屏工具)

**版本**: v3.2
**适用系统**: Windows 10/11

---

## 触发规则（关键）

### ✅ 触发条件
用户输入中**同时包含**以下两类关键词时才调用：
1. SKILL执行指令（如"执行4G5G指标自动通报"）
2. 录屏关键词（"并完成自动录屏"、"并录屏"、"并生成演示视频"）

**示例触发**:
- "执行4G5G指标自动通报，并完成自动录屏"
- "执行4G5G指标自动通报，并录屏"
- "执行4G5G指标自动通报，生成演示视频"

### ❌ 不触发条件
- "执行4G5G指标自动通报" → 仅执行SKILL，不录屏
- "查看输出结果" → 直接打开文件
- 用户未明确提到"录屏"

---

## 执行流程（全程录屏）

```
用户输入: "执行4G5G指标自动通报，并完成自动录屏"
                    │
    ┌───────────────┴───────────────┐
    │  录屏开始（全程不间断录制）     │
    │                               │
    │  步骤1: 桌面开场画面           │
    │  步骤2: 展示源数据目录          │
    │  步骤3: 模拟TRAE界面           │
    │    → 显示"用户输入指令"        │
    │    → 真实运行SKILL脚本         │
    │    → 录制SKILL运行全过程       │
    │    → 等待SKILL执行完成         │
    │  步骤4: 展示所有输出结果       │
    │    （新窗口置顶覆盖）          │
    │  步骤5: 停止录制保存MP4        │
    │  → 自动播放视频                │
    └───────────────────────────────┘
```

> **关键**: 录屏从步骤1就开始，SKILL运行过程（步骤3）也被完整录制。

---

## 调用命令

```bash
cd auto-demo-recorder
python auto_record.py
```

---

## 文件结构

```
auto-demo-recorder/
├── auto_record.py     # 主入口：两阶段自动录屏（先SKILL后录屏）
├── server.py          # Web控制面板（可选，手动模式）
├── index.html         # Web前端（可选）
├── record_demo.py     # 命令行版录屏（可选，独立使用）
├── SKILL.md           # 本文档
├── README.md          # GitHub说明
├── LICENSE            # MIT
└── .gitignore
```

---

## 配置项（auto_record.py 顶部）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `TARGET_SCRIPT` | ../full_process.py | 目标SKILL脚本路径 |
| `TARGET_COMMAND` | 执行4G5G指标自动通报 | TRAE界面显示的指令文字 |
| `OUTPUT_DIR` | C:\zhibiao\pic_result | 输出目录 |
| `FPS` | 15 | 视频帧率 |
| `DELAY_INTRO` | 3秒 | 开场画面停留 |
| `DELAY_SOURCE` | 4秒 | 源数据目录停留 |
| `DELAY_TRAE_DISPLAY` | 4秒 | TRAE界面展示停留 |
| `DELAY_PER_RESULT` | 5秒 | 每个结果文件停留 |
| `DELAY_END` | 3秒 | 结束画面停留 |

---

## 依赖

```bash
pip install opencv-python mss numpy
```

---

## 录屏展示顺序

1. 桌面开场画面
2. 4G源数据目录 → 5G源数据目录
3. TRAE任务界面（显示"用户输入：执行4G5G指标自动通报"）
4. 4G总表 → 4G计算结果 → 5G总表 → 5G计算结果
5. 各小区组看板（场馆内 → 周边道路 → 场馆外）
6. 汇总看板 → 合并大图
7. 文字通报（前2个）
8. 结束，自动播放视频

> 每个新窗口自动置顶，覆盖在上一个窗口之上。
