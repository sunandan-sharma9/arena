"""The Sidecar agent: one tool-use loop, two run modes, any domain.

naive     -- always claude-sonnet-5, no prompt caching, no streaming.
optimized -- routes between haiku/sonnet by query shape, caches the
             system prompt + tools, streams (so we can measure TTFT).

Every function here takes a `domain` module -- mock_helpdesk or
mock_parking -- rather than importing one directly, so the same engine
drives either "legacy system" being retrofitted. A domain module exposes:
SYSTEM_PROMPT, TOOL_SPECS, TOOL_REGISTRY, MUTATING_TOOLS,
ROUTING_WRITE_SIGNALS, ROUTING_REASONING_SIGNALS, EVAL_TASKS, reset().
"""

from __future__ import annotations

import os
import pathlib
import time

import anthropic
from anthropic.types import TextBlock, ToolUseBlock

from economics import cost_for_call

# ── Credentials ───────────────────────────────────────────────────────────


def _resolve_env_file():
    here = pathlib.Path.cwd().resolve()
    for d in [here, *here.parents]:
        if (d / ".env").is_file():
            return d / ".env"
    return None


def _load_env():
    if os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-"):
        return

    # Local dev: read from .env (walks up from cwd, same as the course notebooks).
    env_file = _resolve_env_file()
    if env_file:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "ANTHROPIC_API_KEY" and v.startswith("sk-ant-"):
                    os.environ["ANTHROPIC_API_KEY"] = v
    if os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-"):
        return

    # Streamlit Community Cloud: no .env file there -- the key comes in via
    # the app's "Secrets" panel instead, exposed as st.secrets.
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key.startswith("sk-ant-"):
            os.environ["ANTHROPIC_API_KEY"] = key
    except Exception:
        pass


_load_env()
client = anthropic.Anthropic()

NAIVE_MODEL = "claude-sonnet-5"
MAX_TOKENS = 1024

# ── Model routing (optimized mode only) ─────────────────────────────────


def choose_model(query: str, domain) -> str:
    q = query.lower()
    if any(s in q for s in domain.ROUTING_WRITE_SIGNALS):
        return "claude-sonnet-5"
    if any(s in q for s in domain.ROUTING_REASONING_SIGNALS):
        return "claude-sonnet-5"
    return "claude-haiku-4-5"


# ── Tool execution ───────────────────────────────────────────────────────


def execute_tool(name: str, tool_input: dict, domain) -> str:
    try:
        return str(domain.TOOL_REGISTRY[name](**tool_input))
    except Exception as e:  # noqa: BLE001 -- surfaced to the model as a tool error
        return f"Error: {e}"


def is_mutating(name: str, domain) -> bool:
    return name in domain.MUTATING_TOOLS


# ── One Claude call, instrumented ────────────────────────────────────────


def system_and_tools_for(domain, context: str):
    """context: 'engineered' (policy doc + rich tool specs) or 'bare' (generic
    prompt + vague tool specs) -- same tools, same models, different context."""
    if context == "bare":
        return domain.BARE_SYSTEM_PROMPT, domain.BARE_TOOL_SPECS
    return domain.SYSTEM_PROMPT, domain.TOOL_SPECS


def call_claude(messages: list, mode: str, domain, query_for_routing: str = "",
                 context: str = "engineered"):
    """Make one Claude call under the given mode/context, against the given
    domain. Returns (response, metrics)."""
    system_prompt, tool_specs = system_and_tools_for(domain, context)

    if mode == "naive":
        model = NAIVE_MODEL
        start = time.time()
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tool_specs,
            messages=messages,
        )
        elapsed = time.time() - start
        ttft = elapsed  # no streaming signal in naive mode -- TTFT == TTC
    else:
        model = choose_model(query_for_routing, domain)
        start = time.time()
        ttft = None
        with client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=tool_specs,
            messages=messages,
        ) as stream:
            for event in stream:
                if ttft is None and event.type == "content_block_delta":
                    ttft = time.time() - start
            response = stream.get_final_message()
        elapsed = time.time() - start
        if ttft is None:
            ttft = elapsed

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
    }
    metrics = {
        "model": model,
        "mode": mode,
        "context": context,
        "latency_s": elapsed,
        "ttft_s": ttft,
        "usage": usage,
        "cost_usd": cost_for_call(model, usage),
    }
    return response, metrics


# ── Full-auto loop (used by the eval harness -- auto-approves writes) ────


def parse_transcript(messages: list) -> dict:
    tool_calls, final_text = [], ""
    for msg in messages:
        if msg["role"] != "assistant":
            continue
        for block in msg["content"]:
            if isinstance(block, ToolUseBlock):
                tool_calls.append({"name": block.name, "arguments": block.input, "id": block.id})
            elif isinstance(block, TextBlock):
                final_text = block.text
    return {"tool_calls": tool_calls, "final_text": final_text}


def run_agent_full(query: str, mode: str, domain, max_turns: int = 6,
                    context: str = "engineered") -> dict:
    messages = [{"role": "user", "content": query}]
    metrics_log = []
    response = None
    for _ in range(max_turns):
        response, metrics = call_claude(messages, mode, domain, query_for_routing=query, context=context)
        metrics_log.append(metrics)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        tool_calls = [b for b in response.content if isinstance(b, ToolUseBlock)]
        tool_results = []
        for call in tool_calls:
            result = execute_tool(call.name, call.input, domain)
            tool_results.append({"type": "tool_result", "tool_use_id": call.id, "content": result})
        messages.append({"role": "user", "content": tool_results})
    parsed = parse_transcript(messages)
    return {"messages": messages, "metrics_log": metrics_log, "final_text": parsed["final_text"],
            "tool_calls": parsed["tool_calls"]}


# ── Eval harness (graders are domain-agnostic; tasks live on the domain) ──


def _grade_tool_use(result: dict, check: dict) -> bool:
    expected = check.get("arguments")
    for call in result["tool_calls"]:
        if call["name"] != check["tool_name"]:
            continue
        if expected is None:
            return True
        actual = call.get("arguments", {})
        if all(str(actual.get(k, "")).lower() == str(v).lower() for k, v in expected.items()):
            return True
    return False


def _grade_response_contains(result: dict, check: dict) -> bool:
    return check["text"].lower() in result["final_text"].lower()


def _grade_tool_call_count(result: dict, check: dict) -> bool:
    count = sum(1 for c in result["tool_calls"] if c["name"] == check["tool_name"])
    return count >= check.get("min_calls", 1)


GRADER_REGISTRY = {
    "tool_use": _grade_tool_use,
    "response_contains": _grade_response_contains,
    "tool_call_count": _grade_tool_call_count,
}


def run_eval_task(task: dict, mode: str, domain) -> dict:
    domain.reset()  # each task starts from a clean, independent data state
    raw = run_agent_full(task["query"], mode, domain)
    result = {"tool_calls": raw["tool_calls"], "final_text": raw["final_text"]}
    grades = [
        {"check": c, "passed": GRADER_REGISTRY[c["type"]](result, c)}
        for c in task["graders"]
    ]
    return {
        "task_id": task["id"],
        "category": task.get("category", ""),
        "query": task["query"],
        "passed": all(g["passed"] for g in grades),
        "grades": grades,
        "metrics_log": raw["metrics_log"],
        "final_text": raw["final_text"],
    }


def run_eval_suite(mode: str, domain) -> list:
    results = [run_eval_task(t, mode, domain) for t in domain.EVAL_TASKS]
    domain.reset()  # leave a clean slate for the interactive chat afterwards
    return results
