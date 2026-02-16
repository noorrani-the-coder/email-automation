import unittest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
import sys

# Add project root to path
sys.path.append("d:\\FINALEMAIL")

from google_calendar.events import create_calendar_event

class TestCalendarPayload(unittest.TestCase):
    def test_create_event_payload(self):
        # Mock Service
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()
        
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert
        mock_insert.execute.return_value = {"id": "new_event_123"}
        
        # Test Data
        event_details = {
            "summary": "Urgent financial matters",
            "description": "Sender: boss@company.com\nAgenda: Pay bills",
            "start_time": "2024-02-11T18:00:00Z",
            "location": "Google Meet",
            "attendees": ["boss@company.com"]
        }
        
        # Execute
        result = create_calendar_event(mock_service, event_details)
        
        # Verify
        self.assertIsNotNone(result)
        mock_events.insert.assert_called_once()
        
        # Check arguments passed to insert
        call_args = mock_events.insert.call_args[1] # kwargs
        self.assertEqual(call_args['calendarId'], 'primary')
        body = call_args['body']
        
        print("\nGenerated Body:")
        print(body)
        
        self.assertEqual(body['summary'], "Urgent financial matters")
        self.assertEqual(body['attendees'], [{'email': 'boss@company.com'}])
        self.assertEqual(body['start']['dateTime'], "2024-02-11T18:00:00+00:00")
        
        # Verify end time is calculated (+1 hour default)
        expected_end = "2024-02-11T19:00:00+00:00" 
        # Note: fromisoformat with Z usually creates aware datetime, isoformat outputs with offset.
        # Implementation uses .replace("Z", "+00:00") then fromisoformat.
        
        self.assertEqual(body['end']['dateTime'], expected_end)

    def test_implied_today_creates_all_day_event(self):
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()

        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert
        mock_insert.execute.return_value = {"id": "all_day_event_1"}

        event_details = {
            "summary": "Project Discussion",
            "description": "Meeting invitation",
            "start_time": "Today (implied)",
            "location": "Not specified",
        }

        result = create_calendar_event(mock_service, event_details)

        self.assertIsNotNone(result)
        mock_events.insert.assert_called_once()
        body = mock_events.insert.call_args[1]["body"]

        today = datetime.utcnow().date().isoformat()
        tomorrow = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
        self.assertEqual(body["start"]["date"], today)
        self.assertEqual(body["end"]["date"], tomorrow)
        self.assertNotIn("dateTime", body["start"])
        self.assertNotIn("timeZone", body["start"])

    def test_invalid_start_time_does_not_call_api(self):
        mock_service = MagicMock()
        mock_events = MagicMock()

        mock_service.events.return_value = mock_events

        event_details = {
            "summary": "Broken Event",
            "description": "Bad start format",
            "start_time": "not a real time",
            "location": "N/A",
        }

        result = create_calendar_event(mock_service, event_details)

        self.assertIsNone(result)
        mock_events.insert.assert_not_called()

if __name__ == "__main__":
    unittest.main()
