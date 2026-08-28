import json
import os
from openai import OpenAI
from pathlib import Path

# 初始化客户端（再次确认API Key）
client = None

def init_client(api_key):
    global client  # 必须先声明！
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return client

# 经验库目录
EXPERIENCE_DIR = Path("experience")


def read_experience_summary():
    """读取经验库下所有json文件的文件名与步骤摘要"""
    skills = []
    if not EXPERIENCE_DIR.exists():
        return skills

    for file_path in EXPERIENCE_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                steps_desc = [s.get("step", "未描述") for s in data.get("steps", [])]
                skills.append({
                    "filename": file_path.name,
                    "steps": steps_desc
                })
        except Exception as e:
            print(f"[LLM] 读取经验文件 {file_path.name} 失败: {e}")

    return skills


def ask_llm_for_next_action(user_goal, memory, skills_list):
    """
    让LLM判断下一步：是执行经验库技能，还是转交VLM视觉探索。

    返回:
        {
            "action_type": "auto_action" 或 "visual_vlm",
            "skill_filename": "xxx.json" (如果是auto_action),
            "reason": "判断理由"
        }
    """

    # 构造系统提示词，告诉LLM可用的技能
    skill_descriptions = ""
    for skill in skills_list:
        skill_descriptions += f"- 文件名: {skill['filename']}, 步骤: {skill['steps']}\n"

    if not skill_descriptions:
        skill_descriptions = "暂无任何可用技能。\n"

    system_prompt = f"""
你是一个电脑自动化控制核心大脑。当前用户目标：{user_goal}

以下是之前执行的记录（Memory History，可能为空或初始化）：
{json.dumps(memory.get("history", []), ensure_ascii=False)}

目前经验库中可供调用的自动化技能（JSON文件）如下：
{skill_descriptions}

请判断当前状态下，下一步应该怎么做？
决策规则：
1. 如果经验库中存在能够完美解决当前目标的技能，请选择执行该技能。
2. 如果经验库中的技能已全部尝试过但未能达成目标，或者经验库里根本没有对应的技能，或者不确定是否可用，则需要调用视觉模型（VLM）模式进行屏幕分析。

请严格按照以下JSON格式输出，不要输出多余的解释：
{{
    "action_type": "auto_action" 或 "visual_vlm",
    "skill_filename": "选中的文件名（如果action_type是auto_action）",
    "reason": "简短的决策理由"
}}
"""

    response = client.chat.completions.create(
        model="deepseek-chat",  # 注意：这里使用文本模型即可，不需要Vision
        messages=[{"role": "user", "content": system_prompt}],
        temperature=0.0,
        max_tokens=200
    )

    raw_content = response.choices[0].message.content
    clean_content = raw_content.replace("```json", "").replace("```", "").strip()

    try:
        decision = json.loads(clean_content)
        return decision
    except json.JSONDecodeError:
        # 模型输出错误时的默认兜底方案（转为VLM探索）
        print("[LLM] 模型决策输出解析失败，默认转交给VLM处理")
        return {"action_type": "visual_vlm", "skill_filename": "", "reason": "LLM输出解析异常"}


def auto_loop(user_goal, memory):
    """
    LLM 主导的主循环判断逻辑（供 main.py 调用）
    """
    max_iterations = 5  # 防止无限循环执行技能

    for i in range(max_iterations):
        # 1. 扫描经验库
        skills = read_experience_summary()

        # 2. 询问 LLM 下一步
        decision = ask_llm_for_next_action(user_goal, memory, skills)

        # 3. 处理决策结果
        if decision.get("action_type") == "auto_action":
            filename = decision.get("skill_filename")
            print(f"[LLM] 决定执行技能: {filename}。理由: {decision.get('reason')}")

            # 调用 auto_action
            from auto_action import execute_skill
            result = execute_skill(memory, filename, user_goal)

            # 写入 memory 的 LLM 决策记录  统一格式 保证复盘解析正确
            memory["history"].append({
                "type": "llm_decision",
                "step": "LLM决策",
                "command": {"action": "decision", "params": {}, "step_aim": "决定走经验库还是视觉"},
                "decision": decision,
                "skill_result": result
            })
            """
            memory["history"].append({
                "type": "llm_decision",
                "decision": decision,
                "skill_result": result
            })
            """

            # 如果技能执行失败，不再盲目尝试该技能，转交VLM
            if result.get("status") == "failed":
                print(f"[LLM] 技能执行失败，转交给VLM视觉探索。")
                return {"mode": "vlm", "reason": "经验执行失败，需要视觉辅助"}

            # 如果技能执行完成/成功，继续让LLM判断是继续执行下一个技能还是结束
            continue

        elif decision.get("action_type") == "visual_vlm":
            # LLM认为没有合适的技能，转交VLM
            print(f"[LLM] 无可用技能，决定转交VLM。理由: {decision.get('reason')}")
            return {"mode": "vlm", "reason": decision.get("reason", "需要视觉探索")}

    # 如果循环次数耗尽
    return {"mode": "vlm", "reason": "自动执行技能次数达到上限，转交VLM"}
