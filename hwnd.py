import win32gui
import win32con
_locked_hwnd = None
def set_locked_hwnd(hwnd):
    
    global _locked_hwnd
    _locked_hwnd = hwnd
def clear_locked_hwnd():
    
    global _locked_hwnd
    _locked_hwnd = None
def get_game_hwnd():
    
    if _locked_hwnd and win32gui.IsWindow(_locked_hwnd):
        return _locked_hwnd
    return None
def find_window_by_title(title_keyword="异环"):
    
    result = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if title_keyword in window_title:
                result.append((hwnd, window_title))
        return True
    win32gui.EnumWindows(callback, None)
    return result
def get_window_info(hwnd):
    
    if not win32gui.IsWindow(hwnd):
        return None
    rect = win32gui.GetClientRect(hwnd)
    title = win32gui.GetWindowText(hwnd)
    screen_pos = win32gui.ClientToScreen(hwnd, (0, 0))
    return {
        "hwnd": hwnd,
        "title": title,
        "client_width": rect[2] - rect[0],
        "client_height": rect[3] - rect[1],
        "screen_x": screen_pos[0],
        "screen_y": screen_pos[1],
    }
