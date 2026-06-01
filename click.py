import win32gui
import win32con
import win32api
import time
import ctypes
from ctypes import wintypes, byref, pointer, c_ulong
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(c_ulong)),
    ]
class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
    ]
class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]
def send_click_event(duration=0.2):
    
    down = INPUT()
    down.type = INPUT_MOUSE
    down.union.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
    ctypes.windll.user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    time.sleep(duration)
    up = INPUT()
    up.type = INPUT_MOUSE
    up.union.mi.dwFlags = MOUSEEVENTF_LEFTUP
    ctypes.windll.user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
def bring_window_to_top_force(hwnd):
    
    if not win32gui.IsWindow(hwnd):
        return
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
    time.sleep(0.05)
    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
def click_at_screen(screen_x, screen_y, duration=0.2, pre_delay=0.5):
    
    ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
    time.sleep(pre_delay)
    send_click_event(duration)
def click_at_client(hwnd, client_x, client_y, duration=0.2, pre_delay=0.5):
    
    if not win32gui.IsWindow(hwnd):
        print("[警告] 无效的窗口句柄")
        return
    bring_window_to_top_force(hwnd)
    screen_x, screen_y = win32gui.ClientToScreen(hwnd, (client_x, client_y))
    click_at_screen(screen_x, screen_y, duration, pre_delay)
def move_to_client(hwnd, client_x, client_y):
    
    if not win32gui.IsWindow(hwnd):
        return
    bring_window_to_top_force(hwnd)
    screen_x, screen_y = win32gui.ClientToScreen(hwnd, (client_x, client_y))
    ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
    time.sleep(0.5)
def click_at_current_pos(duration=0.2):
    
    send_click_event(duration)
