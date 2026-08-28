import base64
import json
import ctypes
import mss
import cv2
import numpy as np
import pyautogui
from openai import OpenAI

# 1. 配置 DeepSeek API (记得替换你的 API Key)
client = OpenAI(api_key="", base_url="https://api.deepseek.com")


# --- 2. 取得分辨率和 DPI 缩放 ---
def get_screen_info():
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        scale = dpi / 96
    except Exception:
        scale = 1.0
    pyautogui_size = pyautogui.size()
    logical_w, logical_h = pyautogui_size
    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        physical_w, physical_h = monitor["width"], monitor["height"]
    print(f"逻辑: {logical_w}x{logical_h}, 物理: {physical_w}x{physical_h}, 缩放: {scale:.2f}")
    return logical_w, logical_h, physical_w, physical_h


# --- 3. 高清截图 (通过 mss) ---
def capture_hd_screenshot():
    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)[:, :, :3]
        return img


# --- 4. 调用 DeepSeek V4 Vision 模型 ---
def locate_target_via_api(screenshot):
    # 把 numpy 图片转为 Base64
    _, buffer = cv2.imencode('.jpg', screenshot)
    b64_img = base64.b64encode(buffer).decode('utf-8')

    # 预留模型接口：指定你想要的定位目标
    prompt = "请定位屏幕截图中的'微信'图标。请只返回JSON格式，包含中心坐标x和y（范围0-999的相对坐标）：{\"x\": 123, \"y\": 456}"

    response = client.chat.completions.create(
        model="deepseek-v4-flash-vision-exp",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}", "detail": "high"}}
                ]
            }
        ]
    )

    # 提取并解析 JSON
    content = response.choices[0].message.content
    # 容错处理：清除模型返回中可能带有的```json 标识
    content_clean = content.replace('```json', '').replace('```', '').strip()
    coords_dict = json.loads(content_clean)
    return int(coords_dict['x']), int(coords_dict['y'])


# --- 5. 坐标换算与主流程 ---
def main():
    logic_w, logic_h, phys_w, phys_h = get_screen_info()
    screenshot = capture_hd_screenshot()

    print("正在调用 DeepSeek V4 Vision 识别目标...")
    model_x, model_y = locate_target_via_api(screenshot)

    # 将 0-999 的相对坐标换算为物理像素坐标
    phys_x = int(model_x / 999 * phys_w)
    phys_y = int(model_y / 999 * phys_h)

    # 换算为 pyautogui 所需的逻辑坐标
    logic_x = int(phys_x / phys_w * logic_w)
    logic_y = int(phys_y / phys_h * logic_h)

    print(f"模型相对坐标: ({model_x}, {model_y})")
    print(f"换算后点击坐标: ({logic_x}, {logic_y})")

    pyautogui.click(logic_x, logic_y)
    pyautogui.click(logic_x, logic_y)


if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    main()