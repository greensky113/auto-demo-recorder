# -*- coding: utf-8 -*-
"""
Auto Demo Recorder v2.0  -  record_demo.py
自动化演示视频录制工具：
 - 模拟 TRAE 任务界面输入指令调用 SKILL
 - 结果文件按顺序展示，新窗口始终置顶覆盖
 - 支持自动模式 & 手动模式（按回车切下一步）
"""

import os
import sys
import time
import subprocess
import threading
import numpy as np
import cv2
import mss
from datetime import datetime
import ctypes

# ========================================================================
# 以下区域 —— 面向使用者修改（按需自定义）
# ========================================================================

# 目标 SKILL 配置：把这两项换成你自己的 SKILL 即可
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_SCRIPT = os.path.join(SCRIPT_DIR, "..", "full_process.py")
TARGET_COMMAND = "执行4G5G指标自动通报"

# 依赖库路径（如果 --target 本地安装的话）
LIBS_PATH = os.path.join(SCRIPT_DIR, "..", "libs")

# 视频输出目录 & 命名
OUTPUT_DIR = r"C:\zhibiao\pic_result"
VIDEO_OUTPUT = os.path.join(
    OUTPUT_DIR, f"演示视频_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
)

# 视频参数
FPS = 15

# 自动模式下每步停留秒数
DELAY_INTRO = 3
DELAY_SOURCE_DIR = 4
DELAY_TRAE_INPUT = 3
DELAY_WAIT_SKILL_RUNNING = 2
DELAY_PER_RESULT = 5
DELAY_END = 3

# ========================================================================
# 以下区域 —— Win32 窗口置顶 & 录屏核心（一般无需改）
# ========================================================================

SW_RESTORE = 9
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


class ScreenRecorder:
    """屏幕录制器（独立线程写帧到 MP4）"""

    def __init__(self, output_path, fps=15):
        self.output_path = output_path
        self.fps = fps
        self.recording = False
        self.writer = None
        self.thread = None
        self.sct = mss.mss()

        monitor = self.sct.monitors[1]
        self.width = monitor["width"]
        self.height = monitor["height"]

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(output_path, fourcc, fps, (self.width, self.height))

    def _capture_loop(self):
        monitor = self.sct.monitors[1]
        while self.recording:
            img = self.sct.grab(monitor)
            frame = np.array(img)[:, :, :3]
            self.writer.write(frame)
            time.sleep(1.0 / self.fps)

    def start(self):
        self.recording = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print(f"  [录制] 开始录屏: {self.width}x{self.height} @ {self.fps}fps")

    def stop(self):
        self.recording = False
        if self.thread:
            self.thread.join(timeout=5)
        if self.writer:
            self.writer.release()
        self.sct.close()
        print(f"  [录制] 视频已保存: {self.output_path}")


def bring_window_to_front(pid=None):
    """调用 Win32 API 将窗口置顶（总是覆盖在上一个之上）"""
    try:
        user32 = ctypes.windll.user32

        def enum_handler(hwnd, _):
            found_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
            if pid is None or found_pid.value == pid:
                if user32.IsWindowVisible(hwnd):
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetWindowPos(
                        hwnd,
                        HWND_TOPMOST,
                        0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                    )
                    user32.SetForegroundWindow(hwnd)

        cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_handler)
        user32.EnumWindows(cb, 0)
    except Exception:
        pass
    time.sleep(0.3)


def open_file_on_top(filepath):
    if not os.path.exists(filepath):
        print(f"  [警告] 文件不存在: {filepath}")
        return False
    try:
        os.startfile(filepath)
        time.sleep(1.2)
        bring_window_to_front()
        return True
    except Exception as e:
        print(f"  [警告] 打开失败 {os.path.basename(filepath)}: {e}")
        return False


def open_folder_on_top(folder_path):
    if not os.path.exists(folder_path):
        print(f"  [警告] 目录不存在: {folder_path}")
        return False
    try:
        proc = subprocess.Popen(["explorer", folder_path])
        time.sleep(1.5)
        bring_window_to_front(proc.pid if proc else None)
        return True
    except Exception as e:
        print(f"  [警告] 打开目录失败: {e}")
        return False


def find_latest_file(directory, prefix, suffix):
    if not os.path.exists(directory):
        return None
    cands = [f for f in os.listdir(directory) if f.startswith(prefix) and f.endswith(suffix)]
    if not cands:
        return None
    cands.sort(reverse=True)
    return os.path.join(directory, cands[0])


def wait_for_user_or_auto(step_label, auto_delay, manual_mode):
    """手动模式：按回车/输入秒数进入下一步；自动模式：等待auto_delay秒"""
    if manual_mode:
        prompt = f"\n>>> [{step_label}] 按 [回车键] 进入下一步，或直接输入秒数自动等待："
        try:
            ans = input(prompt).strip()
            if ans.isdigit():
                secs = int(ans)
                print(f"    自动等待 {secs} 秒后继续...")
                time.sleep(secs)
        except EOFError:
            time.sleep(auto_delay)
    else:
        print(f"  [录制] 展示 {step_label}，停留 {auto_delay} 秒")
        time.sleep(auto_delay)


def run_skill_in_cmd():
    """模拟 TRAE 任务界面：先显示 "用户输入指令"，再真实执行目标脚本"""
    inner_cmd = (
        f"@echo off && "
        f"title TRAE 任务界面 - 4G5G指标自动通报 && "
        f"echo. && "
        f"echo ================================================================ && "
        f"echo   TRAE 任务界面                                                   && "
        f"echo ================================================================ && "
        f"echo. && "
        f"echo   用户输入： {TARGET_COMMAND} && "
        f"echo. && "
        f"echo   [回车] 确认执行...                                              && "
        f"echo. && "
        f"set PYTHONPATH={LIBS_PATH} && "
        f"python \"{TARGET_SCRIPT}\""
    )
    return subprocess.Popen(
        ["cmd", "/k", inner_cmd],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def ask_mode():
    print()
    print("请选择录制模式：")
    print("  [1] 自动模式 - 每步自动停留指定秒数，无需人工干预")
    print("  [2] 手动模式 - 每步按回车键切换，可自由操作鼠标")
    try:
        ans = input("输入模式编号 (1/2，默认1): ").strip() or "1"
        return ans == "2"
    except EOFError:
        return False


# ========================================================================
# 主流程
# ========================================================================
def run_demo():
    print("=" * 60)
    print("  Auto Demo Recorder v2.0")
    print("  • 模拟TRAE界面输入指令")
    print("  • 结果窗口自动置顶覆盖")
    print("  • 支持自动 / 手动模式")
    print("=" * 60)
    print(f" 目标指令: {TARGET_COMMAND}")
    print(f" 视频输出: {VIDEO_OUTPUT}")
    print()

    manual_mode = ask_mode()
    mode_name = "手动模式" if manual_mode else "自动模式"
    print(f"\n当前模式: {mode_name}\n")

    recorder = ScreenRecorder(VIDEO_OUTPUT, fps=FPS)

    # 步骤1：开场
    print("\n[步骤1] 开始录制 - 桌面开场")
    recorder.start()
    wait_for_user_or_auto("桌面开场", DELAY_INTRO, manual_mode)

    # 步骤2：源数据目录
    print("\n[步骤2] 展示源数据目录")
    open_folder_on_top(r"C:\zhibiao\4G_source")
    wait_for_user_or_auto("4G源数据目录", DELAY_SOURCE_DIR, manual_mode)
    open_folder_on_top(r"C:\zhibiao\5G_source")
    wait_for_user_or_auto("5G源数据目录", DELAY_SOURCE_DIR, manual_mode)

    # 步骤3：模拟TRAE界面输入指令 -> 运行SKILL
    print(f"\n[步骤3] TRAE界面输入指令: {TARGET_COMMAND}")
    skill_proc = run_skill_in_cmd()
    time.sleep(DELAY_TRAE_INPUT)
    bring_window_to_front(skill_proc.pid if skill_proc else None)
    wait_for_user_or_auto(
        f"TRAE界面已输入『{TARGET_COMMAND}』",
        DELAY_WAIT_SKILL_RUNNING,
        manual_mode,
    )
    # 等待SKILL运行完成（监控合并大图作为结束标志）
    print("  SKILL正在执行，等待输出生成...")
    max_wait, waited = 180, 0
    while waited < max_wait:
        merged = find_latest_file(OUTPUT_DIR, "指标通报汇总图_", ".PNG")
        if merged:
            print(f"  ✓ SKILL执行完成")
            time.sleep(3)
            break
        time.sleep(2)
        waited += 2
        if waited % 10 == 0:
            print(f"  已等待 {waited} 秒...")

    # 步骤4：展示所有输出结果（按顺序打开，每一个都置顶覆盖）
    print("\n[步骤4] 依次展示输出结果（新窗口置顶覆盖）")
    steps = []

    total_4g = find_latest_file(r"C:\zhibiao\4G_output", "4G总表_", ".xlsx")
    if total_4g:
        steps.append(("4G总表Excel", total_4g))
    r4g = find_latest_file(r"C:\zhibiao\4G_output", "4G指标通报计算结果_", ".xlsx")
    if r4g:
        steps.append(("4G计算结果Excel", r4g))
    total_5g = find_latest_file(r"C:\zhibiao\5G_output", "5G总表_", ".xlsx")
    if total_5g:
        steps.append(("5G总表Excel", total_5g))
    r5g = find_latest_file(r"C:\zhibiao\5G_output", "5G指标通报计算结果_", ".xlsx")
    if r5g:
        steps.append(("5G计算结果Excel", r5g))

    boards = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.endswith(".PNG")
        and "指标通报计算结果" in f
        and "汇总" not in f
        and "汇总图" not in f
    ])
    for b in boards:
        steps.append((b, os.path.join(OUTPUT_DIR, b)))

    sb = find_latest_file(OUTPUT_DIR, "汇总指标通报计算结果_", ".PNG")
    if sb:
        steps.append(("汇总看板", sb))
    mg = find_latest_file(OUTPUT_DIR, "指标通报汇总图_", ".PNG")
    if mg:
        steps.append(("合并大图", mg))

    txts = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".txt") and "文字通报" in f])
    for t in txts[:2]:
        steps.append((t, os.path.join(OUTPUT_DIR, t)))

    for idx, (label, filepath) in enumerate(steps, 1):
        print(f"\n  [4.{idx}] 打开: {label}")
        open_file_on_top(filepath)
        wait_for_user_or_auto(label, DELAY_PER_RESULT, manual_mode)

    # 步骤5：结束录制
    print("\n[步骤5] 结束录制")
    wait_for_user_or_auto("结束画面", DELAY_END, manual_mode)
    recorder.stop()

    print("\n" + "=" * 60)
    print(f"✓ 演示视频录制完成！")
    print(f"  模式: {mode_name}")
    print(f"  文件: {VIDEO_OUTPUT}")
    print(f"  参数: {recorder.width}x{recorder.height} @ {FPS}fps")
    print("=" * 60)


if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        print("\n用户中断录制")
    except Exception as e:
        print(f"\n录制出错: {e}")
        import traceback
        traceback.print_exc()
