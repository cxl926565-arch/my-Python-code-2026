import os
import json
import time
from pathlib import Path
from datetime import datetime
import mss
import cv2
import numpy as np
import pyautogui
import vlm
# 导入其他文件
from action import ActionExecutor
from openai import api_key
from vlm import get_next_action
import review_vlm
import experience_save
import llm

# 创建目录
BASE_DIR = Path(__file__).parent
SCREENSHOT_DIR = BASE_DIR / "screenshots"
MEMORY_DIR = BASE_DIR / "memory"
SCREENSHOT_DIR.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)


def get_screenshot(tag_name):
    """截图函数，利用mss获取高清图，保存并返回图片路径"""
    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)[:, :, :3]
        file_path = SCREENSHOT_DIR / f"{tag_name}_{int(time.time())}.png"
        cv2.imwrite(str(file_path), img)
        return str(file_path)


def main():

    #初始提示
    print("程序即将开始，请查看弹窗消息")
    pyautogui.alert("GUI自动化运行过程中请不要操控鼠标键盘\n程序涉及隐私，可在目录查看所有操作\n若有误操作趋势请立刻终止程序", "提示", "我已知悉")


    #1 获取用户自然语言指令（模拟 LLM 大脑入口）
    user_goal = input("请输入您的任务指令（自然语言，例如：帮我自动回复微信里面的未读消息）: ")

    #2 初始化全局运行记忆
    main_order = input("请输入本次任务的名称 (用于记忆归档, 例: sendamessage): ")
    pyautogui.alert(
        "程序即将开始，请确保主屏幕桌面干净，目标程序可见",
        "提示", "我已知悉")


    api_key = pyautogui.prompt("请输入你的DeepSeek APIkey ", "提示", "")
    llm.init_client(api_key)
    vlm.init_client(api_key)
    review_vlm.init_client(api_key)


    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    memory = {
        "main_order": main_order,
        "run_id": run_id,
        "user_goal": user_goal,  # 记录主目标
        "history": []  # 记录每一步的命令和结果
    }
    print(f"[Main] 初始化任务: {main_order} (ID: {run_id})")
    print(f"[Main] 用户主目标: {user_goal}")

    #3 初始化执行器
    executor = ActionExecutor()

    time.sleep(1)
    print("程序初始化成功，开始运行\n============================================================================================================")
    #4 调用LLM程序 进行初始普遍性操作自动化运行
    llm_result = llm.auto_loop(user_goal, memory)

    #5 根据 LLM 返回的结果，决定是否进入原来的 VLM 循环
    if llm_result["mode"] == "vlm":
        print("[Main] 经验库自动执行结束，现在开始 VLM 视觉探索循环...")

        #vlm1 循环过程
        step_num = 0
        while True:

            step_num += 1
            print(f"\n[Main] === vlm视觉方案程序 第 {step_num} 步循环开始 ===")

            #v1.1 截取当前屏幕
            screenshot_path = get_screenshot(f"step_{step_num}")

            #v1.2 构造上下文记忆字符串（供VLM分析）
            context_string = json.dumps(memory["history"], ensure_ascii=False)

            #v1.3 调用VLM获取下一步指令。传入截图、上下文、以及最重要的：用户自然语言命令！                  ###  调用VLM
            vlm_result = get_next_action(screenshot_path, context_string, user_goal)            #是把上下文memory复制后 发过去的，不是原稿

            if vlm_result["status"] == "error":
                print(f"[Main] VLM 解析失败: {vlm_result['message']}")
                continue

            command_dict = vlm_result["command"]
            step_aim = command_dict["step_aim"]

            #v1.4 执行Action                                                                    ###  调用action
            if command_dict["action"] == "finish":
                print("[Main] 收到结束指令，任务完成！")
                memory["history"].append(
                    {"step": step_num, "type": "finish", "command": command_dict, "result": "任务结束"})
                break

            action_result = executor.execute(command_dict)

            #v1.5 记录运行记忆
            memory["history"].append({
                "step": step_num,
                "step_aim": step_aim,
                "screenshot": screenshot_path,
                "command": command_dict,
                "result": action_result
            })

            print(f"[Main] Action执行结果: {action_result}")

        #vlm2 归档本次运行的记忆文件
        memory_path = MEMORY_DIR / f"{main_order}_{run_id}.json"
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=4)

        print(f"\n[Main] 运行结束！记忆已归档至: {memory_path}")


        #vlm3 调用 review_vlm 进行复盘，提取经验

        extracted_steps = review_vlm.review_experience(memory, user_goal, SCREENSHOT_DIR)


        #vlm4 用户确认是否保存经验
        if extracted_steps:
            print("\n[Main] Review-VLM 认为以下步骤可以沉淀为通用经验：")
            for i, step in enumerate(extracted_steps):
                print(f"{i + 1}. {step.get('step_desc')} -> {step.get('action')} params: {step.get('params')}")

            user_confirm = input("是否将这些步骤保存到经验库？(y/n): ").strip().lower()

            if user_confirm == "y":
                # 用户可以指定一个经验保存的任务名称
                exp_order = input("请输入保存经验的任务名称 (例如: sendamessage): ").strip()
                if not exp_order:
                    exp_order = main_order
                experience_save.save_experience_batch(exp_order, extracted_steps)
                print(f"[Main] 经验已保存到 'experience/{exp_order}.json' 文件中。")
            else:
                print("[Main] 用户未确认，放弃保存经验。")
        else:
            print("[Main] Review-VLM 未提取到可复用的经验步骤。")

    else:
        print("[Main] 任务在所有自动技能中执行完毕，程序正常结束。")


if __name__ == "__main__":
    main()