import base64
from email.message import EmailMessage

def create_gmail_draft(service, msg_metadata, draft_text):
    """
    Creates a draft in Gmail as a reply to an existing message.

    Input: service=<Gmail service>, msg_metadata={"from": "...", "thread_id": "..."}, draft_text="Hello..."
    Output: <Draft object>
    """
    try:
        message = EmailMessage()
        message.set_content(draft_text)

        # Basic metadata
        recipient = msg_metadata.get("from")
        subject = msg_metadata.get("subject")
        if subject and not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        
        message["To"] = recipient
        message["Subject"] = subject

        # Threading metadata
        thread_id = msg_metadata.get("thread_id")
        message_id = msg_metadata.get("message_id") # To be added in observation.py
        
        if message_id:
            message["In-Reply-To"] = message_id
            message["References"] = message_id

        # Encode the message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {
            "message": {
                "raw": encoded_message,
                "threadId": thread_id
            }
        }

        draft = service.users().drafts().create(userId="me", body=create_message).execute()
        return draft
    except Exception as e:
        print(f"Error creating draft: {e}")
        return None
