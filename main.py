import sys
import os
import ctypes
import json
import threading
import traceback
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False
if not is_admin():
    python_exe = sys.executable
    script_path = os.path.abspath(sys.argv[0])
    params = [script_path] + sys.argv[1:]
    cmd_line = " ".join([f'"{a}"' if ' ' in a else a for a in params])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", python_exe, cmd_line, None, 1)
    sys.exit(0)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox, QMessageBox,
    QComboBox, QGridLayout, QLineEdit, QFileDialog, QCheckBox,
    QTabWidget, QFrame, QPlainTextEdit
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont
try:
    import keyboard as _keyboard_lib
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    print("[警告] 未安装 keyboard 库，全局热键不可用。请执行: pip install keyboard")
from coffee_core import CoffeeCore, load_config
from hwnd import find_window_by_title, set_locked_hwnd, get_game_hwnd, get_window_info, clear_locked_hwnd
from log_handler import setup_logging, get_ui_handler
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
_logger, _ui_handler = setup_logging()
class HotkeyManager(QObject):
    
    hotkey_triggered = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._registered = {}
        self._last_trigger = {}
    @staticmethod
    def _normalize(shortcut_str):
        parts = shortcut_str.strip().split('+')
        normalized = []
        for p in parts:
            p = p.strip().lower()
            if p in ('ctrl', 'control'):
                normalized.append('ctrl')
            elif p == 'alt':
                normalized.append('alt')
            elif p == 'shift':
                normalized.append('shift')
            else:
                normalized.append(p)
        return '+'.join(normalized)
    def register_hotkey(self, name, shortcut_str):
        if name in self._registered:
            self.unregister_hotkey(name)
        if not HAS_KEYBOARD:
            return False
        try:
            hotkey = self._normalize(shortcut_str)
            _keyboard_lib.add_hotkey(hotkey, lambda n=name: self._on_trigger(n), suppress=False)
            self._registered[name] = shortcut_str
            return True
        except Exception as e:
            print(f"[警告] 注册热键失败: {shortcut_str} ({e})")
            return False
    def unregister_hotkey(self, name):
        if name in self._registered:
            try:
                shortcut_str = self._registered.pop(name)
                _keyboard_lib.remove_hotkey(shortcut_str)
            except:
                pass
    def clear_all(self):
        for name in list(self._registered.keys()):
            self.unregister_hotkey(name)
    def _on_trigger(self, name):
        import time as _time
        now = _time.time()
        if name in self._last_trigger and now - self._last_trigger[name] < 1.0:
            return
        self._last_trigger[name] = now
        self.hotkey_triggered.emit(name)
class CoffeeUI(QWidget):
    
    update_status_signal = pyqtSignal(str)
    update_cycle_signal = pyqtSignal(int)
    capture_pos_signal = pyqtSignal(str, int, int)
    def __init__(self):
        super().__init__()
        self.coffee_thread = None
        self.stop_event = None
        self.coffee_core = None
        self.config = load_config(CONFIG_FILE)
        self.capture_target = None
        self.is_paused = False
        self.hotkey_mgr = HotkeyManager(self)
        self.hotkey_mgr.hotkey_triggered.connect(self._on_hotkey)
        self.setup_ui()
        self.load_config_to_ui()
        self._register_hotkeys()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status_display)
        self.status_timer.start(500)
        self.update_status_signal.connect(self._set_status_text)
        self.update_cycle_signal.connect(self._set_cycle_text)
        self.capture_pos_signal.connect(self._on_capture_pos)
    def setup_ui(self):
        self.setWindowTitle("NTEautoCoffee - 异环自动咖啡")
        self.setMinimumSize(720, 650)
        self.resize(760, 700)
        self.setStyleSheet(self._get_style())
        outer = QVBoxLayout(self)
        outer.setSpacing(6)
        outer.setContentsMargins(10, 8, 10, 8)
        top_bar = QHBoxLayout()
        title = QLabel("☕ 异环自动咖啡脚本")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff9900;")
        top_bar.addWidget(title)
        top_bar.addStretch()
        self.lbl_window_info = QLabel("未锁定窗口")
        self.lbl_window_info.setObjectName("WinInfo")
        top_bar.addWidget(self.lbl_window_info)
        self.window_combo = QComboBox()
        self.window_combo.setMinimumWidth(200)
        self.window_combo.setFixedHeight(28)
        top_bar.addWidget(self.window_combo)
        btn_refresh = QPushButton("刷新")
        btn_refresh.setFixedHeight(28)
        btn_refresh.clicked.connect(self.refresh_windows)
        top_bar.addWidget(btn_refresh)
        self.btn_lock = QPushButton("锁定")
        self.btn_lock.setFixedHeight(28)
        self.btn_lock.clicked.connect(self.lock_window)
        top_bar.addWidget(self.btn_lock)
        outer.addLayout(top_bar)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #444;")
        outer.addWidget(sep)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        outer.addWidget(self.tabs)
        tab_pos = QWidget()
        tab_pos_layout = QVBoxLayout(tab_pos)
        tab_pos_layout.setSpacing(10)
        tab_pos_layout.setContentsMargins(12, 12, 12, 12)
        self.pos_inputs = {}
        pos_labels = {
            "pos1": "位置1 — 开始制作咖啡（点击后等待8秒）",
            "pos2": "位置2 — 连续点击直到出现三个黄色星星",
            "pos3": "位置3 — 检测到星星后点击（等待3秒）",
            "pos4": "位置4 — 收尾点击（等待5秒后循环）",
        }
        for key, desc in pos_labels.items():
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl_desc = QLabel(desc)
            lbl_desc.setMinimumWidth(250)
            lbl_desc.setStyleSheet("color: #ccc; font-size: 13px;")
            row.addWidget(lbl_desc)
            row.addWidget(QLabel("X"))
            x_spin = QSpinBox()
            x_spin.setRange(0, 3840)
            x_spin.setValue(960)
            x_spin.setFixedWidth(70)
            x_spin.setFixedHeight(26)
            row.addWidget(x_spin)
            row.addWidget(QLabel("Y"))
            y_spin = QSpinBox()
            y_spin.setRange(0, 2160)
            y_spin.setValue(540)
            y_spin.setFixedWidth(70)
            y_spin.setFixedHeight(26)
            row.addWidget(y_spin)
            btn_cap = QPushButton("🎯")
            btn_cap.setFixedSize(38, 28)
            btn_cap.setToolTip(f"点击后按 F6 捕获鼠标位置到 {desc}")
            btn_cap.clicked.connect(lambda checked, k=key: self._start_capture_for(k))
            row.addWidget(btn_cap)
            row.addStretch()
            tab_pos_layout.addLayout(row)
            self.pos_inputs[key] = (x_spin, y_spin)
        cap_hint = QLabel("💡 点击 🎯 按钮后，将鼠标移到游戏中的目标位置，按 F6 即可自动填入坐标")
        cap_hint.setStyleSheet("color: #888; font-size: 12px; padding-top: 8px;")
        tab_pos_layout.addWidget(cap_hint)
        tab_pos_layout.addStretch()
        self.tabs.addTab(tab_pos, "📍 位置设置")
        tab_timing = QWidget()
        tab_timing_layout = QVBoxLayout(tab_timing)
        tab_timing_layout.setSpacing(12)
        tab_timing_layout.setContentsMargins(12, 12, 12, 12)
        time_group = QGroupBox("各步骤等待时间")
        time_grid = QGridLayout(time_group)
        time_grid.setSpacing(8)
        self.time_inputs = {}
        time_labels = [
            ("wait_after_pos1", "步骤1 点击后等待", 8.0, "秒"),
            ("wait_after_pos3", "步骤3 点击后等待", 3.0, "秒"),
            ("wait_after_pos4", "步骤4 点击后等待", 5.0, "秒"),
        ]
        for i, (key, label, default, unit) in enumerate(time_labels):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("font-size: 13px; color: #ccc;")
            time_grid.addWidget(lbl, i, 0)
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 999.0)
            spin.setValue(default)
            spin.setDecimals(1)
            spin.setFixedWidth(80)
            spin.setFixedHeight(26)
            time_grid.addWidget(spin, i, 1)
            time_grid.addWidget(QLabel(unit), i, 2)
            self.time_inputs[key] = spin
        tab_timing_layout.addWidget(time_group)
        click_group = QGroupBox("位置2 连点参数")
        click_grid = QGridLayout(click_group)
        click_grid.setSpacing(8)
        lbl_ci = QLabel("点击间隔:")
        lbl_ci.setStyleSheet("font-size: 13px; color: #ccc;")
        click_grid.addWidget(lbl_ci, 0, 0)
        self.click_interval_spin = QDoubleSpinBox()
        self.click_interval_spin.setRange(0.05, 2.0)
        self.click_interval_spin.setValue(0.1)
        self.click_interval_spin.setSingleStep(0.05)
        self.click_interval_spin.setDecimals(2)
        self.click_interval_spin.setFixedWidth(80)
        self.click_interval_spin.setFixedHeight(26)
        click_grid.addWidget(self.click_interval_spin, 0, 1)
        click_grid.addWidget(QLabel("秒（每次点击之间的间隔）"), 0, 2)
        lbl_di = QLabel("检测间隔:")
        lbl_di.setStyleSheet("font-size: 13px; color: #ccc;")
        click_grid.addWidget(lbl_di, 1, 0)
        self.detect_interval_spin = QDoubleSpinBox()
        self.detect_interval_spin.setRange(0.05, 2.0)
        self.detect_interval_spin.setValue(0.1)
        self.detect_interval_spin.setSingleStep(0.05)
        self.detect_interval_spin.setDecimals(2)
        self.detect_interval_spin.setFixedWidth(80)
        self.detect_interval_spin.setFixedHeight(26)
        click_grid.addWidget(self.detect_interval_spin, 1, 1)
        click_grid.addWidget(QLabel("秒（截图+匹配检测间隔）"), 1, 2)
        tab_timing_layout.addWidget(click_group)
        tab_timing_layout.addStretch()
        self.tabs.addTab(tab_timing, "⏱ 时间设置")
        tab_tpl = QWidget()
        tab_tpl_layout = QVBoxLayout(tab_tpl)
        tab_tpl_layout.setSpacing(12)
        tab_tpl_layout.setContentsMargins(12, 12, 12, 12)
        tpl_group = QGroupBox("模板匹配设置（三个黄色星星）")
        tpl_inner = QGridLayout(tpl_group)
        tpl_inner.setSpacing(8)
        lbl_path = QLabel("模板图片:")
        lbl_path.setStyleSheet("font-size: 13px; color: #ccc;")
        tpl_inner.addWidget(lbl_path, 0, 0)
        path_row = QHBoxLayout()
        self.template_path_edit = QLineEdit("images/three_yellow_stars.png")
        self.template_path_edit.setFixedHeight(26)
        self.template_path_edit.setMinimumWidth(280)
        path_row.addWidget(self.template_path_edit)
        btn_browse = QPushButton("浏览...")
        btn_browse.setFixedHeight(26)
        btn_browse.clicked.connect(self.browse_template)
        path_row.addWidget(btn_browse)
        tpl_inner.addLayout(path_row, 0, 1, 1, 2)
        lbl_th = QLabel("匹配阈值:")
        lbl_th.setStyleSheet("font-size: 13px; color: #ccc;")
        tpl_inner.addWidget(lbl_th, 1, 0)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.30, 0.99)
        self.threshold_spin.setValue(0.70)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setFixedWidth(80)
        self.threshold_spin.setFixedHeight(26)
        tpl_inner.addWidget(self.threshold_spin, 1, 1)
        tpl_inner.addWidget(QLabel("(0.3~0.99，越高越严格，推荐 0.90)"), 1, 2)
        tab_tpl_layout.addWidget(tpl_group)
        hint_group = QGroupBox("使用提示")
        hint_layout = QVBoxLayout(hint_group)
        hints = [
            "1. 在游戏中截取「三个黄色星星」出现的画面",
            "2. 裁剪出仅包含三个星星的局部区域保存为 PNG",
            "3. 确保截图窗口尺寸和游戏窗口一致，否则坐标会偏移",
            "4. 阈值建议从 0.70 开始，匹配不上则降低，误匹配则提高",
        ]
        for h in hints:
            lbl = QLabel(h)
            lbl.setStyleSheet("color: #999; font-size: 12px;")
            hint_layout.addWidget(lbl)
        tab_tpl_layout.addWidget(hint_group)
        tab_tpl_layout.addStretch()
        self.tabs.addTab(tab_tpl, "🎯 图像识别")
        log_header = QHBoxLayout()
        log_header.setContentsMargins(0, 2, 0, 0)
        log_title = QLabel("📋 运行日志")
        log_title.setStyleSheet("color: #ff9900; font-size: 13px; font-weight: bold;")
        log_header.addWidget(log_title)
        log_header.addStretch()
        btn_clear_log = QPushButton("清空日志")
        btn_clear_log.setFixedHeight(24)
        btn_clear_log.setStyleSheet("font-size: 12px; padding: 2px 10px;")
        btn_clear_log.clicked.connect(lambda: self.log_viewer.clear())
        log_header.addWidget(btn_clear_log)
        outer.addLayout(log_header)
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumBlockCount(2000)
        self.log_viewer.setFixedHeight(130)
        self.log_viewer.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0a0a15;
                color: #00ffcc;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 6px;
            }
        """)
        outer.addWidget(self.log_viewer)
        if _ui_handler:
            _ui_handler.new_log.connect(self._append_log)
        bottom_frame = QFrame()
        bottom_frame.setObjectName("BottomFrame")
        bottom_layout = QVBoxLayout(bottom_frame)
        bottom_layout.setSpacing(6)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        status_row = QHBoxLayout()
        self.status_label = QLabel("当前状态：待机")
        self.status_label.setObjectName("StatusLabel")
        status_row.addWidget(self.status_label)
        self.cycle_label = QLabel("循环: 0 次")
        self.cycle_label.setObjectName("CycleLabel")
        status_row.addWidget(self.cycle_label)
        self.hotkey_label = QLabel("F6=捕获坐标  F8=开始  F9=停止")
        self.hotkey_label.setStyleSheet("color: #888; font-size: 12px;")
        status_row.addWidget(self.hotkey_label)
        status_row.addStretch()
        bottom_layout.addLayout(status_row)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_start = QPushButton("▶  开始制作咖啡")
        self.btn_start.setObjectName("StartButton")
        self.btn_start.setMinimumHeight(36)
        self.btn_start.clicked.connect(self.start_coffee)
        btn_row.addWidget(self.btn_start)
        self.btn_stop = QPushButton("⏹  停止")
        self.btn_stop.setObjectName("StopButton")
        self.btn_stop.setMinimumHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_coffee)
        btn_row.addWidget(self.btn_stop)
        self.btn_save = QPushButton("💾 保存配置")
        self.btn_save.setMinimumHeight(36)
        self.btn_save.clicked.connect(self.save_config)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch()
        bottom_layout.addLayout(btn_row)
        outer.addWidget(bottom_frame)
    def _register_hotkeys(self):
        
        if not HAS_KEYBOARD:
            return
        self.hotkey_mgr.register_hotkey("start_pause", "f8")
        self.hotkey_mgr.register_hotkey("stop", "f9")
        self.hotkey_mgr.register_hotkey("capture_mouse", "f6")
        print("[热键] F6=捕获鼠标坐标  F8=开始/暂停  F9=停止")
    def _on_hotkey(self, name):
        
        if name == "start_pause":
            if self.coffee_thread and self.coffee_thread.is_alive():
                self._toggle_pause()
            else:
                self.start_coffee()
        elif name == "stop":
            self.stop_coffee()
        elif name == "capture_mouse":
            self._capture_current_mouse()
    def _toggle_pause(self):
        
        if not self.coffee_core:
            return
        if self.is_paused:
            self.is_paused = False
            self.coffee_core.stop_event.clear()
            self._set_status_text("运行中...")
            self.status_label.setStyleSheet("color: #00ff88; font-size: 15px; font-weight: bold;")
            print("[热键] 已恢复")
        else:
            self.is_paused = True
            self.coffee_core.stop_event.set()
            self._set_status_text("已暂停")
            self.status_label.setStyleSheet("color: #ffaa00; font-size: 15px; font-weight: bold;")
            print("[热键] 已暂停")
    def _capture_current_mouse(self):
        
        import win32gui as _wg
        hwnd = get_game_hwnd()
        if not hwnd:
            QTimer.singleShot(0, lambda: QMessageBox.warning(
                self, "捕获失败", "请先锁定游戏窗口！"))
            return
        cursor_screen = _wg.GetCursorPos()
        try:
            client_pt = _wg.ScreenToClient(hwnd, cursor_screen)
            cx, cy = client_pt[0], client_pt[1]
        except:
            cx, cy = cursor_screen[0], cursor_screen[1]
        print(f"[捕获] 屏幕坐标={cursor_screen} → 客户区坐标=({cx}, {cy})")
        if self.capture_target and self.capture_target in self.pos_inputs:
            x_spin, y_spin = self.pos_inputs[self.capture_target]
            x_spin.setValue(max(0, cx))
            y_spin.setValue(max(0, cy))
            self.capture_pos_signal.emit(self.capture_target, max(0, cx), max(0, cy))
            self.capture_target = None
        else:
            QTimer.singleShot(0, lambda: self._ask_capture_target(cx, cy))
    def _ask_capture_target(self, cx, cy):
        
        if cx < 0 or cy < 0:
            QMessageBox.warning(self, "坐标异常",
                f"捕获到负数坐标 ({cx}, {cy})，请确保鼠标在游戏窗口内。")
            return
        names = {
            "pos1": "位置1 (开始制作)",
            "pos2": "位置2 (连点区域)",
            "pos3": "位置3 (完成确认)",
            "pos4": "位置4 (收尾)",
        }
        msg = f"捕获到客户区坐标: ({cx}, {cy})\n\n请选择填入哪个位置:"
        for key, label in names.items():
            btn = QMessageBox.question(
                self, f"填入 {label}", f"{msg}\n\n→ 填入 {label} ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if btn == QMessageBox.Yes:
                x_spin, y_spin = self.pos_inputs[key]
                x_spin.setValue(max(0, cx))
                y_spin.setValue(max(0, cy))
                self._set_status_text(f"已填入{label}: ({max(0,cx)}, {max(0,cy)})")
                return
        self._set_status_text(f"捕获坐标 ({cx}, {cy}) 已忽略")
    def _start_capture_for(self, pos_key):
        
        self.capture_target = pos_key
        self._set_status_text(f"请将鼠标移到目标位置，然后按 F6...")
        QTimer.singleShot(5000, self._cancel_capture)
    def _cancel_capture(self):
        if self.capture_target:
            self.capture_target = None
            self._set_status_text("捕获已取消")
    def _on_capture_pos(self, pos_key, x, y):
        
        names = {
            "pos1": "位置1", "pos2": "位置2",
            "pos3": "位置3", "pos4": "位置4"
        }
        self._set_status_text(f"✓ {names.get(pos_key, pos_key)} 已更新为 ({x}, {y})")
    def refresh_windows(self):
        
        self.window_combo.clear()
        windows = find_window_by_title("异环")
        if not windows:
            windows = find_window_by_title("")
        for hwnd, title in windows:
            info = get_window_info(hwnd)
            if info:
                self.window_combo.addItem(
                    f"{title} ({info['client_width']}x{info['client_height']})",
                    hwnd
                )
        if self.window_combo.count() == 0:
            self.window_combo.addItem("未找到游戏窗口，请刷新", 0)
    def lock_window(self):
        
        hwnd = self.window_combo.currentData()
        if hwnd and hwnd != 0:
            set_locked_hwnd(hwnd)
            info = get_window_info(hwnd)
            if info:
                self.lbl_window_info.setText(
                    f"已锁定: {info['title']} ({info['client_width']}x{info['client_height']})"
                )
                self.lbl_window_info.setStyleSheet("color: #00ff00;")
                return
        self.lbl_window_info.setText("锁定失败")
        self.lbl_window_info.setStyleSheet("color: #ff4444;")
    def browse_template(self):
        
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模板图片", BASE_DIR,
            "图片文件 (*.png *.bmp *.jpg *.jpeg);;所有文件 (*.*)"
        )
        if path:
            self.template_path_edit.setText(path)
    def load_config_to_ui(self):
        
        positions = self.config.get("positions", {})
        for key, (x_spin, y_spin) in self.pos_inputs.items():
            pos = positions.get(key, [960, 540])
            x_spin.setValue(pos[0])
            y_spin.setValue(pos[1])
        timings = self.config.get("timings", {})
        for key, spin in self.time_inputs.items():
            spin.setValue(timings.get(key, 8.0))
        template = self.config.get("template", {})
        self.template_path_edit.setText(template.get("path", "images/three_yellow_stars.png"))
        self.threshold_spin.setValue(template.get("threshold", 0.7))
        self.click_interval_spin.setValue(timings.get("click_interval", 0.1))
        self.detect_interval_spin.setValue(timings.get("detect_interval", 0.1))
    def save_config(self):
        
        cfg = {
            "positions": {},
            "timings": {},
            "template": {}
        }
        for key, (x_spin, y_spin) in self.pos_inputs.items():
            cfg["positions"][key] = [x_spin.value(), y_spin.value()]
        for key, spin in self.time_inputs.items():
            cfg["timings"][key] = spin.value()
        cfg["timings"]["click_interval"] = self.click_interval_spin.value()
        cfg["timings"]["detect_interval"] = self.detect_interval_spin.value()
        cfg["template"]["path"] = self.template_path_edit.text()
        cfg["template"]["threshold"] = self.threshold_spin.value()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            self.config = cfg
            QMessageBox.information(self, "保存成功", f"配置已保存到:\n{CONFIG_FILE}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))
    def start_coffee(self):
        
        hwnd = get_game_hwnd()
        if not hwnd:
            QMessageBox.warning(self, "错误", "请先锁定游戏窗口！")
            return
        if self.coffee_thread and self.coffee_thread.is_alive():
            if self.is_paused:
                self._toggle_pause()
            return
        self._sync_ui_to_config()
        self._save_config_silent()
        self.is_paused = False
        self.stop_event = threading.Event()
        self.coffee_core = CoffeeCore(hwnd, self.config, stop_event=self.stop_event)
        self.coffee_thread = threading.Thread(target=self._run_coffee, daemon=True)
        self.coffee_thread.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._set_status_text("运行中...")
        self.status_label.setStyleSheet("color: #00ff88; font-size: 15px; font-weight: bold;")
    def _run_coffee(self):
        
        try:
            self.coffee_core.run()
        except Exception as e:
            self.update_status_signal.emit(f"异常: {e}")
        finally:
            self.update_status_signal.emit("待机")
            QTimer.singleShot(0, self._on_stopped)
    def _on_stopped(self):
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
    def stop_coffee(self):
        
        if self.stop_event:
            self.stop_event.set()
        if self.coffee_thread and self.coffee_thread.is_alive():
            self.coffee_thread.join(timeout=3)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._set_status_text("已停止")
    def _save_config_silent(self):
        
        cfg = {
            "positions": {},
            "timings": {},
            "template": {}
        }
        for key, (x_spin, y_spin) in self.pos_inputs.items():
            cfg["positions"][key] = [x_spin.value(), y_spin.value()]
        for key, spin in self.time_inputs.items():
            cfg["timings"][key] = spin.value()
        cfg["timings"]["click_interval"] = self.click_interval_spin.value()
        cfg["timings"]["detect_interval"] = self.detect_interval_spin.value()
        cfg["template"]["path"] = self.template_path_edit.text()
        cfg["template"]["threshold"] = self.threshold_spin.value()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            self.config = cfg
        except Exception:
            pass
    def _sync_ui_to_config(self):
        
        for key, (x_spin, y_spin) in self.pos_inputs.items():
            self.config.setdefault("positions", {})[key] = [x_spin.value(), y_spin.value()]
        for key, spin in self.time_inputs.items():
            self.config.setdefault("timings", {})[key] = spin.value()
        self.config.setdefault("timings", {})["click_interval"] = self.click_interval_spin.value()
        self.config.setdefault("timings", {})["detect_interval"] = self.detect_interval_spin.value()
        self.config.setdefault("template", {})["path"] = self.template_path_edit.text()
        self.config.setdefault("template", {})["threshold"] = self.threshold_spin.value()
    def update_status_display(self):
        
        if self.coffee_core:
            label_text = f"循环: {self.coffee_core.cycle_count} 次"
            if self.is_paused:
                label_text += " [暂停中]"
            self.cycle_label.setText(label_text)
    def _set_status_text(self, text):
        self.status_label.setText(f"当前状态：{text}")
    def _set_cycle_text(self, count):
        self.cycle_label.setText(f"循环次数: {count}")
    def _append_log(self, msg):
        
        self.log_viewer.appendPlainText(msg)
        scrollbar = self.log_viewer.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    def closeEvent(self, event):
        self.stop_coffee()
        self.hotkey_mgr.clear_all()
        clear_locked_hwnd()
        self._save_config_silent()
        event.accept()
    def _get_style(self):
        return """
            QWidget {
                background-color: #1a1a2e;
                color: #e0e0e0;
                font-size: 13px;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            }
            /* 标签页 */
            QTabWidget#MainTabs::pane {
                border: 1px solid #444;
                border-radius: 4px;
                background-color: #222236;
            }
            QTabBar::tab {
                background-color: #2a2a3e;
                color: #aaa;
                border: 1px solid #444;
                border-bottom: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                padding: 8px 18px;
                margin-right: 2px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #222236;
                color: #ff9900;
                border-bottom: 2px solid #ff9900;
            }
            QTabBar::tab:hover {
                color: #ffcc66;
            }
            /* 分组框 */
            QGroupBox {
                color: #ff9900;
                border: 1px solid #555;
                border-radius: 6px;
                margin-top: 14px;
                padding: 18px 12px 10px 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            /* 标签 */
            QLabel {
                color: #c0c0c0;
                font-size: 13px;
            }
            QLabel#WinInfo {
                color: #ff4444;
                font-size: 13px;
                font-weight: bold;
            }
            QLabel#StatusLabel {
                color: #00ff88;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#CycleLabel {
                color: #ffaa00;
                font-size: 14px;
            }
            /* 按钮 */
            QPushButton {
                background-color: #2a2a3e;
                color: #ff9900;
                border: 1px solid #ff9900;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff9900;
                color: #1a1a2e;
            }
            QPushButton#StartButton {
                background-color: #1a3a2a;
                color: #00ff88;
                border: 2px solid #00ff88;
                font-size: 15px;
                padding: 8px 24px;
            }
            QPushButton#StartButton:hover {
                background-color: #00ff88;
                color: #1a1a2e;
            }
            QPushButton#StopButton {
                background-color: #3a1a1a;
                color: #ff4444;
                border: 2px solid #ff4444;
                font-size: 15px;
                padding: 8px 24px;
            }
            QPushButton#StopButton:hover {
                background-color: #ff4444;
                color: #1a1a2e;
            }
            /* 输入控件 */
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
                background-color: #2a2a3e;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px 6px;
                font-size: 13px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border: 1px solid #ff9900;
            }
            QComboBox {
                padding: 4px 8px;
            }
            /* 底部框架 */
            QFrame#BottomFrame {
                border-top: 1px solid #444;
                background: transparent;
            }
        """
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyleSheet("""
            QToolTip {
                font-size: 13px;
                background-color: #1a1a2e;
                color: #ff9900;
                border: 1px solid #ff9900;
                padding: 4px;
            }
        """)
        ui = CoffeeUI()
        ui.refresh_windows()
        ui.show()
        sys.exit(app.exec_())
    except Exception as e:
        error_msg = ''.join(traceback.format_exception(None, e, e.__traceback__))
        print(f"程序崩溃:\n{error_msg}")
        try:
            app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
            QMessageBox.critical(None, "错误", f"程序发生致命错误。\n\n{str(e)}")
        except:
            pass
        sys.exit(1)
