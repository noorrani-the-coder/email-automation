from gmail.fetch import fetch_emails


def ingest_emails(creds, max_results=None):
    """Ingest emails from Gmail using provided credentials."""
    messages = fetch_emails(creds, max_results=max_results)
    return messages
