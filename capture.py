import cv2
import numpy as np
import win32gui
import win32ui
import ctypes
from PIL import Image
def capture_window(hwnd):
    
    if not win32gui.IsWindow(hwnd):
        return None
    rect = win32gui.GetClientRect(hwnd)
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    if not hwnd_dc:
        return None
    try:
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)
        success = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        if not success:
            return None
        bitmap_bits = bitmap.GetBitmapBits(True)
        img = Image.frombuffer("RGB", (width, height), bitmap_bits, "raw", "BGRX", 0, 1)
        opencv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return opencv_img
    except Exception:
        return None
    finally:
        try:
            win32gui.DeleteObject(bitmap.GetHandle())
        except:
            pass
        try:
            save_dc.DeleteDC()
        except:
            pass
        try:
            mfc_dc.DeleteDC()
        except:
            pass
        try:
            win32gui.ReleaseDC(hwnd, hwnd_dc)
        except:
            pass
def find_template_in_window(hwnd, template_path, threshold=0.7, region=None):
    
    full_img = capture_window(hwnd)
    if full_img is None:
        return False, 0.0, None
    from utils import load_template
    template = load_template(template_path)
    if template is None:
        print(f"[错误] 无法加载模板图片: {template_path}")
        return False, 0.0, None
    if region:
        x1, y1, x2, y2 = region
        h, w = full_img.shape[:2]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))
        img = full_img[y1:y2, x1:x2]
    else:
        img = full_img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    found = max_val >= threshold
    if found:
        h_t, w_t = template.shape
        center_x = max_loc[0] + w_t // 2
        center_y = max_loc[1] + h_t // 2
        if region:
            center_x += region[0]
            center_y += region[1]
        return True, max_val, (center_x, center_y)
    return False, max_val, None
