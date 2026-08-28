import base64
import json
import ctypes
import mss
import cv2
import numpy as np
import openai
import pyautogui
from openai import OpenAI
from pathlib import Path


# 1. 配置 DeepSeek API (请替换你的 API Key)
client = None

def init_client(api_key):
    global client  # 必须先声明！
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return client

# --- 动态获取屏幕分辨率和 DPI 缩放 ---
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
    print(f"[VLM] 逻辑: {logical_w}x{logical_h}, 物理: {physical_w}x{physical_h}, 缩放: {scale:.2f}")
    return logical_w, logical_h, physical_w, physical_h


# --- 0-999 相对坐标转绝对逻辑坐标 ---
def convert_relative_to_logic(rel_coords, logic_w, logic_h):
    if rel_coords is None:
        return None
    # 提取目标坐标
    if isinstance(rel_coords, dict):
        rel_x, rel_y = rel_coords.get('x'), rel_coords.get('y')
    else:
        rel_x, rel_y = rel_coords

    # 换算为逻辑坐标
    logic_x = int(rel_x / 999 * logic_w)
    logic_y = int(rel_y / 999 * logic_h)
    return logic_x, logic_y


# --- 读取截图并转为Base64 ---
def get_screenshot_base64(screenshot_path):
    with open(screenshot_path, "rb") as f:
        img_data = f.read()
    return base64.b64encode(img_data).decode('utf-8')


def get_next_action(screenshot_path, memory_context, user_goal):
    """
    调用 DeepSeek V4 Flash Vision 模型。
    根据屏幕截图、上下文和任务目标，返回下一步动作指令（绝对坐标）。
    """
    print("\n" + "=" * 60)
    print(f"[VLM] 正在调用 DeepSeek V4 Vision 分析屏幕...")

    # 1. 获取屏幕尺寸信息（用于将模型返回的相对坐标转换为实际逻辑坐标）
    logic_w, logic_h, phys_w, phys_h = get_screen_info()

    # 2. 读取截图并编码
    b64_img = get_screenshot_base64(screenshot_path)

    # 3. 构造 Prompt（核心：严格限定动作参数及 0-999 相对坐标）
    prompt = f"""
你是一个电脑自动化操作助手。请观察当前屏幕截图，结合上下文和任务目标，决定下一步操作。
任务总目标: {user_goal}
已执行过的动作和结果:
{memory_context}

提示，桌面上部分程序需要双击打开

可用动作及其参数格式说明（坐标必须提供0-999的相对坐标，代表目标的相对位置）：
1. click: {{"action": "click", "params": {{"x": 相对x坐标, "y": 相对y坐标, "clicks": 1}},"step_aim":"Briefly explain the purpose of this step."}}
2. scroll: {{"action": "scroll", "params": {{"x": 相对x坐标, "y": 相对y坐标, "clicks": 负数向下, 正数向上}},"step_aim":"Briefly explain the purpose of this step."}}
3. type: {{"action": "type", "params": {{"text": "要输入的文字"}},"step_aim":"Briefly explain the purpose of this command."}}
4. drag: {{"action": "drag", "params": {{"start_x": 相对x坐标, "start_y": 相对y坐标, "end_x": 相对x坐标, "end_y": 相对y坐标}},"step_aim":"Briefly explain the purpose of this step."}}
5. finish: {{"action": "finish", "params": {{}},"step_aim":"本程序总目标完成"}}

请仅输出一个JSON对象，不要包含任何解释性文字或markdown代码块。
"""

    # 4. 调用 API (保持高清晰度 detail=high)
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash-vision-exp",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{b64_img}", "detail": "high"}}
                    ]
                }
            ],
            temperature=0.0,  # 降低随机性，保证定位稳定
            max_tokens=500
        )

        content = response.choices[0].message.content
        # 容错处理：清除模型返回中可能带有的 ```json 标识
        content_clean = content.replace('```json', '').replace('```', '').strip()
        print(f"[VLM] 模型原始输出: {content_clean}")

        # 解析 JSON
        command = json.loads(content_clean)
        if "action" not in command:
            raise ValueError("模型输出缺少 action 字段")

        # 5. 核心坐标换算 (将0-999相对坐标转为绝对逻辑坐标)
        action = command.get("action")
        params = command.get("params", {})
        step_aim = command.get("step_aim")

        # 根据不同动作转换坐标
        if action in ["click", "scroll"] and "x" in params and "y" in params:
            abs_x, abs_y = convert_relative_to_logic(params, logic_w, logic_h)
            params["x"] = abs_x
            params["y"] = abs_y
        elif action == "drag":
            start_abs_x, start_abs_y = convert_relative_to_logic({"x": params["start_x"], "y": params["start_y"]},
                                                                 logic_w, logic_h)
            end_abs_x, end_abs_y = convert_relative_to_logic({"x": params["end_x"], "y": params["end_y"]}, logic_w,
                                                             logic_h)
            params["start_x"] = start_abs_x
            params["start_y"] = start_abs_y
            params["end_x"] = end_abs_x
            params["end_y"] = end_abs_y

        # 更新回 command
        command["params"] = params
        print(f"[VLM] 转换后的绝对坐标指令: {command}")

        return {"status": "success", "command": command, "goal": user_goal,"step_aim": step_aim }

    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"模型返回内容不是合法JSON: {str(e)}", "command": None}
    except Exception as e:
        return {"status": "error", "message": f"API调用或坐标转换异常: {str(e)}", "command": None}