# -*- coding: utf-8 -*-
"""
Auto Demo Recorder v3.2 - auto_record.py
全程录屏：从桌面开场 → 展示源数据 → 模拟TRAE界面 → 运行SKILL（录制运行过程）→ 展示输出结果 → 保存MP4

触发方式：用户输入 "执行XXX，并完成自动录屏" 时调用此脚本
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
# 配置区
# ========================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_SCRIPT = os.path.join(SCRIPT_DIR, "..", "full_process.py")
TARGET_COMMAND = "执行4G5G指标自动通报"
LIBS_PATH = os.path.join(SCRIPT_DIR, "..", "libs")

OUTPUT_DIR = r"C:\zhibiao\pic_result"
FPS = 15

# 各步停留秒数
DELAY_INTRO = 3
DELAY_SOURCE = 4
DELAY_TRAE_DISPLAY = 4
DELAY_PER_RESULT = 5
DELAY_END = 3

# Win32 窗口置顶 & 最大化
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9
SW_MAXIMIZE = 3


# ========================================================================
# 录屏核心
# ========================================================================
class ScreenRecorder:
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

    def stop(self):
        self.recording = False
        if self.thread:
            self.thread.join(timeout=5)
        if self.writer:
            self.writer.release()
        self.sct.close()


# ========================================================================
# 工具函数
# ========================================================================
def bring_window_to_front(pid=None, maximize=False):
    """将窗口置顶，可选最大化"""
    try:
        user32 = ctypes.windll.user32

        def enum_handler(hwnd, _):
            found_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
            if pid is None or found_pid.value == pid:
                if user32.IsWindowVisible(hwnd):
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    if maximize:
                        user32.ShowWindow(hwnd, SW_MAXIMIZE)
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    user32.SetForegroundWindow(hwnd)

        cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_handler)
        user32.EnumWindows(cb, 0)
    except Exception:
        pass
    time.sleep(0.3)


def open_file_on_top(filepath, maximize=True):
    """打开文件并置顶，默认最大化窗口"""
    if not os.path.exists(filepath):
        return False
    try:
        os.startfile(filepath)
        time.sleep(1.5)
        bring_window_to_front(maximize=maximize)
        return True
    except Exception:
        return False


def open_folder_on_top(folder_path, maximize=True):
    """打开文件夹并置顶，默认最大化窗口"""
    if not os.path.exists(folder_path):
        return False
    try:
        proc = subprocess.Popen(["explorer", folder_path])
        time.sleep(1.5)
        bring_window_to_front(pid=proc.pid if proc else None, maximize=maximize)
        return True
    except Exception:
        return False


def find_latest_file(directory, prefix, suffix):
    if not os.path.exists(directory):
        return None
    cands = [f for f in os.listdir(directory) if f.startswith(prefix) and f.endswith(suffix)]
    if not cands:
        return None
    cands.sort(reverse=True)
    return os.path.join(directory, cands[0])


def show_trae_interface_and_run(target_command, target_script, libs_path):
    """
    打开CMD窗口模拟TRAE任务界面：
    先显示"用户输入指令"，然后真实执行SKILL脚本
    录屏会全程录制SKILL运行过程
    """
    python_exe = sys.executable
    inner_cmd = (
        f'@echo off && '
        f'title TRAE 任务界面 && '
        f'color 0A && '
        f'echo. && '
        f'echo ================================================================ && '
        f'echo   TRAE 任务界面                                                   && '
        f'echo ================================================================ && '
        f'echo. && '
        f'echo   用户输入： {target_command} && '
        f'echo. && '
        f'echo   [系统] 确认执行，正在运行...                                     && '
        f'echo. && '
        f'set PYTHONPATH={libs_path} && '
        f'"{python_exe}" "{target_script}"'
    )
    proc = subprocess.Popen(
        ["cmd", "/k", inner_cmd],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    time.sleep(1)
    bring_window_to_front(proc.pid if proc else None)
    return proc


def wait_for_skill_complete(output_dir, timeout=180):
    """等待SKILL执行完成（监控新生成的合并大图）"""
    # 记录启动前已有的合并大图文件
    existing = set()
    if os.path.exists(output_dir):
        existing = set(f for f in os.listdir(output_dir) if f.startswith("指标通报汇总图_") and f.endswith(".PNG"))

    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(output_dir):
            current = set(f for f in os.listdir(output_dir) if f.startswith("指标通报汇总图_") and f.endswith(".PNG"))
            new_files = current - existing
            if new_files:
                return True
        time.sleep(2)
    return False


# ========================================================================
# 主流程：全程录屏
# ========================================================================
def main():
    print("=" * 60)
    print("  Auto Demo Recorder v3.2")
    print("  全程录屏模式：SKILL运行过程也会被录制")
    print("=" * 60)
    print(f"  目标指令: {TARGET_COMMAND}")
    print(f"  目标脚本: {TARGET_SCRIPT}")

    video_path = os.path.join(
        OUTPUT_DIR, f"演示视频_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    )
    print(f"  视频输出: {video_path}\n")

    # 初始化录制器
    recorder = ScreenRecorder(video_path, fps=FPS)

    # ===== 步骤1: 开始录制 - 桌面开场 =====
    print("[步骤1] 开始录制 - 桌面开场")
    recorder.start()
    time.sleep(DELAY_INTRO)

    # ===== 步骤2: 展示源数据目录 =====
    print("[步骤2] 展示源数据目录")
    open_folder_on_top(r"C:\zhibiao\4G_source")
    time.sleep(DELAY_SOURCE)
    open_folder_on_top(r"C:\zhibiao\5G_source")
    time.sleep(DELAY_SOURCE)

    # ===== 步骤3: 模拟TRAE界面 + 运行SKILL（全程录制）=====
    print(f"[步骤3] TRAE界面输入指令: {TARGET_COMMAND}")
    print("  → 打开TRAE任务界面，显示用户输入指令")
    print("  → 开始运行SKILL脚本（录屏中...）")
    skill_proc = show_trae_interface_and_run(TARGET_COMMAND, TARGET_SCRIPT, LIBS_PATH)
    time.sleep(DELAY_TRAE_DISPLAY)

    # 等待SKILL执行完成（录屏持续录制运行过程）
    print("  → 等待SKILL执行完成（全程录制中）...")
    success = wait_for_skill_complete(OUTPUT_DIR, timeout=180)
    if success:
        print("  ✓ SKILL执行完成")
    else:
        print("  ⚠ SKILL执行超时")
    time.sleep(3)

    # ===== 步骤4: 依次展示输出结果（只展示最新一次的文件）=====
    print("[步骤4] 依次展示输出结果")
    result_steps = []

    # 提取最新时间戳（从合并大图文件名中获取）
    latest_ts = ""
    mg = find_latest_file(OUTPUT_DIR, "指标通报汇总图_", ".PNG")
    if mg:
        # 文件名格式: 指标通报汇总图_20260813_140626.PNG
        fname = os.path.basename(mg)
        parts = fname.rsplit(".", 1)[0].split("_")
        if len(parts) >= 2:
            latest_ts = f"_{parts[-2]}_{parts[-1]}"

    # 4G输出
    total_4g = find_latest_file(r"C:\zhibiao\4G_output", "4G总表_", ".xlsx")
    if total_4g:
        result_steps.append(("4G总表Excel", total_4g))
    r4g = find_latest_file(r"C:\zhibiao\4G_output", "4G指标通报计算结果_", ".xlsx")
    if r4g:
        result_steps.append(("4G计算结果Excel", r4g))

    # 5G输出
    total_5g = find_latest_file(r"C:\zhibiao\5G_output", "5G总表_", ".xlsx")
    if total_5g:
        result_steps.append(("5G总表Excel", total_5g))
    r5g = find_latest_file(r"C:\zhibiao\5G_output", "5G指标通报计算结果_", ".xlsx")
    if r5g:
        result_steps.append(("5G计算结果Excel", r5g))

    # 各小区组看板（只展示最新时间戳的）
    boards = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.endswith(".PNG") and "指标通报计算结果" in f
        and "汇总" not in f and "汇总图" not in f
        and (not latest_ts or latest_ts in f)
    ])
    for b in boards:
        result_steps.append((b, os.path.join(OUTPUT_DIR, b)))

    # 汇总看板
    sb = find_latest_file(OUTPUT_DIR, "汇总指标通报计算结果_", ".PNG")
    if sb:
        result_steps.append(("汇总看板", sb))

    # 合并大图
    if mg:
        result_steps.append(("合并大图", mg))

    # 文字通报（前2个，按最新排序）
    txts = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".txt") and "文字通报" in f])
    for t in txts[:2]:
        result_steps.append((t, os.path.join(OUTPUT_DIR, t)))

    # 逐一打开并置顶
    for idx, (label, filepath) in enumerate(result_steps, 1):
        print(f"  [4.{idx}] {label}")
        open_file_on_top(filepath)
        time.sleep(DELAY_PER_RESULT)

    # ===== 步骤5: 结束录制 =====
    print("[步骤5] 结束录制")
    time.sleep(DELAY_END)
    recorder.stop()

    print("\n" + "=" * 60)
    print(f"✓ 全程录屏完成！")
    print(f"  视频: {video_path}")
    print(f"  参数: {recorder.width}x{recorder.height} @ {FPS}fps")
    print("=" * 60)

    # 自动播放视频
    if os.path.exists(video_path):
        print(f"\n自动播放视频...")
        os.startfile(video_path)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n出错: {e}")
        import traceback
        traceback.print_exc()
