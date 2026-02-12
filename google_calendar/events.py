from datetime import datetime, timedelta

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

        # Parse end_time or default to +1 hour
        if "end_time" in event_details:
            end_time = event_details["end_time"]
        else:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = start_dt + timedelta(hours=1)
                end_time = end_dt.isoformat()
            except Exception:
                end_time = start_time # Fallback if parsing fails

        event = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'UTC',
            },
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
