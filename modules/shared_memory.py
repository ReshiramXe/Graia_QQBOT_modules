# ============================================================
# 共享对话记忆模块
# ai_chat_group.py / agent_mode.py / ai_auto_reply.py 共用
# 格式: OpenAI 兼容 {role, content, name}
# ============================================================

# {group_id: [{"role": "user"/"assistant"/"tool", "content": "...", "name": "..."}]}
chat_histories = {}

MAX_HISTORY = 40  # 每个群最多保留的对话条数


def get_history(group_id: int) -> list:
    """获取指定群的对话历史"""
    return chat_histories.get(group_id, [])


def append_history(group_id: int, role: str, content: str, name: str = None):
    """追加一条对话记录，自动裁剪到 MAX_HISTORY"""
    if group_id not in chat_histories:
        chat_histories[group_id] = []
    entry = {"role": role, "content": content}
    if name:
        entry["name"] = name
    chat_histories[group_id].append(entry)
    if len(chat_histories[group_id]) > MAX_HISTORY:
        chat_histories[group_id] = chat_histories[group_id][-MAX_HISTORY:]


def clear_history(group_id: int):
    """清除指定群的对话历史"""
    chat_histories.pop(group_id, None)
