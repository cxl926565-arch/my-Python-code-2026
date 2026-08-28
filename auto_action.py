import json
from pathlib import Path
from action import ActionExecutor  # 复用之前的动作执行器


def execute_skill(memory, skill_filename, user_goal):
    """
    根据经验库文件名执行自动化步骤
    参数:
        memory: 全局记忆字典
        skill_filename: 经验库中的文件名 (如 "open_wechat.json")
        user_goal: 用户原始目标
    返回:
        result_dict: {"status": "success" / "failed" / "finished", "message": "..."}
    """
    print(f"\n[AutoAction] 开始执行经验技能: {skill_filename}")

    # 1. 读取经验JSON文件
    skill_path = Path("experience") / skill_filename
    if not skill_path.exists():
        return {"status": "failed", "message": f"经验文件不存在: {skill_filename}"}

    with open(skill_path, "r", encoding="utf-8") as f:
        skill_data = json.load(f)

    # 2. 初始化执行器
    executor = ActionExecutor()

    # 3. 遍历执行步骤
    for step in skill_data.get("steps", []):
        step_desc = step.get("step", "未知步骤")
        command = {
            "action": step.get("action"),
            "params": step.get("params", {}),
            "step_aim": step_desc
        }

        print(f"[AutoAction] 正在执行: {step_desc}")

        # 4. 执行动作
        try:
            result = executor.execute(command)
        except Exception as e:
            # 执行发生异常
            error_msg = f"步骤 '{step_desc}' 执行异常: {str(e)}"
            memory["history"].append({
                "type": "auto_action",
                "skill": skill_filename,
                "step": step_desc,
                "command": command,
                "result": {"status": "error", "message": error_msg}
            })
            return {"status": "failed", "message": error_msg}

        # 5. 记录执行结果到记忆
        memory["history"].append({
            "type": "auto_action",
            "skill": skill_filename,
            "step": step_desc,
            "command": command,
            "result": result
        })

        # 6. 如果步骤执行失败，立刻中止当前技能并上报
        if result.get("status") == "error":
            return {"status": "failed", "message": f"步骤 '{step_desc}' 失败: {result.get('message')}"}

        # 7. 如果执行到了 finish 步骤，说明技能完成
        if command.get("action") == "finish":
            return {"status": "finished", "message": "该技能执行完毕"}

    # 循环结束，说明技能正常走完没有 finish
    return {"status": "success", "message": "技能执行完成"}
