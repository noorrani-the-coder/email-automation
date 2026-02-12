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
        self.assertEqual(body['start']['dateTime'], "2024-02-11T18:00:00Z")
        
        # Verify end time is calculated (+1 hour default)
        expected_end = "2024-02-11T19:00:00+00:00" 
        # Note: fromisoformat with Z usually creates aware datetime, isoformat outputs with offset.
        # Implementation uses .replace("Z", "+00:00") then fromisoformat.
        
        self.assertEqual(body['end']['dateTime'], expected_end)

if __name__ == "__main__":
    unittest.main()
