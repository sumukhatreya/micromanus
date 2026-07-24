"""Agent tools: web_search (Tavily) and create_pdf_report (PLAN.md §B5).

Both are exposed to the model in OpenAI function-calling format via TOOLS. The
agent loop (agent.py) calls `execute_tool` for each tool_call the model emits.
`execute_tool` returns (result_text, artifact_url): result_text is fed back to
the model as the tool message; artifact_url is set only by create_pdf_report and
gets attached to the final assistant message so the UI can offer a download.
"""

import json
import logging

from tavily import TavilyClient

from app.config import settings
from app.pdf import render_markdown_pdf
from app.storage import upload_pdf

logger = logging.getLogger(__name__)

# OpenAI function-calling schema advertised to the model on every turn.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information. Returns the top results "
                "with title, URL, and a content snippet. Use repeatedly with "
                "refined queries to research a topic before answering."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_pdf_report",
            "description": (
                "Render a titled report written in Markdown into a downloadable "
                "PDF. Call this only when the user asks for a report, document, or "
                "downloadable artifact. Returns a URL to the generated PDF."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The report title.",
                    },
                    "markdown_content": {
                        "type": "string",
                        "description": (
                            "The full report body in Markdown (headings, lists, "
                            "links, etc.)."
                        ),
                    },
                },
                "required": ["title", "markdown_content"],
            },
        },
    },
]


def _web_search(query: str) -> str:
    """Tavily search → JSON string of up to 5 {title, url, content} results."""
    if not settings.tavily_api_key:
        return json.dumps({"error": "Web search is not configured on the server."})
    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        resp = client.search(query=query, max_results=5)
    except Exception as exc:  # network / quota / auth — report, don't crash the run
        logger.warning("Tavily search failed for %r: %s", query, exc)
        return json.dumps({"error": f"Search failed: {exc}"})

    results = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "content": r.get("content"),
        }
        for r in (resp.get("results") or [])
    ]
    return json.dumps({"query": query, "results": results})


def _create_pdf_report(user_id: str, title: str, markdown_content: str) -> tuple[str, str | None, str | None]:
    """Render + upload a PDF; return (message_for_model, artifact_url, title)."""
    try:
        pdf_bytes = render_markdown_pdf(title, markdown_content)
        url = upload_pdf(user_id, pdf_bytes, title)
    except Exception as exc:
        logger.warning("create_pdf_report failed: %s", exc)
        return json.dumps({"error": f"Could not create the PDF: {exc}"}), None, None
    return (
        json.dumps({"status": "created", "title": title, "note": "A download button is automatically shown to the user. Do NOT include any URL or link in your response."}),
        url,
        title,
    )


def execute_tool(name: str, arguments: dict, user_id: str) -> tuple[str, str | None, str | None]:
    """Dispatch a tool call. Returns (result_text, artifact_url_or_None, artifact_title_or_None)."""
    if name == "web_search":
        return _web_search(arguments.get("query", "")), None, None
    if name == "create_pdf_report":
        return _create_pdf_report(
            user_id,
            arguments.get("title", "Report"),
            arguments.get("markdown_content", ""),
        )
    return json.dumps({"error": f"Unknown tool: {name}"}), None, None


def tool_event_payload(name: str, arguments: dict) -> dict:
    """Short JSON blob persisted as a tool_event message for the UI to render."""
    if name == "web_search":
        return {"tool": "web_search", "query": arguments.get("query", "")}
    if name == "create_pdf_report":
        return {"tool": "create_pdf_report", "title": arguments.get("title", "Report")}
    return {"tool": name}
