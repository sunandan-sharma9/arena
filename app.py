"""Sidecar -- a chat front end bolted onto a mock legacy system (helpdesk
ticketing, or SF parking/street-cleaning), with a live before/after
economics panel, a human-in-the-loop confirmation gate on any mutating
action, and an Arena mode where a red-team agent probes the defender live.
Same engine, swappable domain.

Run: streamlit run app.py
"""

import streamlit as st
from anthropic.types import TextBlock, ToolUseBlock

import agent
import economics
import mock_helpdesk
import mock_parking
import redteam
import ui_theme

st.set_page_config(page_title="Sidecar", page_icon="\U0001F50C", layout="wide")
ui_theme.inject()

DOMAIN_META = {
    "helpdesk": {
        "module": mock_helpdesk,
        "label": "\U0001F3AB Ticket Desk (helpdesk)",
        "short": "Ticket Desk",
        "title": "Sidecar -- Ticket Desk",
        "caption": (
            "Talk to the ticketing system instead of clicking through it. "
            "Mutating actions (reassign / close / re-prioritize) pause for your confirmation."
        ),
        "chat_placeholder": "Ask about tickets, e.g. \"How many open tickets does Priya have?\"",
        "reset_label": "Reset tickets",
    },
    "parking": {
        "module": mock_parking,
        "label": "\U0001F17F️ Meter Minder (SF parking)",
        "short": "Meter Minder",
        "title": "Sidecar -- Meter Minder",
        "caption": (
            "Talk to SF's parking & street-cleaning systems instead of juggling apps. "
            "Mutating actions (extend session / set reminder / file dispute) pause for your confirmation."
        ),
        "chat_placeholder": "Ask about parking, e.g. \"Is my car okay where it's parked?\"",
        "reset_label": "Reset parking data",
    },
}
DOMAIN_KEYS = list(DOMAIN_META.keys())

# Arena is fixed to Meter Minder -- no domain picker there, it's the domain
# the attacker/defender/judge loop was tuned and tested against.
ARENA_DOMAIN_KEY = "parking"
ARENA_META = DOMAIN_META[ARENA_DOMAIN_KEY]

# ── Session state ─────────────────────────────────────────────────────────

if "domain_key" not in st.session_state:
    st.session_state.domain_key = DOMAIN_KEYS[0]
if "raw_messages" not in st.session_state:
    st.session_state.raw_messages = []
if "display" not in st.session_state:
    st.session_state.display = []
if "pending_calls" not in st.session_state:
    st.session_state.pending_calls = None
if "metrics_log" not in st.session_state:
    st.session_state.metrics_log = []
if "mode" not in st.session_state:
    st.session_state.mode = "optimized"
if "context" not in st.session_state:
    st.session_state.context = "engineered"
if "eval_results" not in st.session_state:
    st.session_state.eval_results = None
if "token_cache" not in st.session_state:
    st.session_state.token_cache = {}
if "view" not in st.session_state:
    st.session_state.view = "chat"
if "arena_rounds" not in st.session_state:
    st.session_state.arena_rounds = []


def get_token_count(domain_key: str, context: str):
    """Exact system+tools token count via count_tokens, cached per (domain, context)
    so the inspector doesn't fire a fresh API call on every Streamlit rerun."""
    key = (domain_key, context)
    if key not in st.session_state.token_cache:
        sys_prompt, tool_specs = agent.system_and_tools_for(DOMAIN_META[domain_key]["module"], context)
        try:
            resp = agent.client.messages.count_tokens(
                model="claude-haiku-4-5",
                system=[{"type": "text", "text": sys_prompt}],
                tools=tool_specs,
                messages=[{"role": "user", "content": "hi"}],
            )
            st.session_state.token_cache[key] = resp.input_tokens
        except Exception:
            st.session_state.token_cache[key] = None
    return st.session_state.token_cache[key]


def _reset_conversation_state():
    st.session_state.raw_messages = []
    st.session_state.display = []
    st.session_state.pending_calls = None
    st.session_state.metrics_log = []
    st.session_state.eval_results = None


def _last_user_text() -> str:
    for msg in reversed(st.session_state.raw_messages):
        if msg["role"] == "user" and isinstance(msg["content"], str):
            return msg["content"]
    return ""


def process_turn(domain):
    """Run the agent loop until it needs a human decision or is done."""
    mode = st.session_state.mode
    context = st.session_state.context
    query_for_routing = _last_user_text()
    while True:
        response, metrics = agent.call_claude(
            st.session_state.raw_messages, mode, domain,
            query_for_routing=query_for_routing, context=context,
        )
        st.session_state.metrics_log.append(metrics)
        st.session_state.raw_messages.append({"role": "assistant", "content": response.content})
        for block in response.content:
            if isinstance(block, TextBlock) and block.text.strip():
                st.session_state.display.append({"role": "assistant", "text": block.text})

        if response.stop_reason != "tool_use":
            return

        tool_calls = [b for b in response.content if isinstance(b, ToolUseBlock)]
        if any(agent.is_mutating(c.name, domain) for c in tool_calls):
            st.session_state.pending_calls = [
                {"id": c.id, "name": c.name, "input": c.input} for c in tool_calls
            ]
            return

        tool_results = []
        for c in tool_calls:
            result = agent.execute_tool(c.name, c.input, domain)
            st.session_state.display.append(
                {"role": "tool", "text": f"{c.name}({c.input}) → {result}"}
            )
            tool_results.append({"type": "tool_result", "tool_use_id": c.id, "content": result})
        st.session_state.raw_messages.append({"role": "user", "content": tool_results})


def resolve_pending(domain, confirm: bool):
    tool_results = []
    for call in st.session_state.pending_calls:
        if agent.is_mutating(call["name"], domain) and not confirm:
            result = "User declined this action via the confirmation gate."
        else:
            result = agent.execute_tool(call["name"], call["input"], domain)
        st.session_state.display.append(
            {"role": "tool", "text": f"{call['name']}({call['input']}) → {result}"}
        )
        tool_results.append({"type": "tool_result", "tool_use_id": call["id"], "content": result})
    st.session_state.raw_messages.append({"role": "user", "content": tool_results})
    st.session_state.pending_calls = None
    process_turn(domain)


# ── Sidebar ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("\U0001F50C Sidecar")
    st.caption("Agent-as-a-feature retrofit, demo build")

    # Arena is the only view now -- Chat still exists in code (render_chat_view)
    # but isn't exposed in the UI.
    st.session_state.view = "arena"

    st.divider()

    if st.session_state.view == "chat":
        selected_key = st.selectbox(
            "Domain",
            options=DOMAIN_KEYS,
            index=DOMAIN_KEYS.index(st.session_state.domain_key),
            format_func=lambda k: DOMAIN_META[k]["label"],
            help="Same engine (routing/caching/streaming/confirm-gate) bolted onto a different legacy system.",
        )
        if selected_key != st.session_state.domain_key:
            st.session_state.domain_key = selected_key
            _reset_conversation_state()
            st.rerun()
        meta = DOMAIN_META[st.session_state.domain_key]
        domain = meta["module"]
    else:
        st.caption(f"Domain: {ARENA_META['label']} -- fixed for Arena mode")
        meta = ARENA_META
        domain = ARENA_META["module"]

    with st.container(border=True):
        st.markdown('<div class="sc-section-label">Inference</div>', unsafe_allow_html=True)
        st.session_state.mode = st.radio(
            "Inference mode",
            options=["optimized", "naive"],
            index=0 if st.session_state.mode == "optimized" else 1,
            format_func=lambda m: "⚡ Optimized (routing + cache + stream)" if m == "optimized"
            else "\U0001F40C Naive (always Sonnet, no cache)",
            help="Naive mode reproduces the 'works in the demo, expensive in prod' baseline.",
            label_visibility="collapsed",
        )

        new_context = st.radio(
            "Context quality",
            options=["engineered", "bare"],
            index=0 if st.session_state.context == "engineered" else 1,
            format_func=lambda c: "\U0001F9E0 Engineered (policy doc + rich tool specs)" if c == "engineered"
            else "\U0001FAE5 Bare (generic prompt + vague tools)",
            help="Same tools, same models, same routing -- only the system prompt and tool "
                 "descriptions differ. In Arena mode this is the defender's loadout.",
        )
        if new_context != st.session_state.context:
            st.session_state.context = new_context
            _reset_conversation_state()
            st.rerun()

        with st.expander(f"\U0001F50D Context inspector -- {st.session_state.context}"):
            sys_prompt, tool_specs = agent.system_and_tools_for(domain, st.session_state.context)
            eng_tok = get_token_count(st.session_state.domain_key, "engineered")
            bare_tok = get_token_count(st.session_state.domain_key, "bare")
            if eng_tok and bare_tok:
                st.caption(f"Engineered: ~{eng_tok:,} tokens  ·  Bare: ~{bare_tok:,} tokens  ·  {eng_tok / bare_tok:.0f}x more context")
            st.write(f"**Active system prompt:** {len(sys_prompt):,} chars, {len(tool_specs)} tools")
            st.write(
                "Tool descriptions: "
                + ("detailed, grounded in the policy doc below" if st.session_state.context == "engineered"
                   else "one or two words each -- Claude has to guess what each tool actually does")
            )
            st.code(sys_prompt[:1800] + ("…" if len(sys_prompt) > 1800 else ""), language=None)

    with st.container(border=True):
        st.markdown('<div class="sc-section-label">Economics</div>', unsafe_allow_html=True)
        volume = st.slider("Requests / day at scale", 100, 20000, 1200, step=100)

    with st.container(border=True):
        st.markdown('<div class="sc-section-label">Data controls</div>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        if col_a.button("Reset chat", use_container_width=True):
            st.session_state.raw_messages = []
            st.session_state.display = []
            st.session_state.pending_calls = None
            st.rerun()
        if col_b.button(meta["reset_label"], use_container_width=True):
            domain.reset()
            st.rerun()

    with st.container(border=True):
        st.markdown('<div class="sc-section-label">Eval scorecard</div>', unsafe_allow_html=True)
        st.caption(f"Runs {len(domain.EVAL_TASKS)} tasks against both modes -- costs a handful of real API calls.")
        if st.button("Run eval scorecard", type="primary", use_container_width=True):
            with st.spinner("Running eval suite against naive and optimized..."):
                st.session_state.eval_results = {
                    "naive": agent.run_eval_suite("naive", domain),
                    "optimized": agent.run_eval_suite("optimized", domain),
                }
            st.rerun()


# ── Chat view ──────────────────────────────────────────────────────────────

def render_chat_view():
    left, right = st.columns([2, 1])

    with left:
        st.title(meta["title"])
        st.caption(meta["caption"])

        st.markdown(
            ui_theme.status_row(
                ui_theme.badge(meta["short"], "neutral"),
                ui_theme.badge(st.session_state.mode, "flow" if st.session_state.mode == "optimized" else "gate"),
                ui_theme.badge(st.session_state.context, "flow" if st.session_state.context == "engineered" else "gate"),
            ),
            unsafe_allow_html=True,
        )

        for item in st.session_state.display:
            if item["role"] == "tool":
                st.markdown(ui_theme.tool_log(item["text"]), unsafe_allow_html=True)
                continue
            role = "user" if item["role"] == "user" else "assistant"
            avatar = "\U0001F9D1" if role == "user" else "\U0001F916"
            with st.chat_message(role, avatar=avatar):
                st.write(item["text"])

        if st.session_state.pending_calls:
            st.markdown(
                ui_theme.confirm_card(st.session_state.pending_calls, lambda name: agent.is_mutating(name, domain)),
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirm and run", type="primary", use_container_width=True):
                resolve_pending(domain, confirm=True)
                st.rerun()
            if c2.button("✖️ Cancel", use_container_width=True):
                resolve_pending(domain, confirm=False)
                st.rerun()

        query = st.chat_input(meta["chat_placeholder"])
        if query and not st.session_state.pending_calls:
            st.session_state.display.append({"role": "user", "text": query})
            st.session_state.raw_messages.append({"role": "user", "content": query})
            process_turn(domain)
            st.rerun()

    with right:
        st.subheader("Live economics")

        if st.session_state.metrics_log:
            last = st.session_state.metrics_log[-1]
            ctx_kind = "flow" if last.get("context") == "engineered" else "gate"
            st.markdown(
                ui_theme.status_row(
                    ui_theme.badge(last["model"], "neutral"),
                    ui_theme.badge(last.get("context", "engineered"), ctx_kind),
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                ui_theme.kpi_row([
                    ("TTFT", f"{last['ttft_s']:.2f}s"),
                    ("Total latency", f"{last['latency_s']:.2f}s"),
                    ("Cost", f"${last['cost_usd']:.5f}"),
                ]),
                unsafe_allow_html=True,
            )
            if last["usage"]["cache_read_input_tokens"]:
                st.caption(
                    f"\U0001F4BE cache hit: {last['usage']['cache_read_input_tokens']} tokens served from cache"
                )
        else:
            st.caption("Send a message to see per-call metrics here.")

        st.divider()
        st.caption("Running totals, this session, by mode")
        for mode_key, label in [("naive", "\U0001F40C Naive"), ("optimized", "⚡ Optimized")]:
            mode_metrics = [m for m in st.session_state.metrics_log if m["mode"] == mode_key]
            summary = economics.summarize_metrics(mode_metrics)
            with st.container(border=True):
                st.write(f"**{label}** -- {summary['calls']} calls")
                if summary["calls"]:
                    kpis = [
                        ("Total cost", f"${summary['total_cost']:.5f}"),
                        ("p50 latency", f"{summary['p50_latency']:.2f}s"),
                    ]
                    if summary["avg_ttft"] is not None:
                        kpis.append(("Avg TTFT", f"{summary['avg_ttft']:.2f}s"))
                    st.markdown(ui_theme.kpi_row(kpis), unsafe_allow_html=True)
                    projected = economics.monthly_projection(
                        summary["total_cost"] / summary["calls"], volume
                    )
                    st.write(f"Projected @ {volume:,}/day: **${projected:,.2f}/mo**")

        naive_summary = economics.summarize_metrics(
            [m for m in st.session_state.metrics_log if m["mode"] == "naive"]
        )
        opt_summary = economics.summarize_metrics(
            [m for m in st.session_state.metrics_log if m["mode"] == "optimized"]
        )
        if naive_summary["calls"] and opt_summary["calls"]:
            naive_avg = naive_summary["total_cost"] / naive_summary["calls"]
            opt_avg = opt_summary["total_cost"] / opt_summary["calls"]
            if opt_avg > 0:
                st.success(f"Optimized is **{naive_avg / opt_avg:.1f}x cheaper per call** this session so far.")

    if st.session_state.eval_results:
        st.divider()
        st.header("Eval scorecard")
        ev_left, ev_right = st.columns(2)
        for mode_key, col in [("naive", ev_left), ("optimized", ev_right)]:
            results = st.session_state.eval_results[mode_key]
            passed = sum(1 for r in results if r["passed"])
            all_metrics = [m for r in results for m in r["metrics_log"]]
            summary = economics.summarize_metrics(all_metrics)
            with col:
                st.subheader(("\U0001F40C Naive" if mode_key == "naive" else "⚡ Optimized"))
                st.markdown(
                    ui_theme.kpi_row([
                        ("Pass rate", f"{passed}/{len(results)}"),
                        ("Total cost", f"${summary['total_cost']:.5f}"),
                        ("p50 latency", f"{summary['p50_latency']:.2f}s"),
                    ]),
                    unsafe_allow_html=True,
                )
                for r in results:
                    b = ui_theme.badge("pass", "pass") if r["passed"] else ui_theme.badge("fail", "fail")
                    st.markdown(f'{b} <code>{r["task_id"]}</code> -- {r["category"]}', unsafe_allow_html=True)


# ── Arena view ─────────────────────────────────────────────────────────────

def render_arena_view():
    head_col, info_col = st.columns([3, 1])
    with head_col:
        st.markdown(
            '<div class="sc-vs-title-row">'
            '<span class="sc-vs-mon">\U0001F479</span>'
            '<span class="sc-vs-title">AGENT&nbsp;VS&nbsp;AGENT</span>'
            '<span class="sc-vs-mon">\U0001F409</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="sc-vs-sub">One AI built to manipulate. One AI built to hold the line. '
            f'Nothing you\'re about to see is scripted -- the attacker invents the con, the {meta["short"]} '
            'defender has to survive it live. Flip Context to Bare mid-fight and watch the line actually break.</p>',
            unsafe_allow_html=True,
        )
    with info_col:
        st.markdown(
            ui_theme.app_info_card(
                "Sidecar: an AI agent framework retrofitted onto real systems, stress-tested live.",
                ["agentic tool use", "context engineering", "LLM-as-judge", "adversarial red-team"],
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        ui_theme.status_row(
            ui_theme.badge(meta["short"], "neutral"),
            ui_theme.badge(st.session_state.mode, "flow" if st.session_state.mode == "optimized" else "gate"),
            ui_theme.badge(st.session_state.context, "flow" if st.session_state.context == "engineered" else "gate"),
        ),
        unsafe_allow_html=True,
    )

    rounds = st.session_state.arena_rounds
    blocked = sum(1 for r in rounds if r["verdict"] == "BLOCKED")
    breached = sum(1 for r in rounds if r["verdict"] == "BREACHED")

    last_verdict = rounds[-1]["verdict"] if rounds else None
    st.markdown(ui_theme.battle_bar(blocked, breached, last_verdict), unsafe_allow_html=True)

    st.markdown(
        ui_theme.kpi_row([
            ("Rounds played", str(len(rounds))),
            ("\U0001F6E1️ Defender blocks", str(blocked)),
            ("\U0001F5E1️ Attacker breaches", str(breached)),
        ]),
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    if c1.button("▶ Run 1 round", use_container_width=True):
        with st.spinner("Attacker is crafting a move..."):
            r = redteam.play_round(domain, st.session_state.mode, st.session_state.context)
        st.session_state.arena_rounds.append(r)
        st.rerun()
    if c2.button("⏩ Run 5 rounds", type="primary", use_container_width=True):
        with st.spinner("Playing 5 rounds..."):
            for _ in range(5):
                r = redteam.play_round(domain, st.session_state.mode, st.session_state.context)
                st.session_state.arena_rounds.append(r)
        st.rerun()
    if c3.button("Reset arena", use_container_width=True):
        st.session_state.arena_rounds = []
        st.rerun()

    st.divider()
    for i, r in enumerate(reversed(rounds)):
        round_num = len(rounds) - i
        verdict_badge = ui_theme.badge("blocked", "pass") if r["verdict"] == "BLOCKED" else ui_theme.badge("breached", "fail")
        with st.container(border=True):
            st.markdown(
                f'<b>Round {round_num}</b> &nbsp; <code>{r["tactic"]}</code> &nbsp; {verdict_badge}',
                unsafe_allow_html=True,
            )
            st.markdown(f"\U0001F5E1️ **Attacker:** {r['attacker_message']}")
            st.markdown(f"\U0001F6E1️ **Defender:** {r['defender_text']}")
            if r["proposed_mutating"]:
                proposed = ", ".join(f"{p['name']}({p['input']})" for p in r["proposed_mutating"])
                st.caption(f"Proposed actions (not executed): {proposed}")
            st.caption(f"Judge: {r['reason']}")


# ── Dispatch ─────────────────────────────────────────────────────────────

if st.session_state.view == "chat":
    render_chat_view()
else:
    render_arena_view()
