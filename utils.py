import sys
import os
import cv2
import numpy as np
from PIL import Image
def resource_path(relative_path):
    
    if getattr(sys, 'frozen', False):
        for base in (os.path.dirname(sys.executable), sys._MEIPASS):
            p = os.path.join(base, relative_path)
            if os.path.exists(p):
                return p
        return os.path.join(os.path.dirname(sys.executable), relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
def load_template(path):
    
    tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if tpl is not None:
        return tpl
    try:
        return np.array(Image.open(path).convert('L'))
    except:
        return None
def ensure_dir(path):
    
    d = os.path.dirname(os.path.abspath(path))
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
