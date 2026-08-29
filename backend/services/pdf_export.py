"""
KAVACH — Chat History PDF Export
====================================
Builds a single, properly-formatted PDF from an officer's conversation
history, in either English or Kannada (the Kannada script is rendered
correctly by embedding Noto Sans Kannada — the open-source Google font
at backend/assets/fonts — since PDF's built-in standard fonts, which
jsPDF's client-side export was limited to, don't include Kannada
glyphs at all and would silently render blank boxes).

Used by two things:
  1. The manual "Export PDF" button in CrimeChat (scope='session')
  2. The automatic export that fires right before logout (scope='login')
     — see /api/chat/export in main.py and App.jsx's handleLogout.

FULL-FIDELITY EXPORT (added in response to a reported gap: the PDF used
to contain only the bare reply text, dropping the reasoning trace, the
network graph, and the document review card entirely — none of which
survived a page reload in the app either, until conversation_memory
started persisting each assistant turn's complete response — see
memory_engine.store_turn()'s full_response_json). Every assistant turn
here now renders from that SAME persisted object the chat UI itself
renders from, so the PDF is never missing something the app can show.

Rendering the reasoning trace and the document draft is straightforward
— it's just structured text. The network graph is the one genuinely
harder piece: reportlab has no "embed a live Cytoscape/D3 graph"
shortcut, so _draw_network_snapshot() below draws it manually with
circle/line primitives. This is tractable specifically BECAUSE
brain.py's _network_snapshot() always returns a small, bounded 1-hop
star graph (every edge touches the center person, by construction) —
a simple radial layout is exactly right for that shape. It would be
too simplistic for an arbitrary, non-star graph (e.g. the full
multi-hop investigation graph on the Network page), which is why this
function is deliberately NOT offered as a general-purpose graph
renderer.
"""
import math
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
_KANNADA_FONT_PATH = os.path.join(_ASSETS_DIR, "NotoSansKannada-Regular.ttf")

_NAVY = HexColor("#0B1D3A")
_GOLD = HexColor("#C5A028")
_DARK = HexColor("#1E293B")
_GREY = HexColor("#64748B")
_LIGHT_BG = HexColor("#F8FAFC")
_LIGHT_BORDER = HexColor("#E2E8F0")

_RISK_COLORS = {
    "EXTREME": HexColor("#DC2626"), "HIGH": HexColor("#F59E0B"),
    "MEDIUM": HexColor("#EAB308"), "LOW": HexColor("#64748B"),
}

_RESPONSE_SOURCE_LABELS = {
    "ollama_grounded": "Grounded by local Ollama model",
    "ollama_polish": "Polished by Ollama (facts from template)",
    "general_knowledge": "Curated reference — not case data",
    "document_grounded": "Grounded in attached document — not the case database",
    "template": "Deterministic template (no LLM used)",
}

_kannada_font_registered = False


def _ensure_kannada_font():
    """Registers the Kannada font with reportlab once per process. If the
    font file is somehow missing, falls back to Helvetica — Kannada text
    would then render as blank glyphs, which is a real degradation but a
    safer failure than crashing the whole export."""
    global _kannada_font_registered
    if _kannada_font_registered:
        return True
    if os.path.exists(_KANNADA_FONT_PATH):
        pdfmetrics.registerFont(TTFont("NotoKannada", _KANNADA_FONT_PATH))
        _kannada_font_registered = True
        return True
    return False


def _font_for(text: str, base_font: str) -> str:
    """Picks the Kannada font whenever the text actually contains Kannada
    Unicode codepoints (U+0C80-U+0CFF), else the requested Latin font —
    keeps English-only exports on the crisper standard PDF fonts."""
    if any('\u0c80' <= ch <= '\u0cff' for ch in text) and _ensure_kannada_font():
        return "NotoKannada"
    return base_font


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list:
    """Simple width-aware word wrap using reportlab's own string-width
    metrics — needed because reportlab has no built-in paragraph flow in
    plain canvas mode, and Kannada text wraps at different points than
    Latin text of the same character count."""
    words = text.replace("\r", "").split(" ")
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if c.stringWidth(candidate, font, size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    # also split on hard newlines within the original text
    out = []
    for line in lines:
        out.extend(line.split("\n")) if "\n" in line else out.append(line)
    return out or [""]


def _draw_network_snapshot(c: canvas.Canvas, snapshot: dict, x: float, y_top: float,
                            width: float, height: float) -> float:
    """
    Draws a small hub-and-spoke network diagram directly onto the PDF
    canvas using reportlab's own circle/line primitives — see this
    module's docstring for why a simple radial layout is the right
    (and tractable) choice for this specific data shape, and why it's
    not offered as a general graph renderer. Returns the y-coordinate
    just below the drawn diagram.
    """
    nodes = {n["data"]["id"]: n["data"] for n in snapshot.get("nodes", [])}
    edges = snapshot.get("edges", [])
    center_id = snapshot.get("center_id")
    if center_id not in nodes:
        return y_top

    # Cap to the 5 strongest connections for legibility in a small static
    # diagram — brain.py's _network_snapshot() already sorts edges by
    # Strength DESC, so this keeps the most significant relationships
    # and drops the weakest, rather than truncating arbitrarily. (The
    # live, interactive MiniNetworkGraph in the app has room to show
    # more; this PDF rendering does not, and legibility matters more
    # here than completeness — the app itself is still the full record.)
    ordered_neighbor_ids = []
    for e in edges:
        d = e["data"]
        for nid in (d.get("source"), d.get("target")):
            if nid != center_id and nid in nodes and nid not in ordered_neighbor_ids:
                ordered_neighbor_ids.append(nid)
    shown_ids = ordered_neighbor_ids[:5]
    others = [nodes[nid] for nid in shown_ids]
    shown_id_set = {center_id} | set(shown_ids)

    cx = x + width / 2
    cy = y_top - height / 2
    # Elliptical, not circular, spread: the available box is wide and
    # short (~174mm x 55mm), so a circular layout wasted the width and
    # crowded nodes vertically — this is what caused labels to collide
    # at the top in an earlier version of this diagram. Spreading nodes
    # further horizontally than vertically uses the actual shape of the
    # available space and gives adjacent labels much more room.
    radius_x = min(width / 2 - 22 * mm, 62 * mm)
    radius_y = min(height / 2 - 16 * mm, 20 * mm)
    radius_x = max(radius_x, 30 * mm)
    radius_y = max(radius_y, 14 * mm)

    positions = {center_id: (cx, cy)}
    n = max(len(others), 1)
    for i, node in enumerate(others):
        angle = (2 * math.pi * i / n) - math.pi / 2
        positions[node["id"]] = (cx + radius_x * math.cos(angle), cy + radius_y * math.sin(angle))

    # Edges drawn first so node circles sit on top of the lines. Only
    # edges between two SHOWN nodes are drawn (see the cap above).
    # Relationship-type labels are deliberately omitted here (unlike the
    # live, interactive network view) — in this compact a diagram they
    # added more clutter than they were worth; the officer has the full
    # interactive graph in the app for that detail.
    c.setLineWidth(0.8)
    c.setStrokeColor(HexColor("#94A3B8"))
    for e in edges:
        d = e["data"]
        if d.get("source") not in shown_id_set or d.get("target") not in shown_id_set:
            continue
        p1, p2 = positions.get(d.get("source")), positions.get(d.get("target"))
        if not p1 or not p2:
            continue
        c.line(p1[0], p1[1], p2[0], p2[1])

    node_r = 4.5 * mm
    for nid, (nx, ny) in positions.items():
        node = nodes[nid]
        is_center = bool(node.get("is_center")) or nid == center_id
        color = _RISK_COLORS.get((node.get("risk") or "LOW").upper(), _RISK_COLORS["LOW"])
        r = node_r * 1.3 if is_center else node_r
        c.setFillColor(color)
        c.setStrokeColor(_GOLD if is_center else HexColor("#FFFFFF"))
        c.setLineWidth(1.6 if is_center else 0.8)
        c.circle(nx, ny, r, fill=1, stroke=1)

        # Labels placed ABOVE nodes in the upper half of the diagram and
        # BELOW nodes in the lower half, pointing away from the center —
        # keeps adjacent nodes' labels from colliding. The center node's
        # label always goes above, clear of every neighbor's spoke.
        label = (node.get("label") or "")[:16]
        label_font = _font_for(label, "Helvetica-Bold" if is_center else "Helvetica")
        c.setFillColor(_DARK)
        c.setFont(label_font, 6.2)
        if is_center:
            c.drawCentredString(nx, ny + r + 3 * mm, label)
        elif ny >= cy:
            c.drawCentredString(nx, ny + r + 2.6 * mm, label)
        else:
            c.drawCentredString(nx, ny - r - 3.4 * mm, label)

    # Small legend along the bottom-left of the diagram area.
    legend_y = y_top - height + 3 * mm
    legend_x = x + 2 * mm
    c.setFont("Helvetica", 6)
    for label, color in [("EXTREME", _RISK_COLORS["EXTREME"]), ("HIGH", _RISK_COLORS["HIGH"]),
                          ("MEDIUM", _RISK_COLORS["MEDIUM"]), ("LOW", _RISK_COLORS["LOW"])]:
        c.setFillColor(color)
        c.circle(legend_x + 1 * mm, legend_y, 1.2 * mm, fill=1, stroke=0)
        c.setFillColor(_GREY)
        c.drawString(legend_x + 3.5 * mm, legend_y - 1, label)
        legend_x += 22 * mm

    return y_top - height


def build_chat_history_pdf(officer_name: str, turns: list, scope: str = "login") -> bytes:
    """
    turns: [{"session_id": str, "role": "user"|"assistant", "text": str, "timestamp": str}, ...]
    already ordered chronologically (session, then turn order) by the caller.
    Returns raw PDF bytes.
    """
    from io import BytesIO
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 18 * mm
    content_w = page_w - 2 * margin
    y = page_h - margin

    scope_label = {"login": "Full Session (since this login)", "all": "Complete Chat History",
                   "session": "Single Conversation"}.get(scope, scope)

    def header_footer(page_num: int):
        c.setFillColor(_NAVY)
        c.rect(0, page_h - 26 * mm, page_w, 26 * mm, fill=1, stroke=0)
        c.setFillColor(_GOLD)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(margin, page_h - 12 * mm, "KAVACH — Karnataka State Police")
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#B4B4B4"))
        c.drawString(margin, page_h - 18 * mm, f"Crime Intelligence Chat Export — {scope_label}")
        c.drawString(margin, page_h - 23 * mm,
                     f"Officer: {officer_name}  |  Generated: {datetime.now().strftime('%d %b %Y, %H:%M')} IST")

        c.setFillColor(_NAVY)
        c.rect(0, 0, page_w, 10 * mm, fill=1, stroke=0)
        c.setFillColor(_GOLD)
        c.setFont("Helvetica", 7)
        c.drawString(margin, 4 * mm, "CONFIDENTIAL — FOR OFFICIAL USE ONLY — Karnataka State Police")
        c.drawRightString(page_w - margin, 4 * mm, f"Page {page_num}  |  KAVACH Intelligence Platform")

    page_num = 1
    header_footer(page_num)
    y = page_h - 32 * mm

    def ensure_space(needed: float):
        """Starts a new page if fewer than `needed` points remain above
        the footer — used throughout the reasoning/network/document
        blocks below so none of them ever silently overlaps the footer
        or continues onto content that doesn't exist yet."""
        nonlocal y, page_num
        if y < margin + needed:
            c.showPage(); page_num += 1; header_footer(page_num); y = page_h - 32 * mm

    if not turns:
        c.setFillColor(_GREY)
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, "No conversation turns were recorded for this export.")
        c.save()
        return buf.getvalue()

    current_session = None
    for turn in turns:
        if turn["session_id"] != current_session:
            current_session = turn["session_id"]
            if y < margin + 30 * mm:
                c.showPage(); page_num += 1; header_footer(page_num); y = page_h - 32 * mm
            y -= 4 * mm
            c.setFillColor(HexColor("#F1F5F9"))
            c.rect(margin, y - 5 * mm, content_w, 7 * mm, fill=1, stroke=0)
            c.setFillColor(_NAVY)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(margin + 2 * mm, y - 3 * mm, f"SESSION: {current_session}")
            y -= 10 * mm

        role_label = "OFFICER" if turn["role"] == "user" else "KAVACH-AI"
        role_color = _NAVY if turn["role"] == "user" else _GOLD
        ts = ""
        try:
            ts = datetime.fromisoformat(turn["timestamp"]).strftime("%d %b, %H:%M")
        except (ValueError, TypeError):
            ts = turn.get("timestamp") or ""

        label_font = "Helvetica-Bold"
        body_font_base = "Helvetica"
        body_font = _font_for(turn["text"] or "", body_font_base)
        body_size = 9

        if y < margin + 20 * mm:
            c.showPage(); page_num += 1; header_footer(page_num); y = page_h - 32 * mm

        c.setFont(label_font, 8)
        c.setFillColor(role_color)
        c.drawString(margin, y, f"{role_label}")
        c.setFillColor(_GREY)
        c.setFont("Helvetica", 7)
        c.drawString(margin + 45 * mm, y, ts)
        y -= 4.5 * mm

        c.setFillColor(_DARK)
        c.setFont(body_font, body_size)
        for line in _wrap_text(c, turn["text"] or "", body_font, body_size, content_w - 4 * mm):
            if y < margin + 12 * mm:
                c.showPage(); page_num += 1; header_footer(page_num); y = page_h - 32 * mm
                c.setFont(body_font, body_size)
                c.setFillColor(_DARK)
            c.drawString(margin + 4 * mm, y, line)
            y -= 4.3 * mm
        y -= 3 * mm

        # ── Full-fidelity assistant details ─────────────────────────────
        # Only present for turns stored after conversation_memory started
        # persisting the complete response (see memory_engine.store_turn()'s
        # full_response_json docstring) — older turns just show the bare
        # reply text above, which is still strictly more than this export
        # used to show for ANY turn. This is what makes the "reasoning
        # trace and network graph should be in the PDF too" request real:
        # every field rendered below comes from the SAME object the chat
        # UI's Reasoning panel and network tab render from, never a
        # separate re-derivation.
        full = turn.get("full_response")
        if turn["role"] == "assistant" and full:
            intent = full.get("intent")
            source_label = _RESPONSE_SOURCE_LABELS.get(full.get("response_source"), full.get("response_source"))
            trace_lines = full.get("pipeline_trace") or []
            sql = full.get("sql_generated")
            result_count = full.get("result_count", 0)
            notable = full.get("notable_insight")
            network_snapshot = full.get("network_snapshot")
            document_draft = full.get("document_draft")
            document_attached = full.get("document_attached")

            if intent or trace_lines or sql or network_snapshot or document_draft or document_attached:
                ensure_space(14 * mm)
                y -= 1.5 * mm
                c.setFillColor(_GOLD)
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(margin + 4 * mm, y, "REASONING")
                y -= 4 * mm

                meta_bits = []
                if intent:
                    meta_bits.append(f"Intent: {intent} ({full.get('intent_confidence', 0) or 0:.0%} confidence)")
                if source_label:
                    meta_bits.append(f"Source: {source_label}")
                meta_bits.append(f"Results: {result_count}")
                ensure_space(6 * mm)
                c.setFont("Helvetica", 7.5)
                c.setFillColor(_DARK)
                c.drawString(margin + 6 * mm, y, "  |  ".join(meta_bits))
                y -= 4.2 * mm

                if sql:
                    ensure_space(8 * mm)
                    c.setFont("Helvetica-Bold", 6.5)
                    c.setFillColor(_GREY)
                    c.drawString(margin + 6 * mm, y, "SQL:")
                    y -= 3.3 * mm
                    for line in _wrap_text(c, sql, "Courier", 6.5, content_w - 12 * mm):
                        ensure_space(5 * mm)
                        c.setFont("Courier", 6.5)
                        c.setFillColor(_DARK)
                        c.drawString(margin + 8 * mm, y, line)
                        y -= 3.2 * mm
                    y -= 1 * mm

                if trace_lines:
                    ensure_space(8 * mm)
                    c.setFont("Helvetica-Bold", 6.5)
                    c.setFillColor(_GREY)
                    c.drawString(margin + 6 * mm, y, "PIPELINE TRACE:")
                    y -= 3.3 * mm
                    for tline in trace_lines:
                        for wline in _wrap_text(c, f"- {tline}", "Helvetica", 6.8, content_w - 12 * mm):
                            ensure_space(5 * mm)
                            c.setFont("Helvetica", 6.8)
                            c.setFillColor(_DARK)
                            c.drawString(margin + 8 * mm, y, wline)
                            y -= 3.2 * mm
                    y -= 1 * mm

                if notable:
                    ensure_space(6 * mm)
                    for wline in _wrap_text(c, f"Worth noting: {notable}", "Helvetica-Oblique", 6.8, content_w - 12 * mm):
                        ensure_space(5 * mm)
                        c.setFont("Helvetica-Oblique", 6.8)
                        c.setFillColor(HexColor("#6B21A8"))
                        c.drawString(margin + 6 * mm, y, wline)
                        y -= 3.2 * mm
                    y -= 1 * mm

                if document_attached:
                    ensure_space(6 * mm)
                    c.setFont("Helvetica", 6.8)
                    c.setFillColor(_DARK)
                    doc_line = (f"Document: {document_attached.get('filename')} "
                                f"({document_attached.get('char_count', 0)} chars extracted)")
                    c.drawString(margin + 6 * mm, y, doc_line)
                    y -= 4 * mm

                if document_draft:
                    ensure_space(10 * mm)
                    c.setFont("Helvetica-Bold", 6.5)
                    c.setFillColor(_GREY)
                    c.drawString(margin + 6 * mm, y, "EXTRACTED DRAFT:")
                    y -= 3.3 * mm
                    districts = ", ".join(document_draft.get("districts_detected") or []) or "—"
                    names = ", ".join(document_draft.get("person_name_candidates") or []) or "—"
                    draft_bits = [
                        f"Crime No: {document_draft.get('crime_no_guess') or '—'}",
                        f"Date: {document_draft.get('date_guess') or '—'}",
                        f"District(s): {districts}",
                        f"Names detected: {names}",
                    ]
                    for line in draft_bits:
                        ensure_space(5 * mm)
                        c.setFont("Helvetica", 6.8)
                        c.setFillColor(_DARK)
                        c.drawString(margin + 8 * mm, y, line)
                        y -= 3.2 * mm
                    y -= 1 * mm

                if network_snapshot and network_snapshot.get("nodes"):
                    diagram_h = 68 * mm
                    ensure_space(diagram_h + 10 * mm)
                    c.setFont("Helvetica-Bold", 6.5)
                    c.setFillColor(_GREY)
                    c.drawString(margin + 6 * mm, y, "NETWORK SNAPSHOT:")
                    y -= 3.5 * mm
                    box_x, box_w = margin + 6 * mm, content_w - 12 * mm
                    c.setStrokeColor(_LIGHT_BORDER)
                    c.setLineWidth(0.5)
                    c.rect(box_x, y - diagram_h, box_w, diagram_h, fill=0, stroke=1)
                    y = _draw_network_snapshot(c, network_snapshot, box_x, y, box_w, diagram_h)
                    y -= 4 * mm

                y -= 2 * mm

    c.save()
    return buf.getvalue()
