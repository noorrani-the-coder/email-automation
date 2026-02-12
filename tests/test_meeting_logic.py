import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock database dependencies before importing application code
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()
sys.modules["sqlalchemy.ext.declarative"] = MagicMock()

mock_db_models = MagicMock()
mock_db_models.TaskQueue = MagicMock()
sys.modules["db"] = MagicMock()
sys.modules["db.models"] = mock_db_models
sys.modules["db.session"] = MagicMock()

# Add project root to path
sys.path.append("d:\\FINALEMAIL")

from agent.actions import execute_next_action

class TestMeetingLogic(unittest.TestCase):
    @patch("agent.actions.create_calendar_event")
    @patch("agent.actions.store_action_state")  # Mock DB persistence
    @patch("agent.actions.generate_reply_with_status") # Mock reply generation
    @patch("agent.actions.create_gmail_draft") # Mock draft creation
    def test_schedule_meeting_content(self, mock_create_draft, mock_gen_reply, mock_store, mock_create_event):
        # Setup Mocks
        mock_gen_reply.return_value = ({
            "DraftReply": "Sure, let's meet.",
            "Reasoning": "Standard acceptance.",
            "Confidence": 0.9
        }, True)
        
        # Test Data
        observed = {
            "email_id": "test_msg_123",
            "subject": "Let's catch up",
            "from": "partner@example.com",
            "content": "Can we schedule a call next Tuesday?"
        }
        
        analysis = {
            "Intent": "Proposal",
            "RequiresReply": True,
            "RequiresAction": True,
            "NextAction": "schedule_meeting",
            "ActionReason": "User wants to schedule a call.",
            "Confidence": 0.95,
            "MeetingDetails": {
                "Summary": "Catch up call",
                "StartTime": "2023-11-14T15:00:00Z",
                "Platform": "Google Meet",
                "Link": "https://meet.google.com/abc-defg-hij",
                "Agenda": "Discussion about partnership opportunities."
            }
        }
        
        # Services Mocks
        mock_service = MagicMock()
        mock_cal_service = MagicMock()
        
        # Execute
        result, ok, error = execute_next_action(observed, analysis, service=mock_service, cal_service=mock_cal_service)
        
        # Assertions
        self.assertTrue(ok)
        self.assertEqual(result["Action"], "schedule_meeting")
        
        # Verify Calendar Event
        mock_create_event.assert_called_once()
        call_args = mock_create_event.call_args[0] # (cal_service, event_details)
        event_details = call_args[1]
        
        print("\nGenerated Event Details:")
        print(event_details)
        
        self.assertIn("Sender: partner@example.com", event_details["description"])
        self.assertIn("Agenda: Discussion about partnership opportunities.", event_details["description"])
        self.assertIn("Link: https://meet.google.com/abc-defg-hij", event_details["description"])
        self.assertEqual(event_details["summary"], "Catch up call")
        
        # Verify Attendees
        self.assertEqual(event_details["attendees"], ["partner@example.com"])

if __name__ == "__main__":
    unittest.main()
