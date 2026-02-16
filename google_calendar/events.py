from datetime import date, datetime, timedelta, timezone


def _normalize_event_time(value):
    """
    Normalizes a user/model-provided time into a Google Calendar-compatible value.

    Returns: ("dateTime", "<ISO datetime>") or ("date", "YYYY-MM-DD"), otherwise None.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return ("dateTime", value.isoformat())

    if isinstance(value, date):
        return ("date", value.isoformat())

    text = str(value).strip()
    if not text:
        return None

    lowered = text.lower()
    today = datetime.now(tz=timezone.utc).date()
    if "today" in lowered:
        return ("date", today.isoformat())
    if "tomorrow" in lowered:
        return ("date", (today + timedelta(days=1)).isoformat())
    if "yesterday" in lowered:
        return ("date", (today - timedelta(days=1)).isoformat())

    # Date-only input (YYYY-MM-DD)
    try:
        parsed_date = date.fromisoformat(text)
        return ("date", parsed_date.isoformat())
    except Exception:
        pass

    # Datetime input (ISO 8601)
    try:
        parsed_dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
        return ("dateTime", parsed_dt.isoformat())
    except Exception:
        return None


def _compute_end_time(start_kind, start_value, provided_end):
    normalized_end = _normalize_event_time(provided_end)
    if normalized_end:
        end_kind, end_value = normalized_end
        if start_kind == end_kind:
            return end_kind, end_value

    if start_kind == "date":
        start_date = date.fromisoformat(start_value)
        return "date", (start_date + timedelta(days=1)).isoformat()

    start_dt = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
    return "dateTime", (start_dt + timedelta(hours=1)).isoformat()

def create_calendar_event(service, event_details):
    """
    Creates an event in Google Calendar.

    Input: service=<Calendar service>, event_details={"summary": "Meeting", "start_time": "2023-11-14T15:00:00Z"}
    Output: <Event object>
    """
    try:
        summary = event_details.get("summary", "New Meeting")
        description = event_details.get("description", "")
        start_time = event_details.get("start_time")
        location = event_details.get("location", "")

        if not start_time:
            print("Error: start_time is required for calendar events.")
            return None

        normalized_start = _normalize_event_time(start_time)
        if not normalized_start:
            print(f"Error: invalid start_time for calendar event: {start_time!r}")
            return None

        start_kind, normalized_start_value = normalized_start
        end_kind, normalized_end_value = _compute_end_time(
            start_kind,
            normalized_start_value,
            event_details.get("end_time"),
        )

        start_payload = {start_kind: normalized_start_value}
        end_payload = {end_kind: normalized_end_value}
        if start_kind == "dateTime":
            start_payload["timeZone"] = "UTC"
            end_payload["timeZone"] = "UTC"

        event = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': start_payload,
            'end': end_payload,
            'reminders': {
                'useDefault': True,
            },
        }

        attendees = event_details.get("attendees", [])
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        print(f"DEBUG: Creating calendar event with payload: {event}")
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"DEBUG: Successfully created event ID: {created_event.get('id')}")
        return created_event
    except Exception as e:
        print(f"ERROR creating calendar event: {e}")
        import traceback
        traceback.print_exc()
        return None
