"""Mock helpdesk/ticketing 'legacy system' the agent retrofits a chat UI onto.

In-memory only — resets every process restart. This stands in for the
existing REST API of a real ticketing tool (Zendesk/Jira/etc).
"""

from __future__ import annotations

import itertools

_id_seq = itertools.count(101)

TICKETS: dict[int, dict] = {}


def _seed():
    seed_rows = [
        ("Checkout button unresponsive on Safari", "Priya", "open", "high", "eng"),
        ("Password reset email not arriving", "Priya", "open", "high", "support"),
        ("Typo on pricing page", "Marcus", "open", "low", "content"),
        ("API returns 500 on bulk import", "Priya", "open", "urgent", "eng"),
        ("Customer wants refund for duplicate charge", "Dana", "open", "high", "billing"),
        ("Dark mode toggle resets on reload", "Marcus", "open", "medium", "eng"),
        ("Onboarding email sent twice", "Dana", "closed", "low", "support"),
        ("Export to CSV missing last column", "Priya", "open", "medium", "eng"),
        ("Login page slow on mobile", "Marcus", "open", "medium", "eng"),
        ("Invoice PDF shows wrong tax rate", "Dana", "open", "urgent", "billing"),
        ("Feature request: dark mode for reports", "Marcus", "open", "low", "product"),
        ("Cannot delete old payment method", "Priya", "open", "high", "eng"),
    ]
    for subject, assignee, status, priority, queue in seed_rows:
        tid = next(_id_seq)
        TICKETS[tid] = {
            "id": tid,
            "subject": subject,
            "assignee": assignee,
            "status": status,
            "priority": priority,
            "queue": queue,
            "resolution": None,
        }


_seed()


def reset():
    TICKETS.clear()
    global _id_seq
    _id_seq = itertools.count(101)
    _seed()


# ── Tool implementations ─────────────────────────────────────────────────

def list_tickets(status: str | None = None, assignee: str | None = None, priority: str | None = None):
    rows = list(TICKETS.values())
    if status:
        rows = [r for r in rows if r["status"] == status]
    if assignee:
        rows = [r for r in rows if r["assignee"].lower() == assignee.lower()]
    if priority:
        rows = [r for r in rows if r["priority"] == priority]
    return [{k: v for k, v in r.items() if k != "resolution"} for r in rows]


def get_ticket(ticket_id: int):
    t = TICKETS.get(int(ticket_id))
    if not t:
        return {"error": f"ticket {ticket_id} not found"}
    return t


def reassign_ticket(ticket_id: int, new_assignee: str):
    t = TICKETS.get(int(ticket_id))
    if not t:
        return {"error": f"ticket {ticket_id} not found"}
    old = t["assignee"]
    t["assignee"] = new_assignee
    return {"ok": True, "ticket_id": int(ticket_id), "reassigned_from": old, "reassigned_to": new_assignee}


def close_ticket(ticket_id: int, resolution: str):
    t = TICKETS.get(int(ticket_id))
    if not t:
        return {"error": f"ticket {ticket_id} not found"}
    t["status"] = "closed"
    t["resolution"] = resolution
    return {"ok": True, "ticket_id": int(ticket_id), "status": "closed"}


def update_priority(ticket_id: int, priority: str):
    t = TICKETS.get(int(ticket_id))
    if not t:
        return {"error": f"ticket {ticket_id} not found"}
    old = t["priority"]
    t["priority"] = priority
    return {"ok": True, "ticket_id": int(ticket_id), "priority_from": old, "priority_to": priority}


TOOL_REGISTRY = {
    "list_tickets": list_tickets,
    "get_ticket": get_ticket,
    "reassign_ticket": reassign_ticket,
    "close_ticket": close_ticket,
    "update_priority": update_priority,
}

READ_ONLY_TOOLS = {"list_tickets", "get_ticket"}
MUTATING_TOOLS = {"reassign_ticket", "close_ticket", "update_priority"}

# ── Routing signals (used by agent.choose_model) ─────────────────────────

ROUTING_WRITE_SIGNALS = (
    "reassign", "close", "resolve", "bulk", "all of", "every ",
    "change priority", "update priority", "assign all", "for all",
)
ROUTING_REASONING_SIGNALS = (" and ", "%", "compare", "which is", "how many more", "total")

# ── Tool specs (sent to Claude) ──────────────────────────────────────────

TOOL_SPECS = [
    {
        "name": "list_tickets",
        "description": (
            "List helpdesk tickets, optionally filtered by status ('open'/'closed'), "
            "assignee name, or priority ('low'/'medium'/'high'/'urgent'). "
            "Call this when the user asks to see, count, or find tickets matching some criteria."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: 'open' or 'closed'."},
                "assignee": {"type": "string", "description": "Filter by assignee's name."},
                "priority": {"type": "string", "description": "Filter by priority: low, medium, high, or urgent."},
            },
        },
    },
    {
        "name": "get_ticket",
        "description": "Get full details of a single ticket by its numeric ID.",
        "input_schema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "integer", "description": "The ticket ID."}},
            "required": ["ticket_id"],
        },
    },
    {
        "name": "reassign_ticket",
        "description": (
            "Reassign a ticket to a different person. This is a WRITE action that changes "
            "the live ticketing system — call it once per ticket that needs reassignment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID to reassign."},
                "new_assignee": {"type": "string", "description": "Name of the new assignee."},
            },
            "required": ["ticket_id", "new_assignee"],
        },
    },
    {
        "name": "close_ticket",
        "description": "Close a ticket with a resolution note. This is a WRITE action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID to close."},
                "resolution": {"type": "string", "description": "One-sentence resolution summary."},
            },
            "required": ["ticket_id", "resolution"],
        },
    },
    {
        "name": "update_priority",
        "description": "Change a ticket's priority level. This is a WRITE action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ticket ID."},
                "priority": {"type": "string", "description": "New priority: low, medium, high, or urgent."},
            },
            "required": ["ticket_id", "priority"],
        },
    },
]

# ── "Bare" variants -- same tools, deliberately under-engineered context.
#    Used by the Context inspector's Engineered/Bare toggle to show that
#    routing/caching/streaming/confirm-gate all still run identically; only
#    correctness changes. Mirrors the vague GET_PRODUCT_SPEC-style specs from
#    the 01_evals exercise on purpose.

BARE_SYSTEM_PROMPT = "You are a helpful assistant."

BARE_TOOL_SPECS = [
    {
        "name": "list_tickets",
        "description": "list tickets",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "status"},
                "assignee": {"type": "string", "description": "assignee"},
                "priority": {"type": "string", "description": "priority"},
            },
        },
    },
    {
        "name": "get_ticket",
        "description": "get ticket",
        "input_schema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "integer", "description": "id"}},
            "required": ["ticket_id"],
        },
    },
    {
        "name": "reassign_ticket",
        "description": "reassign",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "id"},
                "new_assignee": {"type": "string", "description": "assignee"},
            },
            "required": ["ticket_id", "new_assignee"],
        },
    },
    {
        "name": "close_ticket",
        "description": "close",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "id"},
                "resolution": {"type": "string", "description": "resolution"},
            },
            "required": ["ticket_id", "resolution"],
        },
    },
    {
        "name": "update_priority",
        "description": "update priority",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "id"},
                "priority": {"type": "string", "description": "priority"},
            },
            "required": ["ticket_id", "priority"],
        },
    },
]

# A bit of bulk so the system prompt clears the prompt-cache token minimum
# and the "optimized mode" caching win is actually visible in the demo.
COMPANY_POLICY_CONTEXT = """
Internal helpdesk handling policy (v3, effective this quarter):

SECTION 1 -- Priority definitions and SLAs
- 'urgent' = customer-facing outage or data-loss risk. First response SLA: 1 hour,
  24/7. Escalate to the on-call engineer immediately if the assigned owner has not
  acknowledged within 15 minutes. Urgent tickets must never sit unassigned.
- 'high' = broken core functionality with no workaround available to the customer.
  First response SLA: 4 business hours. If a high-priority ticket is still open after
  8 business hours, it is automatically a candidate for priority escalation to urgent
  — flag it in the daily standup rather than escalating unilaterally.
- 'medium' = broken functionality that has a known workaround, or a moderate
  inconvenience. First response SLA: 1 business day. Medium tickets are worked in
  FIFO order within their queue unless a customer has an enterprise SLA contract.
- 'low' = cosmetic issues, typos, minor UX friction, or "nice to have" feature
  requests. First response SLA: 5 business days. Low-priority tickets may be batched
  and handled in a weekly cleanup pass rather than individually.

SECTION 2 -- Queue ownership and routing
- 'eng' queue: engineering-owned. Bugs, performance issues, API errors, anything
  requiring a code change. Engineering tickets should not be closed without a
  resolution note describing root cause and fix -- even a "will not fix" needs a
  one-sentence reason, since it becomes searchable precedent for future duplicates.
- 'support' queue: customer support-owned. Account access issues, "how do I" questions,
  anything resolvable via existing tooling without a code change. Support should
  reroute to 'eng' rather than attempt a workaround for anything that looks like a bug.
- 'billing' queue: finance-owned. Refunds, invoice discrepancies, subscription and
  payment-method issues. Any refund over $500 requires a resolution note that
  explicitly states the refund amount and the name of the approving manager -- this is
  a compliance requirement, not a suggestion, and audits check for it quarterly.
  Refunds under $500 may be resolved and closed by the assigned agent without a named
  approver, but the amount must still be stated in the resolution note.
- 'content' queue: marketing/content-owned. Copy errors, broken links on marketing
  pages, asset requests. Lowest operational risk queue; batching is encouraged.
- 'product' queue: product-owned. Feature requests and roadmap-adjacent asks. These
  are rarely closed quickly -- "under review" is an acceptable long-lived state and
  should not be chased for SLA compliance the way bug reports are.

SECTION 3 -- On-call and assignment rules
- The on-call rotation absorbs urgent tickets that arrive outside business hours
  (before 9am or after 6pm local, and all day on weekends). During business hours,
  urgent tickets stay with their currently assigned owner unless that owner is marked
  out-of-office in the HR system, in which case they route to that person's manager
  by default pending reassignment.
- When a bulk reassignment is requested (e.g. "reassign all of X's open tickets to
  Y"), reassign every matching ticket individually and completely -- do not skip any
  matching ticket, do not silently narrow the request to only urgent/high ones unless
  the user said so, and do not ask for confirmation on each ticket one at a time. A
  human reviews and approves mutating actions through the application's own
  confirmation layer before anything is finalized, so the agent's job is to propose
  the complete, correct set of actions in one pass.
- Never reassign a ticket to someone not already referenced in the conversation or
  ticket data unless the user explicitly names that person as the new assignee.

SECTION 4 -- Communication and data handling
- Never fabricate a ticket ID, assignee name, priority, status, or resolution note.
  Every claim about ticket state must be grounded in a tool call made in this
  conversation -- not memory, not a plausible guess, not an inference from a similar
  ticket seen earlier in the chat.
- Do not include a customer's full payment card number, password, or other sensitive
  credential in a resolution note even if it was present in the original ticket
  subject line -- redact it as [redacted] and note that redaction occurred.
- Keep responses focused on what was asked. A status lookup gets a status answer, not
  a proactive audit of every other ticket in the same queue, unless the user asked for
  that.
- Prefer the minimum number of tool calls that fully and correctly answers the
  request: one well-filtered list_tickets call beats several narrower ones, and a
  single get_ticket call beats listing everything and searching client-side.

SECTION 5 -- Escalation matrix (for reference, not something to recite unprompted)
- Urgent + eng, unowned > 15 min: page on-call engineer.
- Urgent + billing, unowned > 15 min: page billing lead.
- High, no update in 8 business hours: flag in daily standup.
- Any ticket reopened twice: route to a senior agent regardless of original queue.
- Any refund request over $2,000: requires VP finance sign-off in addition to the
  approving manager named in the resolution note.

SECTION 6 -- Tone and resolution note style guide
- Resolution notes are read by three audiences: the customer (indirectly, via a
  support agent's summary), the next engineer who searches for a similar issue, and
  quarterly compliance auditors for billing tickets. Write for all three: state what
  broke, what was done about it, and why, in plain sentences -- not shorthand only the
  person who typed it would understand.
- Avoid blame language in resolution notes ("customer error", "user didn't read the
  docs"). State the root cause neutrally: "Root cause: the discount code field is
  case-sensitive and the UI does not indicate this."
- When multiple tickets describe the same underlying issue, note the duplicate
  relationship in each one's resolution rather than silently closing the newer ones
  with no explanation.

SECTION 7 -- Known duplicate and workaround catalogue (for context, not exhaustive)
- "Checkout button unresponsive on Safari" pattern: historically traced to a
  third-party analytics script blocking the click handler on Safari's Intelligent
  Tracking Prevention. Workaround: hard refresh clears it in ~70% of reports; root fix
  is tracked separately in the eng backlog and should not be re-diagnosed from
  scratch on every new report of the same symptom.
- "Password reset email not arriving" pattern: most often a spam-filter or
  corporate-mail-gateway issue on the recipient's side, not a sending failure on our
  end -- confirm via the mail provider's delivery log tool before assuming an outage.
- "Invoice PDF shows wrong tax rate" pattern: usually a stale tax-jurisdiction cache
  on the account; clearing it and regenerating the invoice resolves the vast majority
  of reports. Escalate to eng only if regeneration does not fix it.
- "Export to CSV missing last column" pattern: known issue on wide reports (12+
  columns) due to a rendering-width limit; there is a documented workaround (export in
  two batches) support agents should offer proactively rather than making the
  customer discover it.

SECTION 8 -- Reporting cadence and metrics this agent should be aware of
- Weekly digest goes out every Monday summarizing: tickets opened, tickets closed,
  average time-to-first-response by priority, and SLA breaches. This agent may be
  asked to help assemble figures for that digest; when it is, prefer counting via
  list_tickets filters over manual enumeration.
- SLA breach is defined strictly by the first-response clock in Section 1 -- a ticket
  that was eventually resolved well within a day can still count as an SLA breach if
  the first response itself was late.
- Queue health is reviewed every other Friday; queues with more than 15 open tickets
  older than their SLA window are flagged for staffing review, not treated as an
  emergency requiring immediate reassignment by this agent.

SECTION 9 -- Team roster and coverage notes (context for assignment questions)
- Priya (eng, support): senior engineer, primary owner of the checkout and payments
  surface area. Handles the highest volume of 'eng'-queue urgent and high tickets.
  Typically the right default owner for anything touching checkout, payment methods,
  or the bulk-import API.
- Marcus (eng, content, product): mid-level engineer plus informal content-queue
  liaison; picks up front-end and cosmetic issues along with a mix of low-priority
  product asks. Not the right owner for billing-adjacent bugs even if they touch the
  UI, since those need billing-queue context.
- Dana (billing, support): billing specialist with support-queue overlap for account
  and onboarding issues. The default approver reference for refund resolution notes
  under $500 when no other manager is named in the ticket.
- Jordan: on-call/floating engineer, the default target for "reassign to on-call" or
  "reassign to whoever's on call" requests when no specific on-call name is given in
  the conversation. Jordan does not have a fixed queue -- their assignments span
  whatever the on-call rotation currently covers.
- New hires shadow an existing owner for their first two weeks and should not be
  assigned tickets directly by this agent even if a queue is understaffed; escalate
  staffing questions to a manager rather than routing around the shadow period.

SECTION 10 -- Historical incident notes (background only, do not recite unprompted)
- Q1 outage: a deploy regression caused checkout button unresponsiveness sitewide for
  40 minutes; post-incident review added the Safari analytics-script workaround to
  the known-issue catalogue in Section 7 so it stops being re-diagnosed from scratch.
- Q2 billing audit finding: several refund resolution notes over $500 were missing
  the approving manager's name; Section 3's compliance requirement was tightened as a
  direct result, and this is now checked in the quarterly audit sample.
- Q3 support backlog spike: password-reset tickets tripled after a mail-provider
  configuration change on our side reduced deliverability; the "confirm via delivery
  log before assuming an outage" guidance in Section 7 exists because the initial
  spike response wasted a day assuming it was purely a customer-side spam-filter
  issue when it was actually partly ours.
- These notes exist so the agent doesn't repeat diagnostic dead ends that are already
  documented -- treat them as background knowledge, not something to summarize back
  to a user who didn't ask about incident history.

SECTION 11 -- Vendor and integration notes (background only)
- The payments processor sends webhook confirmations that occasionally arrive
  out of order relative to the checkout flow; this is the most common root cause
  behind "duplicate charge" reports and should be checked before assuming a genuine
  double-charge bug in the checkout code itself.
- The transactional email vendor's delivery-log tool is the source of truth for
  "email not arriving" reports; do not treat an absence of a delivery-log entry as
  proof of a bug without also checking whether the send was even attempted, since a
  validation failure upstream can suppress the send silently.
- The CSV export pipeline is a separate service from the main app and deploys on its
  own schedule -- a regression there will not correlate with app deploy timestamps,
  which has confused triage in the past when engineers assumed a shared release train.

SECTION 12 -- Change log for this policy document
- v1: initial draft, priority definitions and SLAs only.
- v2: added queue ownership section and on-call assignment rules after a string of
  urgent tickets sat unassigned over a weekend.
- v3 (current): added the known-issue catalogue, team roster, historical incident
  notes, and vendor notes so that context lives in one place instead of being
  re-explained in every onboarding conversation and every triage thread.

SECTION 13 -- Definitions of terms used elsewhere in this document
- "First response" means any substantive update on the ticket, not merely an
  automated acknowledgment -- a canned "we received your ticket" auto-reply does not
  stop the SLA clock in Section 1.
- "Business hours" means 9am-6pm in the ticket requester's local timezone where
  known, and company headquarters timezone otherwise.
- "Duplicate charge" means two or more completed payment captures for what the
  customer intended as a single purchase, as distinct from an authorization hold
  that was never captured, which is not a duplicate charge and should be explained
  to the customer as a temporary hold rather than escalated as a billing bug.

APPENDIX A -- Per-queue SLA reference table (expanded, for lookup only)
- eng / urgent: 1h first response, 4h target resolution, page on-call after 15m
  unacknowledged, weekly review of any breach regardless of eventual resolution time.
- eng / high: 4 business-hour first response, 2 business-day target resolution,
  standup flag after 8 business hours unresponded.
- eng / medium: 1 business-day first response, 5 business-day target resolution,
  FIFO within queue absent an enterprise SLA contract on the account.
- eng / low: 5 business-day first response, batched into the weekly cleanup pass,
  no individual resolution deadline tracked.
- support / urgent: 1h first response (rare in this queue; usually a mis-triaged
  eng issue -- confirm before treating as genuinely support-owned).
- support / high: 4 business-hour first response, 1 business-day target resolution.
- support / medium: 1 business-day first response, 3 business-day target resolution.
- support / low: 5 business-day first response, often resolved same-session via
  existing tooling without a formal resolution window.
- billing / urgent: 1h first response, page billing lead after 15m unacknowledged,
  reserved for payment-processing outages affecting multiple customers at once.
- billing / high: 4 business-hour first response, 1 business-day target resolution,
  applies to most individual refund and invoice-discrepancy reports.
- billing / medium: 1 business-day first response, 2 business-day target resolution.
- billing / low: 5 business-day first response, typically minor invoice formatting
  requests with no financial impact.
- content / any priority: batched weekly regardless of stated priority, except a
  'high' or 'urgent' content ticket tied to an active marketing campaign, which
  follows the eng SLA table instead for the duration of that campaign.
- product / any priority: no first-response SLA tracked; "under review" is a valid
  long-lived state and is not counted against queue-health metrics in Section 8.

APPENDIX B -- Frequently confused ticket patterns (disambiguation only)
- "Can't log in" vs "password reset not arriving": the former is almost always
  support-queue (account lockout, wrong credentials, MFA issue); the latter is the
  specific email-deliverability pattern documented in Section 7 and should be routed
  and diagnosed differently even though both sound like login problems to the
  customer describing them.
- "Refund" vs "chargeback": a refund is initiated by the company through the billing
  queue's normal process; a chargeback is initiated by the customer's bank and
  arrives through a separate, external process this agent has no tooling for --
  do not offer to "process the chargeback," only to check on a refund status.
- "Feature request" vs "bug": if the described behavior matches documented,
  intended functionality, it is a feature request for the product queue even if the
  customer calls it a bug; if it contradicts documented intended functionality, it
  is a bug for the eng queue even if the customer calls it a suggestion.
""".strip()

SYSTEM_PROMPT = (
    "You are Sidecar, a natural-language front end bolted onto the company's "
    "existing helpdesk ticketing system. You do not have a UI of your own — you ARE "
    "the UI, replacing multi-click ticket triage with plain English. Use the tools "
    "below to answer questions and take actions; never claim a ticket exists, was "
    "reassigned, or was closed unless a tool call confirms it.\n\n"
    + COMPANY_POLICY_CONTEXT
)

# ── Tiny eval suite (reused by agent.run_eval_suite) ──────────────────────

EVAL_TASKS = [
    {
        "id": "count_priya_open",
        "category": "lookup",
        "query": "How many open tickets does Priya have?",
        "graders": [
            {"type": "tool_use", "tool_name": "list_tickets",
             "arguments": {"assignee": "Priya", "status": "open"}},
        ],
    },
    {
        "id": "ticket_priority",
        "category": "lookup",
        "query": "What's the priority on ticket 104?",
        "graders": [
            {"type": "tool_use", "tool_name": "get_ticket", "arguments": {"ticket_id": 104}},
            {"type": "response_contains", "text": "urgent"},
        ],
    },
    {
        "id": "reassign_single",
        "category": "write",
        "query": "Reassign ticket 101 to Jordan.",
        "graders": [
            {"type": "tool_use", "tool_name": "reassign_ticket",
             "arguments": {"ticket_id": 101, "new_assignee": "Jordan"}},
        ],
    },
    {
        "id": "close_with_resolution",
        "category": "write",
        "query": "Close ticket 106 -- it was fixed by clearing local storage on load.",
        "graders": [
            {"type": "tool_use", "tool_name": "close_ticket", "arguments": {"ticket_id": 106}},
        ],
    },
    {
        "id": "bulk_reassign",
        "category": "multi-step",
        "query": "Reassign all of Priya's open tickets to Jordan.",
        "graders": [
            {"type": "tool_use", "tool_name": "reassign_ticket", "arguments": {"new_assignee": "Jordan"}},
            {"type": "tool_call_count", "tool_name": "reassign_ticket", "min_calls": 5},
        ],
    },
]
