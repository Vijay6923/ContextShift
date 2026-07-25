"""Framework-agnostic representation of a single conversation message."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Message:
    """
    A single turn in a conversation, as seen by ContextShift's strategies.

    This is the library's canonical message representation, deliberately
    decoupled from how a message is stored or transported. It carries only
    the information a context-management strategy needs to decide whether
    to keep, prune, or summarize a message -- nothing about how, where, or
    whether it is persisted.

    Invariants:
        - `role` and `content` are required; every other field has a
          default appropriate for a freshly-created, unpinned message
          whose token count has not yet been measured.
        - Instances are immutable. A strategy that wants a modified
          version of a message (e.g. summarized content) constructs a new
          Message rather than mutating this one, so callers can rely on an
          input list of Messages being unchanged after a strategy call.

    Fields present on this application's current database model are
    deliberately absent here, on purpose rather than by oversight:
        - no `id`: identity is owned by whatever stores the message (a
          database row, a line in a dataset file, a position in a list),
          not by the message itself. A future consumer that needs a
          stable identifier can carry one alongside a Message rather than
          the type assuming one particular storage scheme exists.
        - no `is_archived`: archiving is a persistence-layer soft-delete
          concept specific to how one application models conversation
          history. By the time a Message reaches this library, only
          messages meant to be considered for context are expected to be
          in the list at all -- filtering already happened upstream.
        - no `timestamp`: no strategy in the current design actually
          needs one -- the existing pin/recency algorithm relies entirely
          on input-list order, not wall-clock time. Adding a field with no
          concrete consumer is exactly the premature API surface this
          type is trying to avoid; see
          docs/decisions/0002-minimal-public-api-surface.md.
          If a future strategy genuinely needs temporal reasoning, adding
          an optional field later is a purely additive, non-breaking
          change.

    Args:
        role: Who sent the message. The current application uses "user",
            "assistant", and "system", but this is left as a plain `str`
            rather than a narrower literal type so that future roles
            (e.g. "tool", for tool-calling conversations) don't require a
            type change to represent.
        content: The message text.
        is_pinned: Whether this message must always be kept in context,
            regardless of token budget or recency. Strategies that don't
            support pinning may simply ignore this field.
        token_count: Token count for `content`, as measured by whatever
            Tokenizer produced it (see contextshift.tokenizers), or `None`
            if it has not been measured yet. `None` and `0` are
            deliberately distinct: `0` means a Tokenizer measured this
            content and determined it costs zero tokens (possible for,
            say, a content-less tool-call message); `None` means no
            measurement has happened at all. Code that aggregates token
            counts should treat `None` as missing data, not silently as
            zero.
    """

    role: str
    content: str
    is_pinned: bool = False
    token_count: int | None = None
