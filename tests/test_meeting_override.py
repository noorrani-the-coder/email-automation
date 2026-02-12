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

class TestMeetingOverride(unittest.TestCase):
    @patch("agent.actions.create_calendar_event")
    @patch("agent.actions.store_action_state")
    @patch("agent.actions.generate_reply_with_status")
    @patch("agent.actions.create_gmail_draft")
    def test_schedule_meeting_override(self, mock_create_draft, mock_gen_reply, mock_store, mock_create_event):
        # Mocks
        mock_gen_reply.return_value = ({}, True)
        
        # Scenario: LLM says "ignore" but provides specific meeting details
        observed = {
            "email_id": "19c4c4a83104f851",
            "from": "sender@example.com",
            "subject": "Update",
            "content": "Meeting call at 6pm"
        }
        
        analysis = {
            "Intent": "Informing about a meeting",
            "RequiresReply": False,
            "RequiresAction": False,
            "NextAction": "ignore", # The issue!
            "ActionReason": "No action required",
            "Confidence": 0.9,
            "MeetingDetails": {
                "Summary": "Meeting call at 6pm",
                "Platform": "Not specified",
                "Link": "Not specified",
                "StartTime": "2024-02-11T18:00:00Z",
                "DurationMinutes": 60,
                "Agenda": "Not specified"
            }
        }
        
        mock_service = MagicMock()
        mock_cal_service = MagicMock()
        
        result, ok, _ = execute_next_action(observed, analysis, service=mock_service, cal_service=mock_cal_service)
        
        # Depending on current logic, this might fail or pass. 
        # We WANT it to be 'schedule_meeting'.
        print(f"Result Action: {result['Action']}")
        
        self.assertEqual(result["Action"], "schedule_meeting")
        mock_create_event.assert_called_once()

if __name__ == "__main__":
    unittest.main()
