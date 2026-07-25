from config import Config

def estimate_tokens(text: str) -> int:
    """Simple heuristic: words * 1.3"""
    if not text:
        return 0
    words = len(text.split())
    return max(1, int(words * 1.3))

def get_total_tokens(messages: list) -> int:
    """Sum token_count of all messages in the list."""
    return sum(msg.token_count for msg in messages)

def is_over_limit(messages: list) -> bool:
    """Returns True if total token count exceeds MAX_TOKENS - TOKEN_SAFETY_MARGIN."""
    total = get_total_tokens(messages)
    return total > (Config.MAX_TOKENS - Config.TOKEN_SAFETY_MARGIN)

def get_token_stats(messages: list) -> dict:
    """Returns token stats dictionary."""
    current = get_total_tokens(messages)
    percentage = (current / Config.MAX_TOKENS) * 100
    return {
        "current_tokens": current,
        "max_tokens": Config.MAX_TOKENS,
        "percentage": round(percentage, 2)
    }

def log_token_info(stage: str, messages: list):
    """Prints debug line to stdout."""
    stats = get_token_stats(messages)
    print(f"[TOKEN LOG] After {stage}: {len(messages)} messages, {stats['current_tokens']} tokens ({stats['percentage']}%)")
