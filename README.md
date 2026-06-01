# NTEautoCoffee - 异环自动咖啡脚本

基于 MintNTE 钓鱼脚本架构开发的异环自动咖啡制作脚本。

## 功能流程

1. **位置1** → 鼠标移动并点击 → 等待8秒（开始制作咖啡）
2. **位置2** → 鼠标移动并连续点击，直到图像识别检测到三个黄色星星
3. **位置3** → 检测到模板后 → 移动并点击 → 等待3秒
4. **位置4** → 移动并点击 → 等待5秒
5. 循环上述步骤

## 安装依赖

```
pip install -r requirements.txt
```

## 使用方法

1. 运行 `python main.py`（需要管理员权限）
2. 在"游戏窗口"区域刷新并锁定异环游戏窗口
3. 配置四个位置坐标（窗口客户区坐标）
4. 准备模板图片：截取游戏中的三个黄色星星，保存到 `images/three_yellow_stars.png`
5. 点击"开始制作咖啡"

## 项目结构

```
NTEautoCoffee/
├── main.py          # 主入口（PyQt5 UI）
├── coffee_core.py   # 自动化核心逻辑
├── capture.py       # 窗口截图 & 模板匹配
├── click.py         # 鼠标点击操作
├── hwnd.py          # 窗口句柄管理
├── utils.py         # 工具函数
├── config.json      # 配置文件
├── requirements.txt # Python 依赖
└── images/          # 模板图片目录
```

## 配置说明

`config.json` 中的关键配置:

- `positions`: 四个点击位置的窗口客户区坐标
- `timings`: 各步骤等待时间
- `template.path`: 模板图片路径
- `template.threshold`: 模板匹配阈值 (0.3-0.99)

## 技术架构

- 截图: PrintWindow API (后台截图)
- 点击: SendInput API (前台模拟)
- 图像识别: OpenCV matchTemplate (模板匹配)
- UI: PyQt5
