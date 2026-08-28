import pyautogui
import time


class ActionExecutor:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5  # 防止动作过快

    def execute(self, command_dict):
        """
        接收VLM或经验库传来的指令字典，格式必须为：
        {"action": "click", "params": {"x": 100, "y": 200, "clicks": 1}}
        或 {"action": "type", "params": {"text": "你好"}}
        """
        if not isinstance(command_dict, dict) or "action" not in command_dict:
            return {"status": "error", "message": "指令格式错误，必须包含 action 字段"}

        action = command_dict.get("action")
        params = command_dict.get("params", {})

        print(f"[Action] 接收到指令: {action} -> {params}")

        try:
            if action == "click":
                self.do_click(**params)
            elif action == "scroll":
                self.do_scroll(**params)
            elif action == "type":
                self.do_type(**params)
            elif action == "drag":
                self.do_drag(**params)
            elif action == "finish":
                return {"status": "finished", "message": "任务结束指令"}
            else:
                return {"status": "error", "message": f"未知动作: {action}"}

            # 执行成功，返回结果
            return {"status": "success", "message": f"已按照要求执行 {action},但不确定本次要求是否符合purpose"}

        except Exception as e:
            # 执行失败，返回错误信息
            return {"status": "error", "message": f"动作执行异常: {str(e)}"}

    # 下面各个基础动作实现
    def do_click(self, x, y, clicks=1, button='left'):
        pyautogui.click(x, y, clicks=clicks, button=button)
        print(f"  -> 点击 ({x}, {y}) 次数: {clicks}")

    def do_scroll(self, x, y, clicks):
        pyautogui.moveTo(x, y)
        pyautogui.scroll(clicks, x=x, y=y)
        print(f"  -> 滑动在 ({x}, {y}) 滚轮值: {clicks}")

    def do_type(self, text, interval=0.05):
        pyautogui.write(text, interval=interval)
        print(f"  -> 输入文本: {text}")

    def do_drag(self, start_x, start_y, end_x, end_y, duration=1.0):
        pyautogui.moveTo(start_x, start_y)
        pyautogui.dragTo(end_x, end_y, duration=duration, button='left')
        print(f"  -> 拖动从 ({start_x}, {start_y}) 到 ({end_x}, {end_y})")


"""
import pyautogui
import time

def get_time():
    local_time = time.localtime()
    formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
    print(formatted_time  ,end="")


class ActionExecutor:
    def __init__(self):
        pyautogui.FAILSAFE = True
        # 如果你之前测过DPI缩放，这里可以加上DPI感知处理
        pyautogui.PAUSE = 0.5  # 每次操作后停顿，防止过快

    def execute(self, step_data):
        
        #统一入口：接收 JSON 中的一个 step 字典
        #格式: {"action": "click", "params": {...}}
        
        action = step_data.get("action")
        params = step_data.get("params", {})

        # 动作分发器（匹配到对应的函数）
        if action == "click":
            self.do_click(**params)
        elif action == "scroll":
            self.do_scroll(**params)
        elif action == "type":
            self.do_type(**params)
        elif action == "drag":
            self.do_drag(**params)
        elif action == "hotkey":
            self.do_hotkey(**params)
        else:
            raise ValueError(f"未知的动作类型: {action}")

    # 1. 鼠标点击
    def do_click(self, x, y, clicks=1, button='left'):
        pyautogui.click(x, y, clicks=clicks, button=button)
        get_time()
        print(f"执行点击: ({x}, {y}) 次数: {clicks}")

    # 2. 鼠标滑动
    def do_scroll(self, x, y, clicks, dx=0, dy=0):
        get_time()
        pyautogui.moveTo(x, y,1)  # 先移动鼠标到该位置再滚
        pyautogui.scroll(clicks, x=x, y=y)
        print(f"执行滑动: 位于 ({x}, {y}), 滚轮方向: {clicks}")

    # 3. 鼠标拖动 (起点和终点)
    def do_drag(self, start_x, start_y, end_x, end_y, duration=1.0):
        get_time()
        pyautogui.moveTo(start_x, start_y,1)
        pyautogui.dragTo(end_x, end_y, duration=duration, button='left')
        print(f"执行拖动: 从 ({start_x}, {start_y}) 到 ({end_x}, {end_y})")

    # 4. 按键输入 (文本或单键)
    def do_type(self, text, interval=0.05):
        get_time()
        pyautogui.write(text, interval=interval)
        print(f"执行输入: {text}")

    # 5. 快捷键 (预留)
    def do_hotkey(self, keys):
        get_time()
        pyautogui.hotkey(*keys)
        print(f"执行快捷键: {keys}")


# 测试代码
executor = ActionExecutor()
# 模拟从 JSON 读取的数据执行
executor.execute({"action": "click", "params": {"x": 100, "y": 200, "clicks": 2}})
executor.execute({"action": "type", "params": {"text": "Hello World"}})"""