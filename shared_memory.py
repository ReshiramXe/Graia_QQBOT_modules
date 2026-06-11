# ============================================================
# 共享对话记忆模块
# ai_chat_group.py / agent_mode.py / ai_auto_reply.py 共用
# 格式: OpenAI 兼容 {role, content, name}
#
# 自动总结: 每 10 轮对话自动调用 LLM 压缩旧消息为一条摘要
# ============================================================

import logging

logger = logging.getLogger(__name__)

# {group_id: [{"role": "user"/"assistant"/"tool", "content": "...", "name": "..."}]}
chat_histories = {}

MAX_HISTORY = 20           # 每个群最多保留的完整消息条数
SUMMARY_INTERVAL = 10      # 每 N 轮对话（user+assistant 算1轮）触发一次总结

# {group_id: user_message_count}
_round_counters: dict[int, int] = {}

# 总结器（由 ai_chat_group.py 在启动时初始化）
_summarizer_client = None
_summarizer_model = "deepseek-chat"


def init_summarizer(client, model: str = "deepseek-chat"):
    """初始化自动总结功能，传入 AsyncOpenAI 客户端实例"""
    global _summarizer_client, _summarizer_model
    _summarizer_client = client
    _summarizer_model = model


def get_history(group_id: int) -> list:
    """获取指定群的对话历史"""
    return chat_histories.get(group_id, [])


async def append_history(group_id: int, role: str, content: str, name: str = None):
    """追加一条对话记录。role='user' 时计数，达到阈值自动触发总结。"""
    if group_id not in chat_histories:
        chat_histories[group_id] = []
        _round_counters[group_id] = 0

    entry = {"role": role, "content": content}
    if name:
        entry["name"] = name
    chat_histories[group_id].append(entry)

    # 限制最大长度（防止极端情况）
    if len(chat_histories[group_id]) > MAX_HISTORY * 3:
        chat_histories[group_id] = chat_histories[group_id][-MAX_HISTORY:]

    # 只统计用户消息作为"轮"的计数
    if role == "user":
        _round_counters[group_id] += 1

    # 达到阈值 → 自动总结
    if _round_counters[group_id] >= SUMMARY_INTERVAL:
        await _auto_summarize(group_id)
        _round_counters[group_id] = 0


def clear_history(group_id: int):
    """清除指定群的对话历史"""
    chat_histories.pop(group_id, None)
    _round_counters.pop(group_id, None)


# ============================================================
# 内部：自动总结
# ============================================================

async def _auto_summarize(group_id: int):
    """将旧对话压缩为一条摘要，保留最近的消息"""
    if _summarizer_client is None:
        return  # 总结器未初始化，跳过

    history = chat_histories.get(group_id, [])
    if len(history) < 6:
        return  # 太少不值得总结

    # 取前 2/3 的消息做总结，保留后 1/3
    split_at = len(history) * 2 // 3
    old_messages = history[:split_at]
    recent_messages = history[split_at:]

    # 构建总结输入
    lines = []
    for m in old_messages:
        name = m.get("name", "")
        prefix = f"[{name}]: " if name else ""
        lines.append(f"{prefix}{m['content'][:300]}")
    summary_input = "请将以下对话历史总结为一段简洁的摘要，保留关键信息（人名、话题、结论）：\n\n" + "\n".join(lines)

    try:
        response = await _summarizer_client.chat.completions.create(
            model=_summarizer_model,
            messages=[
                {"role": "system", "content": "你是一个对话总结助手。用中文简洁总结，保留关键信息。"},
                {"role": "user", "content": summary_input},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        summary = response.choices[0].message.content.strip()

        # 替换：摘要 + 最近消息
        chat_histories[group_id] = [
            {"role": "system", "content": f"[对话历史摘要] {summary}"}
        ] + recent_messages

        logger.info(f"群 {group_id} 自动总结: {len(old_messages)} 条 → 1 条摘要")
    except Exception as e:
        logger.warning(f"群 {group_id} 总结失败: {e}")
        # 失败时直接丢弃旧消息，保留最近的
        chat_histories[group_id] = recent_messages
