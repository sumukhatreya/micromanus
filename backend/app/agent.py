"""The agent loop — the core of the project (PLAN.md §B5).

Reconstructs the conversation from the DB (static system prompt first, then the
user/assistant history so the prefix repeats across turns for prompt caching),
then iterates: call the model → log usage → if it wants tools, run them, persist
a tool_event per call for the polling UI, and feed results back; otherwise
persist the final assistant message and stop.

Tool-call message ordering matters (PLAN.md pitfall #3): the assistant message
carrying `tool_calls` is appended to the LLM history BEFORE the matching
`role:"tool"` result messages, each with its `tool_call_id`.
"""

import json
import logging

from app.llm import ActiveKey, compute_cost
from app.supabase_client import get_supabase
from app.tools import TOOLS, execute_tool, tool_event_payload

logger = logging.getLogger(__name__)

MAX_ITER = 10

SYSTEM_PROMPT = """\
You are MicroManus, a deep-research AI agent. Your job is to answer the user's \
question thoroughly and accurately using live web research.

Method:
- Decompose the question into the specific facts you need to find.
- Use the web_search tool multiple times, refining your queries between \
searches, before you attempt a final answer. Do not answer from memory alone \
when the topic is factual, recent, or verifiable.
- Read the returned snippets critically and search again to fill gaps or \
resolve contradictions.
- Synthesize a clear, well-structured answer and cite the source URLs you \
relied on inline.

Reports:
- When the user asks for a report, document, or something downloadable, call \
create_pdf_report with a descriptive title and the full report in Markdown. \
A download button appears automatically — do NOT include any URL or link to \
the PDF in your response. Just tell the user the report is ready.

Style: be concise and direct for simple questions; be thorough and organized \
for research questions. Always ground claims in your search results."""


def _build_history(thread_id: str) -> list[dict]:
    """LLM message list from persisted user/assistant turns (tool_events are
    UI-only and excluded)."""
    supabase = get_supabase()
    res = (
        supabase.table("messages")
        .select("role, content")
        .eq("thread_id", thread_id)
        .order("created_at")
        .execute()
    )
    history = []
    for row in res.data or []:
        if row["role"] in ("user", "assistant"):
            history.append({"role": row["role"], "content": row["content"]})
    return history


def _insert_message(
    thread_id: str,
    role: str,
    content: str,
    artifact_url: str | None = None,
    artifact_title: str | None = None,
) -> dict:
    supabase = get_supabase()
    payload = {"thread_id": thread_id, "role": role, "content": content}
    if artifact_url:
        payload["artifact_url"] = artifact_url
    if artifact_title:
        payload["artifact_title"] = artifact_title
    res = supabase.table("messages").insert(payload).execute()
    return res.data[0]


def _log_usage(user_id: str, thread_id: str, model: str, usage) -> None:
    if usage is None:
        return
    supabase = get_supabase()
    supabase.table("usage_logs").insert(
        {
            "user_id": user_id,
            "thread_id": thread_id,
            "model": model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cached_tokens": usage.cached_tokens,
            "cost_usd": usage.cost_usd,
        }
    ).execute()


def _is_cancelled(thread_id: str) -> bool:
    supabase = get_supabase()
    res = (
        supabase.table("threads")
        .select("cancelled")
        .eq("id", thread_id)
        .limit(1)
        .execute()
    )
    return bool(res.data and res.data[0].get("cancelled"))


def run_agent(user_id: str, thread_id: str, active: ActiveKey, client) -> dict:
    """Run one full agent turn for the latest user message in `thread_id`.

    Returns the persisted final assistant message row. Raises on hard LLM
    failures (e.g. a bad API key) so the caller can refund the credit and surface
    a clean error.
    """
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _build_history(thread_id)
    last_artifact_url: str | None = None
    last_artifact_title: str | None = None

    interrupted = False

    for _ in range(MAX_ITER):
        if _is_cancelled(thread_id):
            interrupted = True
            break

        completion = client.chat.completions.create(
            model=active.model,
            messages=llm_messages,
            tools=TOOLS,
        )

        # Log usage/cost for this call (PLAN.md §B4 caching section).
        usage = getattr(completion, "usage", None)
        if usage is not None:
            _log_usage(
                user_id,
                thread_id,
                active.model,
                compute_cost(active.provider, active.model, usage),
            )

        choice = completion.choices[0].message
        tool_calls = getattr(choice, "tool_calls", None)

        if not tool_calls:
            if _is_cancelled(thread_id):
                interrupted = True
                break
            content = choice.content or "I wasn't able to produce an answer."
            return _insert_message(thread_id, "assistant", content, last_artifact_url, last_artifact_title)

        # Append the assistant tool-call message BEFORE the tool results.
        llm_messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            if _is_cancelled(thread_id):
                interrupted = True
                break

            name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}

            _insert_message(
                thread_id, "tool_event", json.dumps(tool_event_payload(name, arguments))
            )

            result_text, artifact_url, artifact_title = execute_tool(name, arguments, user_id)
            if artifact_url:
                last_artifact_url = artifact_url
                last_artifact_title = artifact_title

            llm_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                }
            )

        if interrupted:
            break

    if interrupted:
        get_supabase().table("threads").update({"cancelled": False}).eq("id", thread_id).execute()
        return _insert_message(
            thread_id,
            "error",
            "Search was interrupted — please try again.",
        )

    logger.warning("Agent hit MAX_ITER for thread %s", thread_id)
    return _insert_message(
        thread_id,
        "assistant",
        "I ran several research steps but couldn't finish within the step limit. "
        "Please try narrowing the question.",
        last_artifact_url,
        last_artifact_title,
    )
