import os
import sys
import time
import json
import threading
import traceback
import datetime
import logging
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from capture import capture_window, find_template_in_window
from click import click_at_client, move_to_client, click_at_current_pos
from hwnd import get_game_hwnd, get_window_info
from utils import resource_path
logger = logging.getLogger("NTEautoCoffee")
class CoffeeCore:
    
    def __init__(self, hwnd, config, stop_event=None):
        self.hwnd = hwnd
        self.stop_event = stop_event or threading.Event()
        self.config = config
        self.cycle_count = 0
        self.start_time = None
        positions = config.get("positions", {})
        self.pos1 = tuple(positions.get("pos1", [960, 540]))
        self.pos2 = tuple(positions.get("pos2", [960, 540]))
        self.pos3 = tuple(positions.get("pos3", [960, 540]))
        self.pos4 = tuple(positions.get("pos4", [960, 540]))
        timings = config.get("timings", {})
        self.wait_after_pos1 = timings.get("wait_after_pos1", 8.0)
        self.wait_after_pos3 = timings.get("wait_after_pos3", 3.0)
        self.wait_after_pos4 = timings.get("wait_after_pos4", 5.0)
        self.click_interval = timings.get("click_interval", 0.3)
        self.detect_interval = timings.get("detect_interval", 0.1)
        template_cfg = config.get("template", {})
        self.template_path = resource_path(template_cfg.get("path", "images/three_yellow_stars.png"))
        self.template_threshold = template_cfg.get("threshold", 0.7)
        self.template_region = template_cfg.get("region", None)
        if self.template_region:
            self.template_region = tuple(self.template_region)
    def log(self, msg, level="info"):
        
        if level == "error":
            logger.error(msg)
        elif level == "warning":
            logger.warning(msg)
        elif level == "debug":
            logger.debug(msg)
        else:
            logger.info(msg)
    def wait_or_stop(self, seconds):
        
        elapsed = 0.0
        interval = 0.05
        while elapsed < seconds and not self.stop_event.is_set():
            time.sleep(min(interval, seconds - elapsed))
            elapsed += interval
        return not self.stop_event.is_set()
    def click_until_detected(self):
        
        self.log(f"开始在位置2连点，等待模板匹配...")
        while not self.stop_event.is_set():
            click_at_client(self.hwnd, self.pos2[0], self.pos2[1],
                           duration=0.15, pre_delay=0.03)
            found, max_val, center = find_template_in_window(
                self.hwnd,
                self.template_path,
                threshold=self.template_threshold,
                region=self.template_region
            )
            if found:
                self.log(f"✓ 检测到模板! 匹配度={max_val:.3f}, 位置={center}")
                return True
            time.sleep(self.detect_interval)
        return False
    def run_cycle(self):
        
        self.log(f"步骤1: 点击位置1 {self.pos1}，等待 {self.wait_after_pos1} 秒")
        click_at_client(self.hwnd, self.pos1[0], self.pos1[1],
                       duration=0.2, pre_delay=0.05)
        if not self.wait_or_stop(self.wait_after_pos1):
            return False
        self.log(f"步骤2: 在位置2 {self.pos2} 连点，等待模板匹配")
        move_to_client(self.hwnd, self.pos2[0], self.pos2[1])
        if not self.click_until_detected():
            self.log("步骤2被中断")
            return False
        self.log("步骤2完成，等待1秒...")
        if not self.wait_or_stop(1.0):
            return False
        self.log(f"步骤3: 点击位置3 {self.pos3}，等待 {self.wait_after_pos3} 秒")
        click_at_client(self.hwnd, self.pos3[0], self.pos3[1],
                       duration=0.2, pre_delay=0.05)
        if not self.wait_or_stop(self.wait_after_pos3):
            return False
        self.log(f"步骤4: 点击位置4 {self.pos4}，等待 {self.wait_after_pos4} 秒")
        click_at_client(self.hwnd, self.pos4[0], self.pos4[1],
                       duration=0.2, pre_delay=0.05)
        if not self.wait_or_stop(self.wait_after_pos4):
            return False
        self.cycle_count += 1
        elapsed = (datetime.datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        self.log(f"✓ 第 {self.cycle_count} 次循环完成 (运行时间: {elapsed:.0f} 秒)")
        return True
    def run(self):
        
        if not self.hwnd or not self._is_hwnd_valid():
            self.log("[错误] 无效的游戏窗口句柄")
            return
        info = get_window_info(self.hwnd)
        if info:
            self.log(f"游戏窗口: {info['title']} ({info['client_width']}x{info['client_height']})")
        if not os.path.exists(self.template_path):
            self.log(f"[错误] 模板图片不存在: {self.template_path}")
            self.log("请将三个黄色星星的截图保存到该路径，或在 config.json 中修改 template.path")
            return
        self.log("=" * 50)
        self.log("异环自动咖啡脚本 启动")
        self.log(f"  位置1: {self.pos1}  位置2: {self.pos2}")
        self.log(f"  位置3: {self.pos3}  位置4: {self.pos4}")
        self.log(f"  模板: {self.template_path}  阈值: {self.template_threshold}")
        self.log(f"  按 Ctrl+C 或设置 stop_event 停止")
        self.log("=" * 50)
        self.start_time = datetime.datetime.now()
        try:
            while not self.stop_event.is_set():
                if not self.run_cycle():
                    break
        except KeyboardInterrupt:
            self.log("收到 Ctrl+C，停止脚本")
        except Exception as e:
            self.log(f"[错误] 脚本异常: {e}")
            traceback.print_exc()
        finally:
            total_time = (datetime.datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            self.log("=" * 50)
            self.log(f"脚本结束。共完成 {self.cycle_count} 次循环，运行 {total_time:.0f} 秒")
            self.log("=" * 50)
    def _is_hwnd_valid(self):
        
        import win32gui
        return win32gui.IsWindow(self.hwnd)
def load_config(config_path=None):
    
    if config_path is None:
        config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[警告] 加载配置文件失败: {e}，使用默认配置")
    return {
        "positions": {
            "pos1": [960, 540], "pos2": [960, 540],
            "pos3": [960, 540], "pos4": [960, 540]
        },
        "timings": {
            "wait_after_pos1": 8.0, "wait_after_pos3": 3.0,
            "wait_after_pos4": 5.0, "click_interval": 0.3, "detect_interval": 0.1
        },
        "template": {"path": "images/three_yellow_stars.png", "threshold": 0.7, "region": None}
    }
