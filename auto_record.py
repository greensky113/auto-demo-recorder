# -*- coding: utf-8 -*-
"""
Auto Demo Recorder v3.3 - auto_record.py
全程录屏 + 实时字幕：从桌面开场 → 展示源数据 → 模拟TRAE界面 → 运行SKILL → 展示输出结果 → 保存MP4

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
from ctypes import windll
import ctypes
from PIL import Image, ImageDraw, ImageFont

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
DELAY_SOURCE = 5
DELAY_TRAE_DISPLAY = 5
DELAY_PER_RESULT = 8       # 每个结果文件展示时间
DELAY_EXCEL_RESULT = 10    # Excel文件额外等待（打开较慢）
DELAY_END = 3

# 文件打开重试
MAX_OPEN_RETRIES = 3
OPEN_WAIT = 2.0             # 每次重试等待秒数

# Win32 窗口置顶 & 最大化
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9
SW_MAXIMIZE = 3

# 字幕字体
FONT_PATHS = [
    r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",     # 黑体
    r"C:\Windows\Fonts\simsun.ttc",     # 宋体
]


# ========================================================================
# 录屏核心（含字幕叠加）
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

        # 字幕系统
        self.current_subtitle = ""
        self._subtitle_lock = threading.Lock()
        self._font = self._load_font()

    def _load_font(self):
        """加载中文字体"""
        for fp in FONT_PATHS:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, 28)
                except Exception:
                    continue
        return ImageFont.load_default()

    def set_subtitle(self, text):
        """设置当前字幕"""
        with self._subtitle_lock:
            self.current_subtitle = text

    def clear_subtitle(self):
        """清除字幕"""
        with self._subtitle_lock:
            self.current_subtitle = ""

    def _draw_subtitle(self, frame):
        """在帧上绘制字幕（半透明底栏 + 白色文字）"""
        subtitle = self.current_subtitle
        if not subtitle:
            return frame

        # 转为PIL图像绘制中文
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil, "RGBA")

        # 计算文字尺寸
        bbox = draw.textbbox((0, 0), subtitle, font=self._font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # 底部字幕栏位置
        bar_h = text_h + 30
        bar_y = self.height - bar_h - 20
        bar_x = (self.width - text_w) // 2 - 20
        bar_w = text_w + 40

        # 绘制半透明黑色底栏
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
            radius=8,
            fill=(0, 0, 0, 200)
        )

        # 绘制白色文字
        text_x = bar_x + 20
        text_y = bar_y + 15
        draw.text((text_x, text_y), subtitle, fill=(255, 255, 255, 255), font=self._font)

        # 转回OpenCV格式
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    def _capture_loop(self):
        monitor = self.sct.monitors[1]
        while self.recording:
            img = self.sct.grab(monitor)
            frame = np.array(img)[:, :, :3]
            # 叠加字幕
            frame = self._draw_subtitle(frame)
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


def get_foreground_window_title():
    """获取当前前台窗口标题"""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def open_file_on_top(filepath, maximize=True, is_excel=False):
    """打开文件并置顶最大化，带重试机制确保窗口成功打开"""
    if not os.path.exists(filepath):
        print(f"    [警告] 文件不存在: {filepath}")
        return False

    fname = os.path.basename(filepath)

    for attempt in range(1, MAX_OPEN_RETRIES + 1):
        try:
            os.startfile(filepath)
            # Excel打开较慢，等待更久
            wait_time = OPEN_WAIT + (2 if is_excel else 0)
            time.sleep(wait_time)
            bring_window_to_front(maximize=maximize)

            # 检查窗口是否成功打开（前台窗口标题不为空且不是桌面）
            title = get_foreground_window_title()
            if title and title != "Program Manager":
                print(f"    [OK] {fname} 已打开 (第{attempt}次尝试)")
                return True
            else:
                print(f"    [重试 {attempt}/{MAX_OPEN_RETRIES}] {fname} 窗口未检测到，重试中...")
        except Exception as e:
            print(f"    [重试 {attempt}/{MAX_OPEN_RETRIES}] {fname} 打开异常: {e}")

    print(f"    [警告] {fname} 经{MAX_OPEN_RETRIES}次重试仍未成功打开")
    return False


def open_folder_on_top(folder_path, maximize=True):
    """打开文件夹并置顶最大化，带重试机制"""
    if not os.path.exists(folder_path):
        return False

    for attempt in range(1, MAX_OPEN_RETRIES + 1):
        try:
            proc = subprocess.Popen(["explorer", folder_path])
            time.sleep(OPEN_WAIT)
            bring_window_to_front(pid=proc.pid if proc else None, maximize=maximize)

            title = get_foreground_window_title()
            if title and title != "Program Manager":
                return True
            else:
                print(f"    [重试 {attempt}/{MAX_OPEN_RETRIES}] 文件夹窗口未检测到...")
        except Exception:
            pass

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
    """打开CMD窗口模拟TRAE任务界面，然后真实执行SKILL脚本"""
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
    bring_window_to_front(proc.pid if proc else None, maximize=True)
    return proc


def wait_for_skill_complete(output_dir, timeout=180):
    """等待SKILL执行完成（监控新生成的合并大图）"""
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
# 主流程：全程录屏 + 字幕
# ========================================================================
def main():
    print("=" * 60)
    print("  Auto Demo Recorder v3.3")
    print("  全程录屏 + 实时字幕")
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
    recorder.set_subtitle("4G/5G指标自动通报 - 演示开始")
    recorder.start()
    time.sleep(DELAY_INTRO)

    # ===== 步骤2: 展示源数据目录 =====
    print("[步骤2] 展示源数据目录")
    recorder.set_subtitle("步骤1：查看4G源数据文件")
    open_folder_on_top(r"C:\zhibiao\4G_source")
    time.sleep(DELAY_SOURCE)

    recorder.set_subtitle("步骤2：查看5G源数据文件")
    open_folder_on_top(r"C:\zhibiao\5G_source")
    time.sleep(DELAY_SOURCE)

    # ===== 步骤3: 模拟TRAE界面 + 运行SKILL =====
    print(f"[步骤3] TRAE界面输入指令: {TARGET_COMMAND}")
    recorder.set_subtitle(f"步骤3：在TRAE任务界面输入指令\n「{TARGET_COMMAND}」")
    print("  → 打开TRAE任务界面，显示用户输入指令")
    print("  → 开始运行SKILL脚本（录屏中...）")
    skill_proc = show_trae_interface_and_run(TARGET_COMMAND, TARGET_SCRIPT, LIBS_PATH)
    time.sleep(DELAY_TRAE_DISPLAY)

    # 等待SKILL执行完成
    recorder.set_subtitle("步骤4：SKILL正在执行中...\n自动处理4G/5G指标数据、生成汇总表和可视化看板")
    print("  → 等待SKILL执行完成（全程录制中）...")
    success = wait_for_skill_complete(OUTPUT_DIR, timeout=180)
    if success:
        print("  ✓ SKILL执行完成")
        recorder.set_subtitle("SKILL执行完成！\n已生成总表、计算结果和可视化看板")
    else:
        print("  ⚠ SKILL执行超时")
        recorder.set_subtitle("SKILL执行超时")
    time.sleep(3)

    # ===== 步骤4: 依次展示输出结果 =====
    print("[步骤4] 依次展示输出结果")
    recorder.set_subtitle("步骤5：展示输出结果")
    time.sleep(2)

    result_steps = []

    # 提取最新时间戳
    latest_ts = ""
    mg = find_latest_file(OUTPUT_DIR, "指标通报汇总图_", ".PNG")
    if mg:
        fname = os.path.basename(mg)
        parts = fname.rsplit(".", 1)[0].split("_")
        if len(parts) >= 2:
            latest_ts = f"_{parts[-2]}_{parts[-1]}"

    # 4G输出（is_excel=True，等待更久）
    total_4g = find_latest_file(r"C:\zhibiao\4G_output", "4G总表_", ".xlsx")
    if total_4g:
        result_steps.append(("4G总表Excel", total_4g, True))
    r4g = find_latest_file(r"C:\zhibiao\4G_output", "4G指标通报计算结果_", ".xlsx")
    if r4g:
        result_steps.append(("4G指标通报计算结果", r4g, True))

    # 5G输出
    total_5g = find_latest_file(r"C:\zhibiao\5G_output", "5G总表_", ".xlsx")
    if total_5g:
        result_steps.append(("5G总表Excel", total_5g, True))
    r5g = find_latest_file(r"C:\zhibiao\5G_output", "5G指标通报计算结果_", ".xlsx")
    if r5g:
        result_steps.append(("5G指标通报计算结果", r5g, True))

    # 各小区组看板（只展示最新时间戳的）
    boards = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.endswith(".PNG") and "指标通报计算结果" in f
        and "汇总" not in f and "汇总图" not in f
        and (not latest_ts or latest_ts in f)
    ])
    for b in boards:
        # 提取小区组名称
        group_name = b.split("指标通报计算结果")[0].replace("26年6月滇超-", "")
        result_steps.append((f"{group_name}看板", os.path.join(OUTPUT_DIR, b), False))

    # 汇总看板
    sb = find_latest_file(OUTPUT_DIR, "汇总指标通报计算结果_", ".PNG")
    if sb:
        result_steps.append(("汇总看板", sb, False))

    # 合并大图
    if mg:
        result_steps.append(("合并大图（4G+5G汇总）", mg, False))

    # 文字通报（前2个）
    txts = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".txt") and "文字通报" in f])
    for t in txts[:2]:
        group_name = t.split("文字通报")[0].strip("[]").replace("26年6月滇超-", "")
        result_steps.append((f"{group_name}文字通报", os.path.join(OUTPUT_DIR, t), False))

    # 逐一打开并置顶（带重试 + 字幕）
    for idx, (label, filepath, is_excel) in enumerate(result_steps, 1):
        subtitle_text = f"步骤5.{idx}：{label}"
        print(f"  [4.{idx}] {label}")
        recorder.set_subtitle(subtitle_text)

        opened = open_file_on_top(filepath, maximize=True, is_excel=is_excel)
        if not opened:
            recorder.set_subtitle(f"{label} - 打开失败，跳过")
            time.sleep(2)
            continue

        # 展示时间：Excel更长
        display_time = DELAY_EXCEL_RESULT if is_excel else DELAY_PER_RESULT
        time.sleep(display_time)

    # ===== 步骤5: 结束录制 =====
    print("[步骤5] 结束录制")
    recorder.set_subtitle("演示结束\n4G/5G指标自动通报 - 全流程完成")
    time.sleep(DELAY_END)
    recorder.clear_subtitle()
    time.sleep(0.5)
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
