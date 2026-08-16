from tests.fixtures.legacy.config import Config
from tests.fixtures.legacy import token_manager

def build_context(messages: list) -> list:
    """
    Assembles the final prompt array for Groq.
    Algorithm:
    1. Separate pinned from non-pinned.
    2. Last RECENT_BUFFER non-pinned are 'recent'.
    3. Older non-pinned are 'candidates'.
    4. Assemble context and prune candidates if over limit.
    """
    pinned = [m for m in messages if m.is_pinned]
    non_pinned = [m for m in messages if not m.is_pinned]
    
    recent = non_pinned[-Config.RECENT_BUFFER:] if non_pinned else []
    candidates = non_pinned[:-Config.RECENT_BUFFER] if len(non_pinned) > Config.RECENT_BUFFER else []
    
    # 5. Assemble draft context
    # format: [{"role": m.role, "content": m.content}, ...]
    def to_openai_format(msg_objs):
        return [{"role": m.role, "content": m.content} for m in msg_objs]

    # Initial check
    token_manager.log_token_info("initial context assembly", messages)
    
    final_messages = pinned + candidates + recent
    
    # Prune candidates one by one from oldest if over limit
    while candidates and token_manager.is_over_limit(final_messages):
        candidates.pop(0)
        final_messages = pinned + candidates + recent
        token_manager.log_token_info("candidate pruning", final_messages)
        
    # If still over limit, prune recent one by one (excluding the very last one)
    while len(recent) > 1 and token_manager.is_over_limit(final_messages):
        recent.pop(0)
        final_messages = pinned + candidates + recent
        token_manager.log_token_info("recent pruning", final_messages)
        
    # Prepend system message
    context = [
        {
            "role": "system",
            "content": "You are a helpful assistant. The conversation history below may include a summary of earlier messages."
        }
    ]
    
    context.extend(to_openai_format(final_messages))
    return context
