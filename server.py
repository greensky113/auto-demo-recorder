# -*- coding: utf-8 -*-
"""
Auto Demo Recorder - Web 控制面板后端
基于 Python 内置 http.server，零额外依赖（除录屏所需的 cv2/mss/numpy）
启动后访问 http://localhost:8765 即可使用
"""

import os
import sys
import json
import time
import threading
import subprocess
import ctypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse

# 录屏依赖
try:
    import numpy as np
    import cv2
    import mss
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# ========================================================================
# 路径配置
# ========================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_SCRIPT_DEFAULT = os.path.join(SCRIPT_DIR, "..", "full_process.py")
TARGET_COMMAND_DEFAULT = "执行4G5G指标自动通报"
LIBS_PATH = os.path.join(SCRIPT_DIR, "..", "libs")
OUTPUT_DIR = r"C:\zhibiao\pic_result"
FPS = 15

# Win32 窗口置顶
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9

HOST = "localhost"
PORT = 8765

# ========================================================================
# 全局状态
# ========================================================================
class RecorderState:
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class AppState:
    """全局应用状态（线程安全）"""
    def __init__(self):
        self.status = RecorderState.IDLE
        self.current_step = ""
        self.step_index = 0
        self.total_steps = 0
        self.start_time = None
        self.output_path = ""
        self.error_msg = ""
        self.manual_mode = False
        self.manual_done = threading.Event()
        self.recorder = None
        self.flow_thread = None
        self.config = {
            "target_script": TARGET_SCRIPT_DEFAULT,
            "target_command": TARGET_COMMAND_DEFAULT,
            "output_dir": OUTPUT_DIR,
            "fps": FPS,
            "mode": "auto",  # auto / manual
            "delay_intro": 3,
            "delay_source": 4,
            "delay_trae_input": 3,
            "delay_per_result": 5,
            "delay_end": 3,
        }

    def reset(self):
        self.status = RecorderState.IDLE
        self.current_step = ""
        self.step_index = 0
        self.total_steps = 0
        self.start_time = None
        self.output_path = ""
        self.error_msg = ""
        self.manual_done.clear()


state = AppState()


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
# 录制流程
# ========================================================================
def set_step(label, index, total):
    state.current_step = label
    state.step_index = index
    state.total_steps = total
    state.manual_done.clear()


def wait_step(label, auto_delay):
    """自动模式等待秒数；手动模式等用户点「下一步」"""
    set_step(label, state.step_index, state.total_steps)
    if state.manual_mode:
        state.manual_done.wait(timeout=600)  # 最多等10分钟
        state.manual_done.clear()
    else:
        time.sleep(auto_delay)


def run_skill_in_cmd(target_script, target_command, libs_path):
    inner_cmd = (
        f"@echo off && "
        f"title TRAE 任务界面 && "
        f"echo. && "
        f"echo ================================================================ && "
        f"echo   TRAE 任务界面                                                   && "
        f"echo ================================================================ && "
        f"echo. && "
        f"echo   用户输入： {target_command} && "
        f"echo. && "
        f"echo   [回车] 确认执行...                                              && "
        f"echo. && "
        f"set PYTHONPATH={libs_path} && "
        f'python "{target_script}"'
    )
    return subprocess.Popen(
        ["cmd", "/k", inner_cmd],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def run_flow(config):
    """完整录制流程（在后台线程中执行）"""
    try:
        cfg = config
        output_dir = cfg["output_dir"]
        video_path = os.path.join(
            output_dir, f"演示视频_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        state.output_path = video_path

        # 初始化录制器
        recorder = ScreenRecorder(video_path, fps=cfg["fps"])
        state.recorder = recorder

        total = 12  # 预估总步数
        state.total_steps = total
        state.step_index = 0

        # 步骤1: 开始录制
        set_step("准备开始录制", 1, total)
        recorder.start()
        wait_step("桌面开场画面", cfg["delay_intro"])

        # 步骤2: 源数据目录
        set_step("展示4G源数据目录", 2, total)
        open_folder_on_top(r"C:\zhibiao\4G_source")
        wait_step("4G源数据目录", cfg["delay_source"])

        set_step("展示5G源数据目录", 3, total)
        open_folder_on_top(r"C:\zhibiao\5G_source")
        wait_step("5G源数据目录", cfg["delay_source"])

        # 步骤3: 模拟TRAE界面
        set_step(f"TRAE界面输入指令: {cfg['target_command']}", 4, total)
        skill_proc = run_skill_in_cmd(cfg["target_script"], cfg["target_command"], LIBS_PATH)
        time.sleep(cfg["delay_trae_input"])
        bring_window_to_front(skill_proc.pid if skill_proc else None)
        wait_step("TRAE界面已输入指令", cfg["delay_trae_input"])

        # 等待SKILL执行完成
        set_step("等待SKILL执行完成...", 5, total)
        max_wait, waited = 180, 0
        while waited < max_wait:
            if state.status != RecorderState.RUNNING:
                break  # 被用户停止
            merged = find_latest_file(output_dir, "指标通报汇总图_", ".PNG")
            if merged:
                time.sleep(3)
                break
            time.sleep(2)
            waited += 2
        set_step("SKILL执行完成", 5, total)
        wait_step("SKILL执行完成", 2)

        # 步骤4: 展示结果
        result_steps = []
        total_4g = find_latest_file(r"C:\zhibiao\4G_output", "4G总表_", ".xlsx")
        if total_4g:
            result_steps.append(("4G总表Excel", total_4g))
        r4g = find_latest_file(r"C:\zhibiao\4G_output", "4G指标通报计算结果_", ".xlsx")
        if r4g:
            result_steps.append(("4G计算结果Excel", r4g))
        total_5g = find_latest_file(r"C:\zhibiao\5G_output", "5G总表_", ".xlsx")
        if total_5g:
            result_steps.append(("5G总表Excel", total_5g))
        r5g = find_latest_file(r"C:\zhibiao\5G_output", "5G指标通报计算结果_", ".xlsx")
        if r5g:
            result_steps.append(("5G计算结果Excel", r5g))

        boards = sorted([
            f for f in os.listdir(output_dir)
            if f.endswith(".PNG") and "指标通报计算结果" in f
            and "汇总" not in f and "汇总图" not in f
        ])
        for b in boards:
            result_steps.append((b, os.path.join(output_dir, b)))

        sb = find_latest_file(output_dir, "汇总指标通报计算结果_", ".PNG")
        if sb:
            result_steps.append(("汇总看板", sb))
        mg = find_latest_file(output_dir, "指标通报汇总图_", ".PNG")
        if mg:
            result_steps.append(("合并大图", mg))

        txts = sorted([f for f in os.listdir(output_dir) if f.endswith(".txt") and "文字通报" in f])
        for t in txts[:2]:
            result_steps.append((t, os.path.join(output_dir, t)))

        total = 5 + len(result_steps) + 1
        state.total_steps = total

        for idx, (label, filepath) in enumerate(result_steps, 6):
            set_step(f"展示: {label}", idx, total)
            open_file_on_top(filepath)
            wait_step(label, cfg["delay_per_result"])

        # 步骤5: 结束
        set_step("录制结束", total, total)
        wait_step("结束画面", cfg["delay_end"])
        recorder.stop()

        state.status = RecorderState.COMPLETED
        state.current_step = "录制完成"

    except Exception as e:
        state.status = RecorderState.ERROR
        state.error_msg = str(e)
        if state.recorder:
            try:
                state.recorder.stop()
            except Exception:
                pass


# ========================================================================
# HTTP 服务
# ========================================================================
class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默日志

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(html_bytes))
        self.end_headers()
        self.wfile.write(html_bytes)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            html_path = os.path.join(SCRIPT_DIR, "index.html")
            if os.path.exists(html_path):
                with open(html_path, "rb") as f:
                    self._send_html(f.read())
            else:
                self._send_json({"error": "index.html not found"}, 404)

        elif path == "/api/status":
            elapsed = 0
            if state.start_time and state.status == RecorderState.RUNNING:
                elapsed = int(time.time() - state.start_time)
            self._send_json({
                "status": state.status,
                "current_step": state.current_step,
                "step_index": state.step_index,
                "total_steps": state.total_steps,
                "elapsed": elapsed,
                "output_path": state.output_path,
                "error": state.error_msg,
                "manual_mode": state.manual_mode,
                "has_deps": HAS_DEPS,
            })

        elif path == "/api/config":
            self._send_json(state.config)

        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if path == "/api/start":
            if state.status == RecorderState.RUNNING:
                self._send_json({"error": "已在录制中"}, 400)
                return
            if not HAS_DEPS:
                self._send_json({"error": "缺少依赖库，请运行: pip install opencv-python mss numpy"}, 400)
                return

            # 更新配置
            if "mode" in data:
                state.config["mode"] = data["mode"]
            for key in ["target_script", "target_command", "output_dir",
                        "delay_intro", "delay_source", "delay_trae_input",
                        "delay_per_result", "delay_end"]:
                if key in data:
                    state.config[key] = data[key]

            state.manual_mode = (state.config["mode"] == "manual")
            state.reset()
            state.status = RecorderState.RUNNING
            state.start_time = time.time()

            # 在后台线程中启动录制流程
            state.flow_thread = threading.Thread(
                target=run_flow, args=(state.config.copy(),), daemon=True
            )
            state.flow_thread.start()

            self._send_json({"ok": True, "message": "录制已开始"})

        elif path == "/api/stop":
            if state.status != RecorderState.RUNNING:
                self._send_json({"error": "未在录制中"}, 400)
                return
            state.status = RecorderState.COMPLETED  # 让流程循环退出
            state.manual_done.set()  # 释放手动等待
            time.sleep(1)
            if state.recorder:
                try:
                    state.recorder.stop()
                except Exception:
                    pass
            state.current_step = "已手动停止"
            self._send_json({"ok": True, "message": "录制已停止"})

        elif path == "/api/next-step":
            if state.status != RecorderState.RUNNING:
                self._send_json({"error": "未在录制中"}, 400)
                return
            state.manual_done.set()  # 释放手动等待
            self._send_json({"ok": True, "message": "已进入下一步"})

        elif path == "/api/open-folder":
            folder = state.config["output_dir"]
            if os.path.exists(folder):
                os.startfile(folder)
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "目录不存在"}, 400)

        elif path == "/api/open-video":
            if state.output_path and os.path.exists(state.output_path):
                os.startfile(state.output_path)
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "视频文件不存在"}, 400)

        else:
            self._send_json({"error": "not found"}, 404)


def main():
    print("=" * 50)
    print("  Auto Demo Recorder - Web 控制面板")
    print(f"  访问: http://{HOST}:{PORT}")
    print("=" * 50)
    if not HAS_DEPS:
        print("\n  ⚠  缺少依赖库，请先安装:")
        print("  pip install opencv-python mss numpy\n")
    server = HTTPServer((HOST, PORT), APIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
