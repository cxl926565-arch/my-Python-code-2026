import base64
import json
import os
from openai import OpenAI
from pathlib import Path

# 初始化 DeepSeek 客户端
#api_key = input("请输入你的DeepSeek apikey")
client = None

def init_client(api_key):
    global client  # 必须先声明！
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return client

def review_experience(memory, user_goal, screenshots_dir):
    """
    在任务完成后，调用 VLM 审核 memory 中的步骤，提取有效且通用的步骤作为经验。
    """
    print("\n" + "=" * 60)
    print("[Review-VLM] 正在复盘任务，提取通用经验...")

    # 构造复盘上下文
    """
    # 将 memory 中的 history 转为易懂的文本
    history_text = ""
    for step in memory.get("history", []):
        if step.get("type") == "finish":
            continue
        history_text += f"步骤: {step['command'].get('step_aim', '未说明')} | 动作: {step['command']['action']} | 参数: {json.dumps(step['command']['params'])} | 执行结果: {step['result']}\n"
    """
    # 构造复盘上下文
    history_text = ""
    for step in memory.get("history", []):
        # 防御性检查：跳过非字典项，或者缺失 command 项的记录（如 LLM 决策记录）
        if not isinstance(step, dict) or "command" not in step:
            continue

        # 安全提取 command 和 result
        cmd = step.get("command", {})
        step_aim = cmd.get("step_aim", "未说明")
        action = cmd.get("action", "未知动作")
        params = cmd.get("params", {})
        step_result = step.get("result", "无记录")

        history_text += f"步骤: {step_aim} | 动作: {action} | 参数: {json.dumps(params, ensure_ascii=False)} | 执行结果: {step_result}\n"


    # 获取最后一张截图（可选，用于提供最终界面上下文）
    final_shot = ""
    if memory["history"]:
        last_shot_path = memory["history"][-1].get("screenshot")
        if last_shot_path and os.path.exists(last_shot_path):
            with open(last_shot_path, "rb") as f:
                final_shot = base64.b64encode(f.read()).decode("utf-8")

    prompt = f"""
你是一个自动化流程专家。某用户完成了任务：“{user_goal}”。
以下是该任务完整执行的历史记录：

{history_text}

请审核这些步骤，提取出哪些步骤是“有效”且“通用”的。
“有效”指：该步骤成功执行了，且没有报错。
“通用”指：该步骤足够基础常用。

提示
状态success仅代表程序没出错，并不表示该步结果执行是否真正成功且符合预期
你可通过这一步的目标是否与上一步不同判断上一步的动作是否成功并符合预期（可能上一步定位错误，打开错误程序，导致状态没变，目标步骤重复进行）
执行坐标已在 历史任务 中，你只需要把成功执行的那一步的坐标提取出来即可，不需你依照屏幕自行计算 

请找出这些可复用的步骤，并严格按要求提取成以下格式的JSON数组，不要包含多余的文本或Markdown：
[
  {{
    "step_desc": "简短描述该步骤的意图（例如：打开微信）",
    "action": "对应的动作类型（如 click, type, scroll, drag）",
    "params": {{... 原动作的参数，如果坐标是特定于这次屏幕的，请尽量使用0-999相对坐标或通用描述 ...}}
  }}
]
如果没有任何可复用的步骤，请返回空数组 []。
"""


    cycle_time = 0
    # 保存最后一次的错误信息，用于反馈给模型
    last_error_msg = ""

    while cycle_time < 3:  # 使用 < 3 确保最多执行 3 次 (0, 1, 2)
        try:
            # 构建消息（附带最后截图）
            content = [{"type": "text", "text": prompt}]

            # 如果有上一次的错误信息，附加在 prompt 里让模型修正
            if last_error_msg:
                prompt_with_feedback = prompt + f"\n\n注意：你上次返回的内容无法解析为JSON，错误信息为：{last_error_msg}。请严格按照要求的格式，只输出纯JSON数组，不要包含任何多余的说明文字或Markdown代码块。"
                content = [{"type": "text", "text": prompt_with_feedback}]

            if final_shot:
                content.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{final_shot}", "detail": "high"}})

            response = client.chat.completions.create(
                model="deepseek-v4-flash-vision-exp",
                messages=[{"role": "user", "content": content}],
                temperature=0.0,
                max_tokens=800
            )

            print("response", response)
            raw_content = response.choices[0].message.content
            clean_content = raw_content.replace("```json", "").replace("```", "").strip()

            # 解析 JSON 数组
            steps = json.loads(clean_content)
            print(f"[Review-VLM] 提取到 {len(steps)} 条通用经验")
            return steps

        except json.JSONDecodeError as e:
            # 捕获 JSON 解析错误
            print(f"[Review-VLM] 第 {cycle_time + 1} 次解析JSON失败，准备重试... 错误: {e}")
            last_error_msg = str(e)
            cycle_time += 1
        except Exception as e:
            # 捕获其他错误（如 API 请求超时、网络异常等）
            print(f"[Review-VLM] 第 {cycle_time + 1} 次调用异常，准备重试... 错误: {e}")
            last_error_msg = str(e)
            cycle_time += 1
            # 如果是API错误可能需要一点冷却时间
            import time

            time.sleep(2)
    # 重试次数用尽，兜底返回空列表
    print("[Review-VLM] 重试次数已用尽，放弃提取经验。")
    return []