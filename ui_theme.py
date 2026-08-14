"""Sidecar's visual design system: token palette, injected CSS, and small
HTML-rendering helpers (badges, status pills, cards) layered on top of
Streamlit's default components.

Design plan:
  Color   -- ink #14231D, bg #F4F6F5, surface #FFFFFF, surface-2 #ECF1EF,
             border #D7DFDB, primary (brand) #145C4B, gate/warning #A8501C,
             success #1E7F4B, danger #B23B3B, muted #55645D.
  Type    -- IBM Plex Sans (UI/body), IBM Plex Mono (data, code, badges) --
             a deliberate pairing associated with technical/enterprise
             products, not the default Inter/system-font look.
  Layout  -- sidebar as a control panel of bordered card sections; a status
             pill row up top always shows the active domain/mode/context;
             tool calls render as a compact log strip, not chat bubbles;
             metrics render as bordered KPI cards with tabular numerals.
"""

from __future__ import annotations

INK = "#14231D"
BG = "#F4F6F5"
SURFACE = "#FFFFFF"
SURFACE_2 = "#ECF1EF"
BORDER = "#D7DFDB"
PRIMARY = "#145C4B"
GATE = "#A8501C"
SUCCESS = "#1E7F4B"
DANGER = "#B23B3B"
MUTED = "#55645D"

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
  font-family: 'IBM Plex Sans', -apple-system, "Segoe UI", sans-serif !important;
}}
h1, h2, h3, h4 {{
  font-weight: 700 !important;
  letter-spacing: -0.01em;
}}
code, pre, .stCode, [data-testid="stCodeBlock"] * {{
  font-family: 'IBM Plex Mono', ui-monospace, monospace !important;
}}

#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}

.block-container {{ padding-top: 2.2rem; max-width: 1240px; }}

/* Dynamic colorful arena backdrop -- amber glow (attacker corner) vs teal
   glow (defender corner), slowly drifting. */
[data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(circle at 6% 8%, color-mix(in srgb, {GATE} 20%, transparent), transparent 40%),
    radial-gradient(circle at 94% 14%, color-mix(in srgb, {PRIMARY} 22%, transparent), transparent 40%),
    radial-gradient(circle at 30% 95%, color-mix(in srgb, {GATE} 10%, transparent), transparent 45%),
    radial-gradient(circle at 75% 90%, color-mix(in srgb, {PRIMARY} 14%, transparent), transparent 45%),
    {BG};
  background-attachment: fixed;
  background-size: 160% 160%, 160% 160%, 160% 160%, 160% 160%, auto;
  animation: sc-bg-drift 22s ease-in-out infinite alternate;
}}
@media (prefers-reduced-motion: reduce) {{
  [data-testid="stAppViewContainer"] {{ animation: none; }}
}}
@keyframes sc-bg-drift {{
  0%   {{ background-position: 0% 0%, 100% 0%, 20% 100%, 80% 100%, 0 0; }}
  100% {{ background-position: 10% 15%, 90% 10%, 30% 90%, 70% 85%, 0 0; }}
}}

.sc-vs-title-row {{
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 0 0 6px;
}}
.sc-vs-mon {{
  font-size: 42px;
  line-height: 1;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.2));
}}
.sc-vs-title {{
  font-family: 'IBM Plex Mono', monospace;
  font-weight: 700;
  font-size: 44px;
  letter-spacing: 0.01em;
  line-height: 1.05;
  background: linear-gradient(90deg, {GATE} 0%, {INK} 48%, {PRIMARY} 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  text-wrap: balance;
}}
.sc-vs-sub {{
  color: {MUTED};
  font-size: 15.5px;
  max-width: 60ch;
  margin: 0 0 14px;
}}

.sc-appinfo {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 12px;
  color: {MUTED};
  line-height: 1.5;
  text-align: right;
  box-shadow: 0 1px 2px rgba(20,35,29,0.05);
}}
.sc-appinfo .sc-appinfo-title {{
  font-family: 'IBM Plex Mono', monospace;
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: {INK};
  display: block;
  margin-bottom: 3px;
}}
.sc-appinfo .sc-appinfo-principles {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10.5px;
  color: {PRIMARY};
}}

[data-testid="stSidebar"] {{
  background: {SURFACE_2};
  border-right: 1px solid {BORDER};
}}
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
  background: {SURFACE};
  border-radius: 10px;
}}

.stButton button {{
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
}}

[data-testid="stMetric"] {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  padding: 12px 16px 10px;
}}
[data-testid="stMetricValue"] {{
  font-family: 'IBM Plex Mono', monospace !important;
  font-variant-numeric: tabular-nums;
  color: {INK} !important;
}}
[data-testid="stMetricLabel"] {{
  color: {MUTED} !important;
  font-size: 12px !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}}

[data-testid="stChatMessage"] {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(20, 35, 29, 0.04);
  margin-bottom: 6px;
  padding: 4px 4px;
}}

.stAlert {{ border-radius: 10px !important; }}

/* ── Sidecar components ─────────────────────────────────────────── */

.sc-status-row {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}}
.sc-badge {{
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  white-space: nowrap;
}}
.sc-badge-flow {{ background: rgba(20,92,75,0.09); color: {PRIMARY}; border-color: rgba(20,92,75,0.28); }}
.sc-badge-gate {{ background: rgba(168,80,28,0.10); color: {GATE}; border-color: rgba(168,80,28,0.32); }}
.sc-badge-pass {{ background: rgba(30,127,75,0.10); color: {SUCCESS}; border-color: rgba(30,127,75,0.30); }}
.sc-badge-fail {{ background: rgba(178,59,59,0.10); color: {DANGER}; border-color: rgba(178,59,59,0.30); }}
.sc-badge-neutral {{ background: rgba(85,100,93,0.08); color: {MUTED}; border-color: rgba(85,100,93,0.22); }}

.sc-confirm-card {{
  border: 1.5px solid {GATE};
  background: rgba(168,80,28,0.05);
  border-radius: 12px;
  padding: 14px 18px 10px;
  margin: 4px 0 12px;
}}
.sc-confirm-card .sc-confirm-head {{
  font-weight: 700;
  color: {GATE};
  font-size: 14px;
  margin-bottom: 8px;
}}
.sc-action-line {{
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12.5px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(168,80,28,0.14);
  color: {INK};
}}
.sc-action-line:last-child {{ border-bottom: none; }}
.sc-action-line .sc-call {{ flex: 1; word-break: break-word; }}

.sc-tool-log {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12px;
  color: {MUTED};
  background: {SURFACE_2};
  border-left: 3px solid {PRIMARY};
  padding: 7px 12px;
  border-radius: 0 8px 8px 0;
  margin: 4px 0 10px;
  word-break: break-word;
}}

.sc-kpi-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 4px 0 10px; }}
.sc-kpi {{
  flex: 1;
  min-width: 120px;
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  padding: 10px 14px;
}}
.sc-kpi .sc-kpi-label {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: {MUTED};
  margin-bottom: 2px;
}}
.sc-kpi .sc-kpi-value {{
  font-family: 'IBM Plex Mono', monospace;
  font-variant-numeric: tabular-nums;
  font-size: 20px;
  font-weight: 600;
  color: {INK};
}}

.sc-section-label {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: {MUTED};
  margin: 2px 0 6px;
}}

.sc-battle {{
  position: relative;
  display: flex;
  align-items: center;
  gap: 20px;
  margin: 10px 0 20px;
}}

.sc-fire {{
  position: absolute;
  top: 50%;
  font-size: 28px;
  white-space: nowrap;
  pointer-events: none;
  filter: drop-shadow(0 0 12px #ff5a1f) drop-shadow(0 0 22px #ffb020);
  opacity: 0;
  z-index: 3;
}}
@media (prefers-reduced-motion: no-preference) {{
  .sc-fire-attacker {{ left: 46px; animation: sc-fire-right 0.85s ease-out 0.1s; }}
  .sc-fire-defender {{ right: 46px; animation: sc-fire-left 0.85s ease-out 0.1s; }}
}}
@keyframes sc-fire-right {{
  0%   {{ opacity: 0; transform: translateY(-50%) scaleX(0.4); }}
  12%  {{ opacity: 1; transform: translateY(-50%) scaleX(1); }}
  75%  {{ opacity: 1; transform: translateY(-50%) translateX(150px) scaleX(1.6); }}
  100% {{ opacity: 0; transform: translateY(-50%) translateX(210px) scaleX(1.8); }}
}}
@keyframes sc-fire-left {{
  0%   {{ opacity: 0; transform: translateY(-50%) scaleX(0.4); }}
  12%  {{ opacity: 1; transform: translateY(-50%) scaleX(1); }}
  75%  {{ opacity: 1; transform: translateY(-50%) translateX(-150px) scaleX(1.6); }}
  100% {{ opacity: 0; transform: translateY(-50%) translateX(-210px) scaleX(1.8); }}
}}
.sc-battle-mon {{
  font-size: 58px;
  line-height: 1;
  flex-shrink: 0;
  filter: drop-shadow(0 3px 5px rgba(0,0,0,0.22));
}}
@media (prefers-reduced-motion: no-preference) {{
  .sc-mon-attacker {{ animation: sc-shake-left 2.2s ease-in-out infinite; }}
  .sc-mon-defender {{ animation: sc-shake-right 2.2s ease-in-out infinite; }}
  .sc-mon-attacker.sc-mon-win {{ animation: sc-shake-left 2.2s ease-in-out infinite, sc-glow-win 0.9s ease-out; }}
  .sc-mon-attacker.sc-mon-lose {{ animation: sc-shake-left 2.2s ease-in-out infinite, sc-flash-lose 0.5s ease-in-out; }}
  .sc-mon-defender.sc-mon-win {{ animation: sc-shake-right 2.2s ease-in-out infinite, sc-glow-win 0.9s ease-out; }}
  .sc-mon-defender.sc-mon-lose {{ animation: sc-shake-right 2.2s ease-in-out infinite, sc-flash-lose 0.5s ease-in-out; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .sc-mon-attacker {{ transform: scaleX(-1) rotate(-8deg); }}
  .sc-mon-defender {{ transform: rotate(8deg); }}
}}
@keyframes sc-shake-left {{
  0%, 100% {{ transform: scaleX(-1) rotate(-8deg); }}
  50% {{ transform: scaleX(-1) rotate(-1deg); }}
}}
@keyframes sc-shake-right {{
  0%, 100% {{ transform: rotate(8deg); }}
  50% {{ transform: rotate(1deg); }}
}}
@keyframes sc-glow-win {{
  0%   {{ filter: drop-shadow(0 3px 5px rgba(0,0,0,0.22)) brightness(1); }}
  35%  {{ filter: drop-shadow(0 0 22px gold) brightness(1.35) saturate(1.4); }}
  100% {{ filter: drop-shadow(0 3px 5px rgba(0,0,0,0.22)) brightness(1); }}
}}
@keyframes sc-flash-lose {{
  0%   {{ filter: drop-shadow(0 3px 5px rgba(0,0,0,0.22)) brightness(1); }}
  25%  {{ filter: brightness(0.45) saturate(3) hue-rotate(-8deg); }}
  100% {{ filter: drop-shadow(0 3px 5px rgba(0,0,0,0.22)) brightness(1); }}
}}

.sc-battle-mid {{ flex: 1; min-width: 0; }}
.sc-track {{
  position: relative;
  height: 32px;
  border-radius: 999px;
  border: 1px solid {BORDER};
  background: linear-gradient(90deg,
    color-mix(in srgb, {GATE} 32%, {SURFACE_2}) 0%,
    {SURFACE_2} 50%,
    color-mix(in srgb, {PRIMARY} 32%, {SURFACE_2}) 100%);
  overflow: hidden;
}}
.sc-track.sc-pulse-block {{ animation: sc-track-pulse-block 0.9s ease-out; }}
.sc-track.sc-pulse-breach {{ animation: sc-track-pulse-breach 0.9s ease-out; }}
@keyframes sc-track-pulse-block {{
  0%   {{ box-shadow: inset 0 0 0 0 color-mix(in srgb, {PRIMARY} 60%, transparent); }}
  30%  {{ box-shadow: inset 0 0 26px 4px color-mix(in srgb, {PRIMARY} 60%, transparent); }}
  100% {{ box-shadow: inset 0 0 0 0 transparent; }}
}}
@keyframes sc-track-pulse-breach {{
  0%   {{ box-shadow: inset 0 0 0 0 color-mix(in srgb, {GATE} 60%, transparent); }}
  30%  {{ box-shadow: inset 0 0 26px 4px color-mix(in srgb, {GATE} 60%, transparent); }}
  100% {{ box-shadow: inset 0 0 0 0 transparent; }}
}}
.sc-track-ticks {{
  position: absolute;
  inset: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
}}
.sc-track-tick {{
  width: 1px;
  height: 12px;
  background: rgba(0,0,0,0.10);
}}
.sc-track-marker {{
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  font-size: 24px;
  z-index: 2;
}}
@media (prefers-reduced-motion: no-preference) {{
  .sc-track-marker {{ animation: sc-marker-impact 0.55s cubic-bezier(.34,1.56,.64,1); }}
}}
@keyframes sc-marker-impact {{
  0%   {{ transform: translate(-50%, -50%) scale(0.3) rotate(-25deg); opacity: 0; }}
  55%  {{ transform: translate(-50%, -50%) scale(1.7) rotate(8deg); opacity: 1; }}
  100% {{ transform: translate(-50%, -50%) scale(1) rotate(0deg); opacity: 1; }}
}}
.sc-marker-attacker {{ filter: drop-shadow(0 0 10px {GATE}); }}
.sc-marker-defender {{ filter: drop-shadow(0 0 10px {PRIMARY}); }}
.sc-marker-neutral {{ filter: drop-shadow(0 0 4px rgba(0,0,0,0.3)); }}

.sc-track-shock {{
  position: absolute;
  top: 50%;
  width: 30px;
  height: 30px;
  margin: -15px 0 0 -15px;
  border-radius: 50%;
  pointer-events: none;
  z-index: 1;
}}
@media (prefers-reduced-motion: no-preference) {{
  .sc-track-shock {{ animation: sc-shockwave 0.7s ease-out; }}
}}
@keyframes sc-shockwave {{
  0%   {{ transform: scale(0.3); opacity: 0.9; }}
  100% {{ transform: scale(3.4); opacity: 0; }}
}}
.sc-shock-breach {{ background: radial-gradient(circle, {GATE}, transparent 70%); }}
.sc-shock-block {{ background: radial-gradient(circle, {PRIMARY}, transparent 70%); }}

.sc-battle-caption {{
  display: flex;
  justify-content: space-between;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11.5px;
  color: {MUTED};
  margin-top: 8px;
}}
.sc-battle-caption b {{ color: {INK}; }}
.sc-track-step {{ opacity: 0.65; }}
</style>
"""


def inject():
    import streamlit as st
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def badge(label: str, kind: str = "neutral") -> str:
    return f'<span class="sc-badge sc-badge-{kind}">{label}</span>'


def status_row(*badges: str) -> str:
    return f'<div class="sc-status-row">{"".join(badges)}</div>'


BATTLE_STEPS = 10


def battle_bar(blocked: int, breached: int, last_verdict: str | None = None) -> str:
    """Two angry monster avatars facing off across a 10-step tug-of-war track.
    Every round moves the marker exactly one step toward whoever won it. The
    position doesn't smoothly slide across Streamlit reruns (the HTML block is
    replaced wholesale, not diffed in place) -- so the drama comes from
    mount-triggered @keyframes instead of a `left` transition: the marker
    slams in with an impact pop, a shockwave ring bursts from its landing
    spot, the track flashes the winner's color, and whichever monster won
    that round gets a glow while the other flashes and staggers."""
    net = blocked - breached
    position = max(0, min(BATTLE_STEPS, BATTLE_STEPS // 2 + net))
    pct = position / BATTLE_STEPS * 100

    if position <= BATTLE_STEPS // 2 - 2:
        glow = "sc-marker-attacker"
    elif position >= BATTLE_STEPS // 2 + 2:
        glow = "sc-marker-defender"
    else:
        glow = "sc-marker-neutral"

    ticks = "".join('<div class="sc-track-tick"></div>' for _ in range(BATTLE_STEPS + 1))

    attacker_cls, defender_cls, track_pulse, shock_cls, fire_div = "", "", "", "", ""
    if last_verdict == "BLOCKED":
        attacker_cls, defender_cls = "sc-mon-lose", "sc-mon-win"
        track_pulse, shock_cls = "sc-pulse-block", "sc-shock-block"
        fire_div = '<div class="sc-fire sc-fire-defender">\U0001F525\U0001F525\U0001F525</div>'
    elif last_verdict == "BREACHED":
        attacker_cls, defender_cls = "sc-mon-win", "sc-mon-lose"
        track_pulse, shock_cls = "sc-pulse-breach", "sc-shock-breach"
        fire_div = '<div class="sc-fire sc-fire-attacker">\U0001F525\U0001F525\U0001F525</div>'

    shock_div = f'<div class="sc-track-shock {shock_cls}" style="left:{pct:.1f}%"></div>' if shock_cls else ""

    return (
        '<div class="sc-battle">'
        f'<div class="sc-battle-mon sc-mon-attacker {attacker_cls}">\U0001F479</div>'
        f'{fire_div}'
        '<div class="sc-battle-mid">'
        f'<div class="sc-track {track_pulse}">'
        f'<div class="sc-track-ticks">{ticks}</div>'
        f'{shock_div}'
        f'<div class="sc-track-marker {glow}" style="left:{pct:.1f}%">⚡</div>'
        '</div>'
        '<div class="sc-battle-caption">'
        f'<span>\U0001F5E1️ <b>{breached}</b> breaches</span>'
        f'<span class="sc-track-step">step {position}/{BATTLE_STEPS}</span>'
        f'<span><b>{blocked}</b> blocks \U0001F6E1️</span>'
        '</div></div>'
        f'<div class="sc-battle-mon sc-mon-defender {defender_cls}">\U0001F409</div>'
        '</div>'
    )


def app_info_card(description: str, principles: list) -> str:
    """Small top-right card: what this app is + the AI principles it demonstrates."""
    principles_line = " &middot; ".join(principles)
    return (
        '<div class="sc-appinfo">'
        f'<span class="sc-appinfo-title">What is this</span>'
        f'{description}'
        f'<div class="sc-appinfo-principles">{principles_line}</div>'
        '</div>'
    )


def confirm_card(calls: list, is_mutating_fn) -> str:
    lines = []
    for call in calls:
        tag = badge("mutating", "gate") if is_mutating_fn(call["name"]) else badge("read-only", "neutral")
        lines.append(
            f'<div class="sc-action-line">{tag}'
            f'<span class="sc-call"><b>{call["name"]}</b>({call["input"]})</span></div>'
        )
    return (
        '<div class="sc-confirm-card">'
        '<div class="sc-confirm-head">⚠️ Action requires confirmation</div>'
        + "".join(lines) + "</div>"
    )


def tool_log(text: str) -> str:
    escaped = text.replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="sc-tool-log">{escaped}</div>'


def kpi_row(items: list) -> str:
    """items: list of (label, value) tuples."""
    tiles = "".join(
        f'<div class="sc-kpi"><div class="sc-kpi-label">{label}</div>'
        f'<div class="sc-kpi-value">{value}</div></div>'
        for label, value in items
    )
    return f'<div class="sc-kpi-row">{tiles}</div>'
