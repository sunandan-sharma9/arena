"""Mock SF parking/street-cleaning system -- a second 'legacy system' Sidecar
retrofits, to show the same engine (routing/caching/streaming/confirm-gate)
isn't tied to helpdesk tickets.

In-memory only -- resets every process restart.
"""

from __future__ import annotations

ZONES: dict[str, dict] = {
    "mission-valencia": {"name": "Mission -- Valencia St", "rate_per_hour": 3.50,
                          "time_limit_minutes": 120, "enforced": "Mon-Sat 9am-6pm"},
    "hayes-valley": {"name": "Hayes Valley", "rate_per_hour": 4.00,
                      "time_limit_minutes": 120, "enforced": "Mon-Sat 9am-6pm"},
    "marina-chestnut": {"name": "Marina -- Chestnut St", "rate_per_hour": 3.00,
                         "time_limit_minutes": 120, "enforced": "Mon-Sat 9am-6pm"},
    "inner-sunset": {"name": "Inner Sunset -- Irving St", "rate_per_hour": 2.50,
                      "time_limit_minutes": 0, "enforced": "Mon-Sat 9am-6pm"},
    "north-beach": {"name": "North Beach -- Columbus Ave", "rate_per_hour": 3.50,
                     "time_limit_minutes": 120, "enforced": "Mon-Sat 9am-8pm"},
    "noe-mission": {"name": "Noe-Mission -- 24th St", "rate_per_hour": 3.00,
                     "time_limit_minutes": 120, "enforced": "Mon-Sat 9am-6pm"},
}

STREETS: dict[str, dict] = {
    "valencia st, 18th-19th": {"zone_id": "mission-valencia", "cleaning_day": "Tuesday",
                                "cleaning_window": "8:00-10:00 AM"},
    "hayes st, octavia-laguna": {"zone_id": "hayes-valley", "cleaning_day": "Monday",
                                  "cleaning_window": "12:00-2:00 PM"},
    "chestnut st, fillmore-steiner": {"zone_id": "marina-chestnut", "cleaning_day": "Thursday",
                                       "cleaning_window": "6:00-8:00 AM"},
    "irving st, 9th-10th": {"zone_id": "inner-sunset", "cleaning_day": "Wednesday",
                             "cleaning_window": "6:00-8:00 AM"},
    "columbus ave, broadway-vallejo": {"zone_id": "north-beach", "cleaning_day": "Friday",
                                        "cleaning_window": "4:00-6:00 AM"},
    "24th st, mission-bartlett": {"zone_id": "noe-mission", "cleaning_day": "Wednesday",
                                   "cleaning_window": "8:00-10:00 AM"},
}

MY_SESSION: dict = {}
CITATIONS: dict[int, dict] = {}


def _seed():
    MY_SESSION.clear()
    MY_SESSION.update({
        "location": "valencia st, 18th-19th",
        "zone_id": "mission-valencia",
        "paid_minutes": 45,
        "minutes_until_cleaning": 42,
        "reminder_set_minutes_before": None,
    })
    CITATIONS.clear()
    CITATIONS.update({
        501: {"id": 501, "reason": "Street cleaning violation", "amount": 98,
              "date": "2026-08-10", "status": "open", "location": "Hayes St, Octavia-Laguna"},
        502: {"id": 502, "reason": "Expired meter", "amount": 83,
              "date": "2026-08-05", "status": "open", "location": "Chestnut St, Fillmore-Steiner"},
        503: {"id": 503, "reason": "No RPP permit displayed", "amount": 76,
              "date": "2026-07-28", "status": "disputed", "location": "Irving St, 9th-10th"},
    })


_seed()


def reset():
    _seed()


def _find_street(location: str):
    loc = location.lower().strip()
    for key, data in STREETS.items():
        if loc in key or key in loc:
            return key, data
    return None, None


# ── Tool implementations ─────────────────────────────────────────────────

def check_street_cleaning(location: str):
    key, data = _find_street(location)
    if not data:
        return {"error": f"no street-cleaning data on file for '{location}'"}
    return {"street": key, "cleaning_day": data["cleaning_day"], "cleaning_window": data["cleaning_window"]}


def check_meter_rules(location: str):
    key, data = _find_street(location)
    if not data:
        return {"error": f"no meter data on file for '{location}'"}
    zone = ZONES[data["zone_id"]]
    return {
        "street": key,
        "zone": zone["name"],
        "rate_per_hour": zone["rate_per_hour"],
        "time_limit_minutes": zone["time_limit_minutes"] or "no posted limit",
        "enforced": zone["enforced"],
    }


def get_my_session():
    zone = ZONES[MY_SESSION["zone_id"]]
    cleaning_soon = MY_SESSION["minutes_until_cleaning"] is not None
    return {
        "location": MY_SESSION["location"],
        "zone": zone["name"],
        "paid_minutes_remaining": MY_SESSION["paid_minutes"],
        "minutes_until_street_cleaning": MY_SESSION["minutes_until_cleaning"],
        "note": ("Paid meter time does NOT exempt you from a street-cleaning citation."
                  if cleaning_soon else None),
        "reminder_set_minutes_before": MY_SESSION["reminder_set_minutes_before"],
    }


def list_citations(status: str | None = None):
    rows = list(CITATIONS.values())
    if status:
        rows = [r for r in rows if r["status"] == status]
    return rows


def extend_session(minutes: int):
    zone = ZONES[MY_SESSION["zone_id"]]
    limit = zone["time_limit_minutes"]
    new_total = MY_SESSION["paid_minutes"] + int(minutes)
    if limit and new_total > limit:
        return {
            "error": f"cannot extend: this zone has a {limit}-minute posted time limit. "
                     f"Currently {MY_SESSION['paid_minutes']} min paid; +{minutes} would be "
                     f"{new_total} min, over the limit. Move the car instead of extending."
        }
    cost = round(zone["rate_per_hour"] * int(minutes) / 60, 2)
    MY_SESSION["paid_minutes"] = new_total
    return {"ok": True, "added_minutes": int(minutes), "cost_usd": cost, "paid_minutes_remaining": new_total}


def set_move_reminder(minutes_before_cleaning: int):
    if MY_SESSION["minutes_until_cleaning"] is None:
        return {"error": "no upcoming street cleaning known for your current parking location."}
    MY_SESSION["reminder_set_minutes_before"] = int(minutes_before_cleaning)
    return {"ok": True, "reminder_set_minutes_before": int(minutes_before_cleaning)}


def file_dispute(citation_id: int, reason: str):
    c = CITATIONS.get(int(citation_id))
    if not c:
        return {"error": f"citation {citation_id} not found"}
    if c["status"] == "disputed":
        return {"error": f"citation {citation_id} is already under dispute"}
    c["status"] = "disputed"
    c["dispute_reason"] = reason
    return {"ok": True, "citation_id": int(citation_id), "status": "disputed"}


TOOL_REGISTRY = {
    "check_street_cleaning": check_street_cleaning,
    "check_meter_rules": check_meter_rules,
    "get_my_session": get_my_session,
    "list_citations": list_citations,
    "extend_session": extend_session,
    "set_move_reminder": set_move_reminder,
    "file_dispute": file_dispute,
}

READ_ONLY_TOOLS = {"check_street_cleaning", "check_meter_rules", "get_my_session", "list_citations"}
MUTATING_TOOLS = {"extend_session", "set_move_reminder", "file_dispute"}

# ── Routing signals (used by agent.choose_model) ─────────────────────────

ROUTING_WRITE_SIGNALS = (
    "extend", "add time", "add minutes", "dispute", "file a dispute",
    "set a reminder", "reminder", "pay for", "move my",
)
ROUTING_REASONING_SIGNALS = (
    " and ", "compare", "which", "should i", "do i need", "is it okay",
    "am i okay", "is my car", "okay where",
)

# ── Tool specs (sent to Claude) ───────────────────────────────────────────

TOOL_SPECS = [
    {
        "name": "check_street_cleaning",
        "description": "Look up the street-cleaning day and time window for a street/block in San Francisco.",
        "input_schema": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "Street name and cross streets, e.g. 'Valencia St, 18th-19th'."}},
            "required": ["location"],
        },
    },
    {
        "name": "check_meter_rules",
        "description": "Look up the parking meter rate, posted time limit, and enforcement hours for a street/block.",
        "input_schema": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "Street name and cross streets."}},
            "required": ["location"],
        },
    },
    {
        "name": "get_my_session",
        "description": "Get the status of the user's currently parked car: location, paid time remaining, and minutes until street cleaning (if any is scheduled soon).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_citations",
        "description": "List the user's parking citations, optionally filtered by status ('open' or 'disputed').",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "description": "Filter by status: 'open' or 'disputed'."}},
        },
    },
    {
        "name": "extend_session",
        "description": (
            "Add paid time to the user's current parking session. This is a WRITE action that "
            "spends real money -- it will refuse if the extension would exceed the zone's posted "
            "time limit (adding time never excuses you from street cleaning)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"minutes": {"type": "integer", "description": "Minutes to add to the paid session."}},
            "required": ["minutes"],
        },
    },
    {
        "name": "set_move_reminder",
        "description": "Set a reminder to move the car some number of minutes before street cleaning starts. This is a WRITE action.",
        "input_schema": {
            "type": "object",
            "properties": {"minutes_before_cleaning": {"type": "integer", "description": "How many minutes before cleaning starts to remind the user."}},
            "required": ["minutes_before_cleaning"],
        },
    },
    {
        "name": "file_dispute",
        "description": "File a dispute against a parking citation with a stated reason. This is a WRITE action submitted to SFMTA.",
        "input_schema": {
            "type": "object",
            "properties": {
                "citation_id": {"type": "integer", "description": "The citation ID to dispute."},
                "reason": {"type": "string", "description": "One-sentence reason for the dispute."},
            },
            "required": ["citation_id", "reason"],
        },
    },
]

# ── "Bare" variants -- same tools, deliberately under-engineered context.
#    Used by the Context inspector's Engineered/Bare toggle.

BARE_SYSTEM_PROMPT = "You are a helpful assistant."

BARE_TOOL_SPECS = [
    {
        "name": "check_street_cleaning",
        "description": "street cleaning",
        "input_schema": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "location"}},
            "required": ["location"],
        },
    },
    {
        "name": "check_meter_rules",
        "description": "meter rules",
        "input_schema": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "location"}},
            "required": ["location"],
        },
    },
    {
        "name": "get_my_session",
        "description": "session",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_citations",
        "description": "citations",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "description": "status"}},
        },
    },
    {
        "name": "extend_session",
        "description": "extend",
        "input_schema": {
            "type": "object",
            "properties": {"minutes": {"type": "integer", "description": "minutes"}},
            "required": ["minutes"],
        },
    },
    {
        "name": "set_move_reminder",
        "description": "reminder",
        "input_schema": {
            "type": "object",
            "properties": {"minutes_before_cleaning": {"type": "integer", "description": "minutes"}},
            "required": ["minutes_before_cleaning"],
        },
    },
    {
        "name": "file_dispute",
        "description": "dispute",
        "input_schema": {
            "type": "object",
            "properties": {
                "citation_id": {"type": "integer", "description": "id"},
                "reason": {"type": "string", "description": "reason"},
            },
            "required": ["citation_id", "reason"],
        },
    },
]

# ── Policy doc (padding for the prompt-cache demo, same purpose as the
#    helpdesk's COMPANY_POLICY_CONTEXT -- and genuinely useful context) ──

SFMTA_POLICY_CONTEXT = """
SFMTA parking policy reference (informational, for grounding answers -- v2):

SECTION 1 -- Meter enforcement basics
- Standard enforcement hours citywide are Monday-Saturday, 9am-6pm, unless a posted
  sign or the zone record says otherwise. Some nightlife corridors (e.g. North Beach)
  extend enforcement to 8pm. Sunday is generally free citywide as of the last policy
  update, except a small number of pilot commercial corridors -- when in doubt, defer
  to the zone's posted "enforced" hours rather than assuming citywide defaults.
- Posted time limits are hard caps. A driver may pay for additional time via the app,
  but the total paid time can never exceed the zone's posted limit -- there is no way
  to "buy out" a 2-hour zone into an all-day session by paying more. If a requested
  extension would exceed the limit, the correct guidance is to move the car, not to
  attempt a workaround.
- A zone with no posted time limit (time_limit_minutes = 0 / "no posted limit") still
  enforces the meter rate during its enforcement hours -- "no limit" means no maximum
  stay, not free parking.

SECTION 2 -- Street cleaning: the rule most people get wrong
- Street cleaning citations are issued regardless of meter payment status. A fully
  paid, non-expired meter provides zero protection against a street-cleaning ticket
  if the vehicle is present during the posted sweeping window. This is the single
  most common cause of citations relative to how avoidable they are, and it is the
  first thing this agent should flag if a user's parked location has cleaning
  scheduled soon -- do not let a "yes, your meter's paid" answer imply the car is
  safe if cleaning is imminent.
- Cleaning is enforced rain or shine; a rained-out sweeper truck does not cancel
  enforcement of the posted window.
- Setting a move reminder before the posted cleaning window is the single most
  effective preventive action available through this system -- prefer proactively
  offering it whenever a session lookup reveals cleaning is scheduled within the
  next hour, rather than waiting to be asked.

SECTION 3 -- Citation disputes
- Disputes must be filed within 21 days of the citation date to be considered timely;
  this system does not enforce that deadline itself, but a dispute reason should be
  honest about timing if it is close to the boundary.
- Qualifying dispute reasons include: sign obstructed or missing, meter confirmed
  malfunctioning (with a timestamp or receipt), valid RPP or DMV placard not properly
  read by the officer, and incorrect vehicle information on the citation (wrong
  plate, wrong make/model). "I didn't see the sign" without an obstruction claim is
  not, on its own, a strong dispute reason and should be represented honestly rather
  than embellished.
- A citation already marked 'disputed' should not be re-filed -- check status via
  list_citations before filing, and if it's already disputed, report that back
  rather than attempting a duplicate submission.

SECTION 4 -- Residential Parking Permits (RPP)
- RPP holders are exempt from the zone's posted time limit within their permit area,
  but are NOT exempt from street cleaning -- the sweeper rule in Section 2 applies to
  everyone regardless of permit status.
- A vehicle without a valid RPP parked in a permit zone is still bound by the zone's
  general (non-permit) time limit, typically 2 hours during enforcement hours.

SECTION 5 -- Neighborhood notes (context, not something to recite unprompted)
- Valencia St (Mission) and Hayes St (Hayes Valley) are both high-turnover commercial
  corridors with aggressive enforcement due to complaint volume from local merchants.
- Columbus Ave (North Beach) has an early-morning sweeping window (4-6am) timed
  around nightlife-corridor cleanup, unusually early relative to most residential
  streets -- worth calling out explicitly since users are less likely to expect it.
- Irving St (Inner Sunset) has no posted time limit but does have a meter rate --
  a common point of confusion is assuming "no limit" means free.

SECTION 6 -- Fine schedule by violation type (reference table)
- Street cleaning violation: $98 base fine. This is the most commonly issued
  violation type in high-turnover commercial corridors and the one this agent
  should be most proactive about preventing via move reminders.
- Expired meter: $83 base fine. Distinct from street cleaning -- an expired meter
  outside a cleaning window is a straightforward, undisputable violation unless the
  meter itself malfunctioned (see Section 3 dispute reasons).
- No RPP permit displayed in a permit zone: $76 base fine. A valid permit that
  simply wasn't visible to the enforcement officer is a legitimate dispute reason
  if the permit was genuinely present and valid at the time.
- Double parking / blocking a driveway: $110 base fine, and the vehicle may also be
  towed at owner expense -- this system does not currently track tow status, only
  citations, so if a user mentions their car is missing entirely, that is outside
  this system's scope and should be flagged as such rather than guessed at.
- Blocking a street-cleaning sweeper specifically (present and ticketed while the
  sweeper truck itself is on the block, versus simply present during the posted
  window before the truck arrives) carries an additional non-waivable surcharge on
  top of the base street-cleaning fine and is very rarely a successful dispute.
- Fines increase by a standard late-payment penalty schedule if unpaid past 21 days
  from issuance, separate from and in addition to the dispute deadline in Section 3
  -- a citation can be both past the dispute window and unpaid, which compounds.

SECTION 7 -- Payment methods and what this system can and cannot do
- Meter payment and time extensions in this system route through the same backend
  as the official parking app -- extending a session here is equivalent to opening
  the app and adding time, not a separate unofficial mechanism.
- This system cannot pay off, dispute, or otherwise act on a citation that isn't
  already on file in list_citations -- if a user describes a citation this system
  has no record of, say so plainly rather than fabricating a citation ID to act on.
- This system cannot cancel or refund an extend_session action once submitted --
  the money has moved. This is exactly the kind of action that should be confirmed
  with the user before it executes, not undone after the fact.
- This system cannot request a tow release, contest a boot, or interact with the
  city's towed-vehicle line -- those go through a separate physical process this
  agent has no tooling for. If a user's situation sounds like a tow rather than a
  citation (car missing rather than a ticket on the windshield), say so and stop
  rather than attempting an action that doesn't apply.

SECTION 8 -- Seasonal and holiday exemptions
- Street cleaning enforcement is suspended on the ten standard city holidays
  (New Year's Day, MLK Day, Presidents' Day, Memorial Day, Juneteenth, Independence
  Day, Labor Day, Indigenous Peoples' Day, Veterans Day, Thanksgiving, and Christmas
  Day) -- meter enforcement typically continues on all of these except Thanksgiving
  and Christmas, which are full holidays for meter enforcement as well. This system
  does not track the current date, so if a user asks specifically about a holiday,
  answer from this policy text rather than guessing whether today qualifies.
- During the winter storm season, the city has in past years suspended street
  cleaning citywide for multi-day stretches during declared emergencies. This system
  has no live feed of active suspensions and should not claim one is or isn't in
  effect -- direct the user to check the official city advisory for real-time status
  rather than asserting a schedule this system can't actually verify in the moment.

SECTION 9 -- Escalation path for denied disputes
- A first-time dispute that is denied can be escalated to a formal in-person or
  written hearing within 21 days of the denial notice -- this system can file the
  initial dispute (file_dispute) but does not currently have a tool for requesting
  a formal hearing; if a user says their dispute was already denied and they want to
  escalate, that is outside this system's current tooling and should be flagged
  rather than silently treated as a duplicate file_dispute call.
- Citations already in 'disputed' status should never be re-submitted through
  file_dispute -- check status via list_citations first, and if it's already
  disputed, report the existing status back to the user instead.

SECTION 10 -- Tone and communication style
- Street-cleaning conflicts are the one thing this agent should volunteer without
  being asked, per the system message above -- everything else should stay scoped
  to what the user actually asked, the same discipline as any good assistant: don't
  pad a rate lookup with an unsolicited citation-history summary.
- When explaining why an extension was refused (Section 1's time-limit cap), state
  the limit and the requested total plainly, and offer the actual alternative
  (moving the car, or setting a reminder) rather than just reporting the failure.

APPENDIX A -- Per-zone quick reference (expanded, for lookup only)
- Mission -- Valencia St: $3.50/hr, 120-minute posted limit, enforced Mon-Sat
  9am-6pm. Street cleaning Tuesdays 8-10am. High-turnover commercial corridor;
  historically one of the top three zones citywide for street-cleaning citation
  volume, which is why proactive move-reminder guidance matters most here.
- Hayes Valley: $4.00/hr, the highest posted rate among the zones this system
  tracks, reflecting sustained high demand near the performing-arts corridor.
  120-minute limit, enforced Mon-Sat 9am-6pm. Street cleaning Mondays 12-2pm --
  notably a midday window rather than early morning, which catches visitors off
  guard more often than the dawn-window zones do.
- Marina -- Chestnut St: $3.00/hr, 120-minute limit, enforced Mon-Sat 9am-6pm.
  Street cleaning Thursdays 6-8am. Weekend brunch traffic makes Saturday
  enforcement the most commonly misunderstood point for this zone -- Saturday IS
  an enforcement day per the standard citywide schedule in Section 1.
- Inner Sunset -- Irving St: $2.50/hr, no posted time limit, enforced Mon-Sat
  9am-6pm. Street cleaning Wednesdays 6-8am. The lowest rate among tracked zones;
  paired with no time limit, this is effectively the most forgiving zone for a
  long stay, cleaning window aside.
- North Beach -- Columbus Ave: $3.50/hr, 120-minute limit, enforced Mon-Sat
  9am-8pm -- the latest closing enforcement hour among tracked zones, extended
  for the nightlife corridor. Street cleaning Fridays 4-6am, notably early even
  by dawn-window standards, timed to finish before Friday morning foot traffic.
- Noe-Mission -- 24th St: $3.00/hr, 120-minute limit, enforced Mon-Sat 9am-6pm.
  Street cleaning Wednesdays 8-10am, same day as Irving St but two hours later.

APPENDIX B -- Frequently confused scenarios (disambiguation only)
- "My meter's still got time on it, why did I get a ticket?" -- almost always a
  street-cleaning citation, not a meter dispute; check the cleaning schedule for
  that block before assuming the meter payment itself failed.
- "The app says I can't add more time" vs "I got a ticket for expired meter" --
  the former is the posted time-limit cap working as intended (Section 1); the
  latter means a session actually lapsed and is a separate, legitimate citation
  unless there's a specific dispute reason from Section 3.
- "I have a permit, why the ticket?" -- check whether the citation is a street-
  cleaning violation (Section 4: permits do not exempt from cleaning) versus a
  time-limit or no-permit-displayed violation (which a valid, visible permit does
  exempt from).
- A user asking to "renew" a citation dispute that's already disputed is usually
  asking about escalation (Section 9), not a second file_dispute call -- clarify
  which they mean rather than assuming.

SECTION 11 -- Program history and why these rules exist (background only)
- The current 21-day dispute window replaced a shorter 14-day window several years
  ago after public feedback that citations mailed rather than issued in person
  often arrived with less runway to respond; this system enforces the 21-day
  framing in its own guidance (Section 3) rather than the older figure.
- The street-cleaning-overrides-meter-payment rule (Section 2) is not a quirk of
  this system -- it reflects the underlying municipal code, which ties the
  citation to vehicle presence during a posted operational window, independent of
  any parked-time transaction. Explaining this distinction, rather than just
  stating the rule, tends to reduce user frustration when the system has to
  deliver bad news about an already-paid meter.
- The time-limit cap on extend_session (Section 1) exists because posted limits
  are a traffic-management tool, not a revenue mechanism -- commercial corridors
  rely on turnover to keep spaces available, which is also why zones with the
  most complaint volume (Valencia St, Hayes Valley) tend to have the tightest caps
  relative to their high demand rather than looser ones.
- RPP zones (Section 4) exist specifically to protect residents in high-demand
  areas from commercial-corridor turnover pressure -- the exemption from time
  limits, not from cleaning, reflects that residents living on a block still need
  to keep it clear for the sweeper the same as anyone else.

SECTION 12 -- Data this system does not have access to (be explicit about gaps)
- No live GPS or vehicle-location feed -- "my current session" always refers to
  the one location on file via get_my_session, not wherever the user's phone
  currently is. If a user describes parking somewhere new, that is not
  automatically reflected here unless the system explicitly supports updating it.
- No real-time occupancy or space-availability data for any block -- this system
  answers rules and schedule questions, not "is there a spot on Valencia right
  now." Do not speculate about current occupancy.
- No live weather or emergency-suspension feed (see Section 8) -- schedule
  questions get answered from the static policy text, and anything requiring
  today's actual conditions should be flagged as outside this system's knowledge
  rather than guessed at with false confidence.
- No integration with the citywide 311 system, tow lot, or boot-release line --
  those require a human to call a different number, and this agent should say so
  plainly rather than attempting an action it has no tool for.

SECTION 13 -- Change log for this policy document
- v1: initial draft, meter and street-cleaning basics only.
- v2 (current): added the fine schedule, payment-method scope boundaries, seasonal
  exemptions, the dispute-escalation path, and explicit data-gap disclosures, after
  early testing showed the agent would otherwise imply capabilities (like tow
  release or live occupancy) that this system was never built to provide.
""".strip()

SYSTEM_PROMPT = (
    "You are Sidecar, a natural-language front end bolted onto the city's parking "
    "and street-cleaning systems. You do not have a UI of your own -- you ARE the "
    "UI, replacing app-hopping between a meter-payment app and a citation portal "
    "with plain English. Use the tools below to answer questions and take actions; "
    "never claim a rate, schedule, session status, or citation outcome unless a "
    "tool call in this conversation confirms it. When a session lookup reveals "
    "street cleaning is coming up, say so plainly even if that wasn't the exact "
    "question asked -- a paid meter never protects against a cleaning citation.\n\n"
    + SFMTA_POLICY_CONTEXT
)

# ── Tiny eval suite ────────────────────────────────────────────────────────

EVAL_TASKS = [
    {
        "id": "meter_rate_lookup",
        "category": "lookup",
        "query": "What's the hourly rate on Hayes St between Octavia and Laguna?",
        "graders": [
            {"type": "tool_use", "tool_name": "check_meter_rules",
             "arguments": {"location": "hayes st, octavia-laguna"}},
            {"type": "response_contains", "text": "4"},
        ],
    },
    {
        "id": "cleaning_lookup",
        "category": "lookup",
        "query": "When does street cleaning happen on Valencia between 18th and 19th?",
        "graders": [
            {"type": "tool_use", "tool_name": "check_street_cleaning",
             "arguments": {"location": "valencia st, 18th-19th"}},
            {"type": "response_contains", "text": "tuesday"},
        ],
    },
    {
        "id": "extend_session_write",
        "category": "write",
        "query": "Add 30 minutes to my parking.",
        "graders": [
            {"type": "tool_use", "tool_name": "extend_session", "arguments": {"minutes": 30}},
        ],
    },
    {
        "id": "file_dispute_write",
        "category": "write",
        "query": "Dispute citation 502 -- the meter was confirmed malfunctioning and I have a timestamped receipt showing I paid.",
        "graders": [
            {"type": "tool_use", "tool_name": "file_dispute", "arguments": {"citation_id": 502}},
        ],
    },
    {
        "id": "conflict_and_reminder",
        "category": "multi-step",
        "query": "Is my car okay where it's parked? If not, set a reminder for 10 minutes before cleaning.",
        "graders": [
            {"type": "tool_use", "tool_name": "get_my_session"},
            {"type": "tool_use", "tool_name": "set_move_reminder",
             "arguments": {"minutes_before_cleaning": 10}},
            {"type": "response_contains", "text": "clean"},
        ],
    },
]
