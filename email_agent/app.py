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
from db.models import EmailMemory, UserCredentials, User
from db.session import get_session, init_db
from gmail.auth import get_credentials_for_user
from googleapiclient.discovery import build


import time

# ... (imports remain)

# Global control flags
should_run = False
is_running = False

def run_single_cycle(service, cal_service, session, user_id, creds):
    """
    Runs a single cycle of the email agent loop for a specific user.
    """
    try:
        process_retry_queue(service=service, cal_service=cal_service, user_id=user_id)
        emails = ingest_emails(creds, max_results=20)
        
        for e in emails:
            if not should_run:
                break

            email_id = e.get("id")
            if email_id and session.query(EmailMemory).filter_by(email_id=email_id, user_id=user_id).first():
                continue

            print(f"New email detected for user {user_id}: {email_id}")
            observed = observe_email(service, e["id"])
            print(f"Email body: {observed.get('content', 'No content')}")
            persist_observation(observed, user_id=user_id)
            try:
                store_email(observed.get("content", ""))
            except Exception:
                pass

            analysis, analysis_ok = analyze_email_with_status(observed)
            print(f"Analysis OK: {analysis_ok}")
            print(f"Analysis result: {analysis}")
            
            if not analysis_ok:
                # Analysis failed, queue for retry
                print(f"Analysis failed, queuing for retry. Reason: {analysis.get('Reasoning', '')}")
                enqueue_retry(observed, operation="analyze_and_execute", error=str(analysis.get("Reasoning", "")), user_id=user_id)
                action_result = {
                    "Action": "queued_for_retry",
                    "ActionReason": "Analysis failed and was queued for retry.",
                    "Draft": {"DraftReply": "", "Reasoning": "No draft generated.", "Confidence": 0.0},
                }
            else:
                # Analysis succeeded, try to execute the action
                action_result, action_ok, action_error = execute_next_action(observed, analysis, service=service, cal_service=cal_service, user_id=user_id)
                print(f"Action execution OK: {action_ok}")
                print(f"Action result: {action_result}")
                if not action_ok:
                    print(f"Action failed, queuing for retry. Error: {action_error}")
                    enqueue_retry(observed, operation="analyze_and_execute", error=action_error, user_id=user_id)
                else:
                    print(f"Action executed successfully: {action_result.get('Action')}")

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
                user_id=user_id,
            )

            process_retry_queue(service=service, cal_service=cal_service, limit=1, user_id=user_id)

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
        print(f"Error in agent loop for user {user_id}: {e}")

def run_agent_loop():
    """
    Main loop for the email agent. Monitors inboxes for all users with stored credentials,
    analyzes emails, and takes actions.
    """
    global should_run, is_running
    
    init_db()
    print("Agent background task started.")
    is_running = True
    
    while should_run:
        try:
            # Get all users with stored credentials
            session = get_session()
            try:
                users_with_creds = (
                    session.query(User.id, User.email)
                    .join(UserCredentials, User.id == UserCredentials.user_id)
                    .all()
                )
            finally:
                session.close()
            
            # Process each user's emails
            for user_id, user_email in users_with_creds:
                if not should_run:
                    break
                
                try:
                    # Get credentials for this user from database
                    creds = get_credentials_for_user(user_id)
                    if not creds:
                        print(f"Could not load credentials for user {user_id} ({user_email}), skipping...")
                        continue
                    
                    # Build services
                    service = build("gmail", "v1", credentials=creds)
                    cal_service = build("calendar", "v3", credentials=creds)
                    
                    # Process this user's emails
                    session = get_session()
                    try:
                        for _ in run_single_cycle(service, cal_service, session, user_id, creds):
                            pass
                    finally:
                        session.close()
                        
                except Exception as e:
                    print(f"Error processing user {user_id}: {e}")
                    continue
        
        except Exception as e:
            print(f"Error in agent main loop: {e}")
        
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
