#pip install pyautogui ,openai
"""图片传递：
视觉模型要求图片以 base64 编码或 URL 形式传入。这里将截图 screenshot.png 读取并转为 base64 字符串，
放在 image_url 的 url 字段中，格式为 data:image/png;base64,<base64>。
"""
import base64
import os
import re
import time
from io import BytesIO

from openai import OpenAI
from PIL import ImageGrab


# ---------- 配置 ----------
MODEL_NAME = "deepseek-v4-flash-vision-exp"   # 确认该模型支持视觉
BASE_URL = "https://api.deepseek.com"
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")  # 建议设置环境变量，或直接在此填写


def capture_screen():
    """
    截取全屏，返回 (PIL.Image, width, height)
    使用 Pillow 的 ImageGrab，跨平台且稳定
    """
    try:
        screenshot = ImageGrab.grab()  # 全屏截图
        width, height = screenshot.size
        return screenshot, width, height
    except Exception as e:
        raise RuntimeError(f"截图失败: {e}")


def encode_image_to_base64(image):
    """
    将 PIL Image 对象编码为 base64 字符串（PNG 格式）
    无需保存临时文件
    """
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def parse_coordinates(text):
    """
    从模型返回的文本中提取 (x, y) 坐标，支持多种常见格式：
    - "123, 456"
    - "x=123, y=456"
    - "坐标：123，456"
    - "(123,456)"
    返回 (int, int) 或 None
    """
    # 匹配数字对，允许中文逗号或英文逗号，周围可有空格
    pattern = r"(\d+)\s*[,，]\s*(\d+)"
    matches = re.findall(pattern, text)
    if matches:
        # 取最后一对数字（通常更可靠）
        x_str, y_str = matches[-1]
        return int(x_str), int(y_str)
    return None


def find_wechat_icon_coordinates(api_key, base_url, model, max_retries=2):
    """
    主流程：截图 → 调用视觉模型 → 解析坐标
    """
    # 1. 截图并获取分辨率
    screenshot, width, height = capture_screen()

    # 2. 构建指令（包含分辨率信息）
    instruction = (
        f"该用户主屏幕的分辨率为 {width}×{height}，"
        "请识别微信图标的位置，告诉我其可点击的中心坐标（x, y），"
        "只需返回坐标数值，用英文逗号分隔，例如：123, 456"
    )

    # 3. 将图片转为 base64
    img_base64 = encode_image_to_base64(screenshot)

    # 4. 初始化 OpenAI 客户端
    client = OpenAI(api_key=api_key, base_url=base_url)

    # 5. 调用 API（带重试）
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                            },
                        ],
                    }
                ],
                max_tokens=100,  # 只需简短坐标，设小以节省 token
                temperature=0.0,  # 尽量确定输出
            )

            reply = response.choices[0].message.content.strip()
            print(f"[尝试 {attempt+1}] 模型返回: {reply}")

            # 6. 解析坐标
            coords = parse_coordinates(reply)
            if coords:
                return coords
            else:
                print("无法解析坐标，可能返回格式不符，稍后重试...")
                # 如果返回格式不匹配，可以尝试再次请求（非必要）
        except Exception as e:
            print(f"API 调用失败 (尝试 {attempt+1}/{max_retries}): {e}")
            time.sleep(1)  # 等待后重试

    print("多次尝试后仍未获得有效坐标。")
    return None


def main():
    # 检查 API Key
    if not API_KEY:
        print("错误：未设置 API Key。请设置环境变量 DEEPSEEK_API_KEY 或在代码中直接赋值。")
        return

    coords = find_wechat_icon_coordinates(API_KEY, BASE_URL, MODEL_NAME)
    if coords:
        x, y = coords
        print(f"微信图标可点击坐标：({x}, {y})")
        # 如需自动点击，可取消下一行注释：
        # import pyautogui
        # pyautogui.click(x, y)
    else:
        print("未能获取坐标。")

if __name__ == "__main__":
    main()