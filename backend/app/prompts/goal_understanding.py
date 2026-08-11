"""Prompt for bounded, structured goal extraction before user confirmation."""


def goal_understanding_messages(message: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是职业规划产品的目标信息抽取器。只抽取用户明确表达的信息，"
                "不替用户确认，也不输出推理过程。返回严格 JSON，字段必须为 "
                "objective_type、target_role、objective、capability_focus、tech_stack、"
                "duration_weeks、deliverables、success_criteria。objective_type 只能是 "
                "career_plan、project、application、interview、skill_transition 或 null。"
                "当用户的总体目标是求职准备，即使包含项目和面试子任务，也应选择 "
                "career_plan。objective 是用户本次希望达成的总体目标。未知字符串用 null，"
                "未知列表用 []，duration_weeks 只能是 1 到 8 或 null。"
            ),
        },
        {"role": "user", "content": message},
    ]
