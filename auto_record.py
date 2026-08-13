# -*- coding: utf-8 -*-
"""
Auto Demo Recorder v3.1 - auto_record.py
两阶段自动录屏：
  阶段1: 正常运行目标SKILL（生成所有输出文件）
  阶段2: SKILL完成后自动启动录屏（模拟TRAE界面 → 展示所有结果 → 保存MP4）

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

# 录屏展示阶段每步停留秒数
DELAY_INTRO = 3
DELAY_SOURCE = 4
DELAY_TRAE_DISPLAY = 4
DELAY_PER_RESULT = 5
DELAY_END = 3

# Win32 窗口置顶
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9


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
def bring_window_to_front(pid=None):
    try:
        user32 = ctypes.windll.user32

        def enum_handler(hwnd, _):
            found_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
            if pid is None or found_pid.value == pid:
                if user32.IsWindowVisible(hwnd):
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    user32.SetForegroundWindow(hwnd)

        cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_handler)
        user32.EnumWindows(cb, 0)
    except Exception:
        pass
    time.sleep(0.3)


def open_file_on_top(filepath):
    if not os.path.exists(filepath):
        return False
    try:
        os.startfile(filepath)
        time.sleep(1.2)
        bring_window_to_front()
        return True
    except Exception:
        return False


def open_folder_on_top(folder_path):
    if not os.path.exists(folder_path):
        return False
    try:
        proc = subprocess.Popen(["explorer", folder_path])
        time.sleep(1.5)
        bring_window_to_front(proc.pid if proc else None)
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


# ========================================================================
# 阶段1: 运行目标SKILL
# ========================================================================
def run_skill(target_script, libs_path):
    """正常运行目标SKILL脚本，等待完成"""
    print("\n" + "=" * 60)
    print("  阶段1: 运行目标SKILL")
    print("=" * 60)

    env = os.environ.copy()
    if libs_path and os.path.exists(libs_path):
        env["PYTHONPATH"] = libs_path

    proc = subprocess.Popen(
        [sys.executable, target_script],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # 实时输出SKILL运行日志
    for line in proc.stdout:
        print(f"  {line}", end="")

    proc.wait()
    exit_code = proc.returncode
    print(f"\n  SKILL执行完成，退出码: {exit_code}")
    return exit_code == 0


# ========================================================================
# 阶段2: 自动录屏展示
# ========================================================================
def show_trae_interface(target_command):
    """打开CMD窗口模拟TRAE任务界面，展示用户输入的指令"""
    inner_cmd = (
        f"@echo off && "
        f"title TRAE 任务界面 && "
        f"color 0A && "
        f"echo. && "
        f"echo ================================================================ && "
        f"echo   TRAE 任务界面                                                   && "
        f"echo ================================================================ && "
        f"echo. && "
        f"echo   用户输入： {target_command} && "
        f"echo. && "
        f"echo   [系统] 正在执行...                                              && "
        f"echo. && "
        f"echo   [系统] 执行完成！已生成所有输出文件。                            && "
        f"echo. && "
        f"echo   下面展示输出结果...                                              && "
        f"echo. && "
        f"pause"
    )
    proc = subprocess.Popen(
        ["cmd", "/k", inner_cmd],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    time.sleep(1)
    bring_window_to_front(proc.pid if proc else None)
    return proc


def run_recording(target_command, output_dir):
    """阶段2: 启动录屏，模拟TRAE界面，展示所有输出结果"""
    print("\n" + "=" * 60)
    print("  阶段2: 自动录屏展示")
    print("=" * 60)

    video_path = os.path.join(
        output_dir, f"演示视频_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    )
    print(f"  视频输出: {video_path}")

    # 初始化录制器
    recorder = ScreenRecorder(video_path, fps=FPS)

    # 开始录制
    print("\n  [步骤1] 开始录制 - 桌面开场")
    recorder.start()
    time.sleep(DELAY_INTRO)

    # 展示源数据目录
    print("  [步骤2] 展示源数据目录")
    open_folder_on_top(r"C:\zhibiao\4G_source")
    time.sleep(DELAY_SOURCE)
    open_folder_on_top(r"C:\zhibiao\5G_source")
    time.sleep(DELAY_SOURCE)

    # 模拟TRAE任务界面
    print(f"  [步骤3] 展示TRAE任务界面: {target_command}")
    trae_proc = show_trae_interface(target_command)
    time.sleep(DELAY_TRAE_DISPLAY)

    # 展示所有输出结果（新窗口置顶覆盖）
    print("  [步骤4] 依次展示输出结果")
    result_steps = []

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

    # 各小区组看板
    boards = sorted([
        f for f in os.listdir(output_dir)
        if f.endswith(".PNG") and "指标通报计算结果" in f
        and "汇总" not in f and "汇总图" not in f
    ])
    for b in boards:
        result_steps.append((b, os.path.join(output_dir, b)))

    # 汇总看板
    sb = find_latest_file(output_dir, "汇总指标通报计算结果_", ".PNG")
    if sb:
        result_steps.append(("汇总看板", sb))

    # 合并大图
    mg = find_latest_file(output_dir, "指标通报汇总图_", ".PNG")
    if mg:
        result_steps.append(("合并大图", mg))

    # 文字通报（前2个）
    txts = sorted([f for f in os.listdir(output_dir) if f.endswith(".txt") and "文字通报" in f])
    for t in txts[:2]:
        result_steps.append((t, os.path.join(output_dir, t)))

    # 逐一打开并置顶
    for idx, (label, filepath) in enumerate(result_steps, 1):
        print(f"    [4.{idx}] {label}")
        open_file_on_top(filepath)
        time.sleep(DELAY_PER_RESULT)

    # 结束录制
    print("  [步骤5] 结束录制")
    time.sleep(DELAY_END)
    recorder.stop()

    print("\n" + "=" * 60)
    print(f"  ✓ 录屏完成！")
    print(f"  视频: {video_path}")
    print(f"  参数: {recorder.width}x{recorder.height} @ {FPS}fps")
    print("=" * 60)
    return video_path


# ========================================================================
# 主入口
# ========================================================================
def main():
    """两阶段执行：先运行SKILL，再自动录屏"""
    print("=" * 60)
    print("  Auto Demo Recorder v3.1")
    print("  模式: 先执行SKILL → 再自动录屏")
    print("=" * 60)
    print(f"  目标指令: {TARGET_COMMAND}")
    print(f"  目标脚本: {TARGET_SCRIPT}")

    # 阶段1: 运行SKILL
    success = run_skill(TARGET_SCRIPT, LIBS_PATH)
    if not success:
        print("\n  ⚠ SKILL执行失败，跳过录屏")
        return

    # 短暂停顿
    print("\n  等待3秒后开始录屏...")
    time.sleep(3)

    # 阶段2: 自动录屏
    video_path = run_recording(TARGET_COMMAND, OUTPUT_DIR)

    # 自动打开视频
    if video_path and os.path.exists(video_path):
        print(f"\n  自动播放视频: {video_path}")
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
