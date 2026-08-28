#经验保存函数，将经验以一定格式保存在文件中，在下次处理指令时查看文件是否可直接执行，待出错那一步在转化处理标准

import json
from pathlib import Path

EXPERIENCE_DIR = Path("experience")


def ensure_directory():
    if not EXPERIENCE_DIR.exists():
        EXPERIENCE_DIR.mkdir(parents=True)
        print(f"已创建经验库目录: {EXPERIENCE_DIR}")


def load_experience(main_order):
    path = EXPERIENCE_DIR / f"{main_order}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_experience(main_order, step_desc, action, params, mode="append"):
    """单条保存/更新经验"""
    ensure_directory()
    path = EXPERIENCE_DIR / f"{main_order}.json"

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"main_order": main_order, "steps": []}

    new_step = {
        "step": step_desc,
        "action": action,
        "params": params
    }

    if mode == "append":
        data["steps"].append(new_step)
        print(f"[经验保存] 追加步骤: {step_desc} -> {action}")
    elif mode == "update":
        updated = False
        for i, step in enumerate(data["steps"]):
            if step.get("step") == step_desc:
                data["steps"][i] = new_step
                updated = True
                print(f"[经验修正] 更新步骤: {step_desc} -> {action}")
                break
        if not updated:
            data["steps"].append(new_step)
    else:
        raise ValueError(f"未知的保存模式: {mode}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def save_experience_batch(main_order, steps):
    """批量追加（review_vlm 提取后调用）"""
    for step in steps:
        # 过滤掉没有 action 的异常数据
        if "action" in step and "step_desc" in step:
            save_experience(main_order, step["step_desc"], step["action"], step.get("params", {}))
        else:
            print(f"[经验保存] 跳过格式错误的步骤: {step}")
