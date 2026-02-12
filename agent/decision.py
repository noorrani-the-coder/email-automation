import json
from typing import Any

from ai.llm import call_llm


EXEC_EMAIL_ANALYSIS_PROMPT = """
You are an intelligent executive email assistant.

Analyze the email carefully and answer the following:

1. Intent: What is the main purpose of the email?
2. RequiresReply: Does the sender expect a response from the recipient? (true/false)
3. RequiresAction: Does the email require the recipient to take any action? (true/false)
4. NextAction: choose exactly one of:
   - ignore
   - draft_reply
   - create_task
   - flag_high_urgency
   - escalate_human_review
   - schedule_meeting
5. ActionReason: Brief reason for NextAction.
6. Urgency: low / medium / high
7. Reasoning: Brief explanation.
8. Confidence: 0.0 to 1.0
9. MeetingDetails: If NextAction is schedule_meeting or a meeting is otherwise mentioned, provide:
   - Summary (string)
   - Platform (e.g., "Google Meet", "Zoom")
   - Link (string)
   - StartTime (ISO 8601 string)
   - DurationMinutes (integer)
   - Agenda (string): A short summary of what the meeting is about.

Important:
- **Keyword Trigger**: If the body or subject contains "meeting", "schedule", or "call", and a date/time is proposed or implied, prioritize `schedule_meeting`.
- Do not use keyword rules blindly; ensure context implies a meeting.
- Infer expectations socially and professionally.
- Newsletters, automated notifications, and marketing emails usually do not require replies.
- Direct questions, requests, proposals, confirmations usually require replies.

Return output strictly in JSON.
Use exactly these keys: Intent, RequiresReply, RequiresAction, NextAction, ActionReason, Urgency, Reasoning, Confidence, MeetingDetails.
Do not include markdown or any extra keys.
"""

EXEC_EMAIL_REPLY_PROMPT = """
You are an executive email assistant that writes concise, professional drafts.

You will receive:
- The original email content.
- A structured analysis of that email.

Write a suitable reply draft that matches the analysis.
- If analysis indicates `schedule_meeting` as the NextAction, draft a polite acceptance of the invitation, acknowledging the date and time from MeetingDetails.
- If analysis indicates no reply is required, set DraftReply to an empty string and explain briefly.
Do not invent facts or commitments not present in the email.

Return output strictly in JSON.
Use exactly these keys: DraftReply, Reasoning, Confidence.
Confidence must be a number from 0.0 to 1.0.
Do not include markdown or any extra keys.
"""


def _clean_json(raw: str) -> str:
    """
    Cleans raw JSON string by extracting the content between the first { and last }.

    Input: "```json\n{\"key\": \"value\"}\n```"
    Output: "{\"key\": \"value\"}"
    """
    raw = raw.strip()
    # Find first { and last } regardless of markdown backticks or preamble
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        return raw[start : end + 1]
    return raw


def _email_content(email: Any) -> str:
    """
    Extracts the content from an email object or dictionary.

    Input: {"content": "Hello"}
    Output: "Hello"
    """
    if isinstance(email, dict):
        return str(email.get("content", ""))
    return ""


def _fallback_analysis(reasoning: str = "Model response could not be parsed reliably.") -> dict[str, Any]:
    """
    Returns a fallback analysis dictionary when parsing fails.

    Input: reasoning="Error parsing"
    Output: {"Intent": "Unknown", ...}
    """
    return {
        "Intent": "Unknown",
        "RequiresReply": None,
        "RequiresAction": None,
        "NextAction": "escalate_human_review",
        "ActionReason": "Analysis is uncertain; routing to human review.",
        "Urgency": "low",
        "Reasoning": reasoning,
        "Confidence": 0.2,
    }


def _coerce_bool_or_none(value: Any) -> Any:
    """
    Coerces a value to a boolean or None.

    Input: "true"
    Output: True
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return None


def _normalize_next_action(value: Any, requires_reply: Any) -> str:
    """
    Normalizes the next action string to a standard set of allowed actions.

    Input: value="reply", requires_reply=True
    Output: "draft_reply"
    """
    allowed = {
        "ignore",
        "draft_reply",
        "create_task",
        "flag_high_urgency",
        "escalate_human_review",
        "schedule_meeting",
    }
    if isinstance(value, str):
        normalized = value.strip().lower()
        aliases = {
            "draft": "draft_reply",
            "reply": "draft_reply",
            "create task": "create_task",
            "task": "create_task",
            "flag high urgency": "flag_high_urgency",
            "high_urgency": "flag_high_urgency",
            "escalate": "escalate_human_review",
            "human_review": "escalate_human_review",
            "schedule meeting": "schedule_meeting",
            "schedule": "schedule_meeting",
            "meeting": "schedule_meeting",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized in allowed:
            return normalized
    if requires_reply is True:
        return "draft_reply"
    if requires_reply is False:
        return "ignore"
    return "escalate_human_review"


def _coerce_analysis_payload(raw: str) -> tuple[dict[str, Any], bool]:
    """
    Coerces the raw LLM response into a structured analysis payload.

    Input: raw='{"Intent": "Propoal"}'
    Output: ({"Intent": "Proposal", ...}, True)
    """
    parse_ok = True
    try:
        clean = _clean_json(raw)
        parsed = json.loads(clean)
        if not isinstance(parsed, dict):
            raise ValueError("response is not an object")
    except Exception as e:
        print(f"DEBUG: JSON parse failure for analysis: {e}")
        print(f"DEBUG: Raw response prefix: {raw[:200]}...")
        parsed = _fallback_analysis()
        parse_ok = False

    payload = {
        "Intent": str(parsed.get("Intent", "Unknown")).strip() or "Unknown",
        "RequiresReply": _coerce_bool_or_none(parsed.get("RequiresReply")),
        "RequiresAction": _coerce_bool_or_none(parsed.get("RequiresAction")),
        "NextAction": "",
        "ActionReason": str(parsed.get("ActionReason", "")).strip(),
        "Urgency": str(parsed.get("Urgency", "low")).strip().lower(),
        "Reasoning": str(parsed.get("Reasoning", "")).strip() or "No reasoning provided.",
        "Confidence": parsed.get("Confidence", 0.2),
        "MeetingDetails": parsed.get("MeetingDetails"),
    }
    payload["NextAction"] = _normalize_next_action(parsed.get("NextAction"), payload["RequiresReply"])
    if not payload["ActionReason"]:
        payload["ActionReason"] = payload["Reasoning"]

    if payload["Urgency"] not in {"low", "medium", "high"}:
        payload["Urgency"] = "low"

    try:
        payload["Confidence"] = float(payload["Confidence"])
    except Exception:
        payload["Confidence"] = 0.2
    payload["Confidence"] = max(0.0, min(1.0, payload["Confidence"]))

    return payload, parse_ok


def _fallback_reply(reasoning: str = "Reply draft could not be generated reliably.") -> dict[str, Any]:
    """
    Returns a fallback reply dictionary when generation fails.

    Input: reasoning="Error generating"
    Output: {"DraftReply": "", ...}
    """
    return {
        "DraftReply": "",
        "Reasoning": reasoning,
        "Confidence": 0.2,
    }


def _coerce_reply_payload(raw: str) -> dict[str, Any]:
    """
    Coerces the raw LLM response into a structured reply payload.

    Input: raw='{"DraftReply": "Hi"}'
    Output: {"DraftReply": "Hi", ...}
    """
    try:
        clean = _clean_json(raw)
        parsed = json.loads(clean)
        if not isinstance(parsed, dict):
            raise ValueError("response is not an object")
    except Exception as e:
        print(f"DEBUG: JSON parse failure for reply: {e}")
        parsed = _fallback_reply()

    payload = {
        "DraftReply": str(parsed.get("DraftReply", "")).strip(),
        "Reasoning": str(parsed.get("Reasoning", "")).strip() or "No reasoning provided.",
        "Confidence": parsed.get("Confidence", 0.2),
    }

    try:
        payload["Confidence"] = float(payload["Confidence"])
    except Exception:
        payload["Confidence"] = 0.2
    payload["Confidence"] = max(0.0, min(1.0, payload["Confidence"]))

    return payload


def analyze_email(email: Any) -> dict[str, Any]:
    """
    Analyzes an email to determine intent and next action.

    Input: email={"content": "..."}
    Output: {"Intent": "Proposal", ...}
    """
    payload, _ = analyze_email_with_status(email)
    return payload


def analyze_email_with_status(email: Any) -> tuple[dict[str, Any], bool]:
    """
    Analyzes an email and returns the result along with a success status.

    Input: email={"content": "..."}
    Output: ({"Intent": "Proposal", ...}, True)
    """
    try:
        raw = call_llm(
            EXEC_EMAIL_ANALYSIS_PROMPT,
            _email_content(email),
            temperature=0.1,
        )
    except Exception as exc:
        return _fallback_analysis(reasoning=f"analysis unavailable: {exc.__class__.__name__}"), False
    return _coerce_analysis_payload(raw)


def generate_reply(email: Any, analysis: Any) -> dict[str, Any]:
    """
    Generates a reply draft based on the email and analysis.

    Input: email={...}, analysis={...}
    Output: {"DraftReply": "Hi...", ...}
    """
    payload, _ = generate_reply_with_status(email, analysis)
    return payload


def generate_reply_with_status(email: Any, analysis: Any) -> tuple[dict[str, Any], bool]:
    """
    Generates a reply draft and returns the result along with a success status.

    Input: email={...}, analysis={...}
    Output: ({"DraftReply": "..."}, True)
    """
    user_payload = {
        "email_content": _email_content(email),
        "analysis": analysis if isinstance(analysis, dict) else _fallback_analysis(),
    }

    try:
        raw = call_llm(
            EXEC_EMAIL_REPLY_PROMPT,
            json.dumps(user_payload, ensure_ascii=True),
            temperature=0.2,
        )
    except Exception as exc:
        return _fallback_reply(reasoning=f"draft unavailable: {exc.__class__.__name__}"), False
    return _coerce_reply_payload(raw), True


def summarize(email: Any) -> str:
    """
    Returns a JSON string summary of the email analysis.

    Input: email={...}
    Output: '{"Intent": "..."}'
    """
    return json.dumps(analyze_email(email), ensure_ascii=True)


def draft_reply(email: Any) -> str:
    """
    Analyzes the email and returns a JSON string containing the draft reply.

    Input: email={...}
    Output: '{"DraftReply": "..."}'
    """
    analysis = analyze_email(email)
    return json.dumps(generate_reply(email, analysis), ensure_ascii=True)
