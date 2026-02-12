from pathlib import Path
import sys
import json

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.ingestion import ingest_emails
from agent.observation import observe_email
from agent.decision import analyze_email_with_status
from agent.persist import persist_observation
from agent.memory import store_email
from agent.actions import execute_next_action
from agent.behavior import log_behavior_event, sender_domain_from_observed
from agent.retry_queue import enqueue_retry, process_retry_queue
from db.models import EmailMemory
from db.session import get_session, init_db
from gmail.auth import get_credentials
from googleapiclient.discovery import build


import time

# ... (imports remain)

# Global control flags
should_run = False
is_running = False

def run_single_cycle(service, cal_service, session):
    """
    Runs a single cycle of the email agent loop.
    """
    try:
        process_retry_queue(service=service, cal_service=cal_service)
        emails = ingest_emails(max_results=20)
        
        for e in emails:
            if not should_run:
                break

            email_id = e.get("id")
            if email_id and session.query(EmailMemory).filter_by(email_id=email_id).first():
                continue

            print(f"New email detected: {email_id}")
            observed = observe_email(service, e["id"])
            persist_observation(observed)
            try:
                store_email(observed.get("content", ""))
            except Exception:
                pass

            analysis, analysis_ok = analyze_email_with_status(observed)
            action_result = {
                "Action": "escalate_human_review",
                "ActionReason": "Analysis failed and was queued for retry.",
                "Draft": {"DraftReply": "", "Reasoning": "No draft generated.", "Confidence": 0.0},
            }

            if not analysis_ok:
                action_result, _, _ = execute_next_action(observed, analysis, service=service, cal_service=cal_service)
                enqueue_retry(observed, operation="analyze_and_execute", error=str(analysis.get("Reasoning", "")))
            else:
                action_result, action_ok, action_error = execute_next_action(observed, analysis, service=service, cal_service=cal_service)
                if not action_ok:
                    enqueue_retry(observed, operation="analyze_and_execute", error=action_error)

            log_behavior_event(
                email_id=observed.get("email_id") or observed.get("id") or email_id or "",
                intent=str(analysis.get("Intent") or ""),
                sender_domain=sender_domain_from_observed(observed),
                requires_reply=analysis.get("RequiresReply"),
                proposed_action=str(action_result.get("ProposedAction") or action_result.get("Action") or ""),
                agent_action=str(action_result.get("Action") or ""),
                llm_confidence=float(action_result.get("LLMConfidence", analysis.get("Confidence", 0.0)) or 0.0),
                behavior_match_score=float(action_result.get("ImportanceScore", 0.0) or 0.0),
                final_decision_score=float(action_result.get("FinalDecisionScore", 0.0) or 0.0),
                user_final_action="",
            )

            process_retry_queue(service=service, cal_service=cal_service, limit=1)

            output = {
                "EmailId": observed.get("email_id") or observed.get("id") or email_id or "",
                "Analysis": analysis,
                "Action": action_result.get("Action"),
                "ActionReason": action_result.get("ActionReason"),
                "CalendarEvent": action_result.get("CalendarEvent"),
                "Draft": action_result.get("Draft"),
            }
            # print(json.dumps(output, ensure_ascii=True)) # Suppress print in background
            yield output

    except Exception as e:
        print(f"Error in agent loop: {e}")

def run_agent_loop():
    """
    Main loop for the email agent. Monitors inbox, analyzes emails, and takes actions.
    """
    global should_run, is_running
    
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)
    cal_service = build("calendar", "v3", credentials=creds)
    init_db()

    print("Agent background task started.")
    is_running = True
    
    while should_run:
        session = get_session()
        try:
             # Consume generator to execute cycle
            for _ in run_single_cycle(service, cal_service, session):
                pass
        finally:
            session.close()
        
        # Sleep with check
        for _ in range(30):
            if not should_run:
                break
            time.sleep(1)

    is_running = False
    print("Agent background task stopped.")


def start_agent():
    global should_run
    if not should_run:
        should_run = True
        import threading
        t = threading.Thread(target=run_agent_loop)
        t.start()

def stop_agent():
    global should_run
    should_run = False

if __name__ == "__main__":
    start_agent()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            stop_agent()
            break
