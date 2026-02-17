from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from pathlib import Path
import os
import sys
import httplib2
import certifi
import json
from typing import Optional

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar"
]


def _configure_ssl_ca(root_dir: Path) -> None:
    """
    Ensure Google API HTTP client uses a valid CA bundle.
    """
    current = getattr(httplib2, "CA_CERTS", "") or ""
    if current and Path(current).exists():
        return

    candidates = [
        Path(certifi.where()),
        Path(sys.base_prefix) / "Lib" / "site-packages" / "certifi" / "cacert.pem",
    ]
    for path in candidates:
        if path.exists():
            ca_path = str(path)
            httplib2.CA_CERTS = ca_path
            os.environ["SSL_CERT_FILE"] = ca_path
            os.environ["REQUESTS_CA_BUNDLE"] = ca_path
            os.environ["CURL_CA_BUNDLE"] = ca_path
            return

def get_credentials():
    """
    Retrieves or refreshes Google API credentials (legacy file-based).

    Input: None
    Output: <Credentials object>
    """
    root_dir = Path(__file__).resolve().parents[1]
    _configure_ssl_ca(root_dir)
    token_path = root_dir / "token.json"
    creds_path = root_dir / "credentials.json"
    alt_creds_path = root_dir / "email_agent" / "credentials.json"

    if not creds_path.exists() and alt_creds_path.exists():
        creds_path = alt_creds_path

    if token_path.exists():
        return Credentials.from_authorized_user_file(str(token_path), SCOPES)

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_credentials_for_user(user_id: int) -> Optional[Credentials]:
    """
    Retrieves Google API credentials for a specific user from the database.
    
    Input: user_id (int)
    Output: <Credentials object> or None
    """
    try:
        from db.session import get_session
        from db.models import UserCredentials
        
        session = get_session()
        try:
            user_cred = session.query(UserCredentials).filter_by(user_id=user_id).first()
            if not user_cred:
                return None
            
            # If we have a token, use it
            if user_cred.token_json:
                token_data = json.loads(user_cred.token_json)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
                return creds
            
            # Otherwise, create new credentials from credentials_json
            if user_cred.credentials_json:
                creds_data = json.loads(user_cred.credentials_json)
                flow = InstalledAppFlow.from_client_config(creds_data, SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save token back to database
                token_data = json.loads(creds.to_json())
                user_cred.token_json = json.dumps(token_data)
                session.commit()
                
                return creds
        finally:
            session.close()
    except Exception as e:
        print(f"Error retrieving credentials for user {user_id}: {e}")
        return None


def store_credentials_for_user(user_id: int, credentials_json: str, token_json: str = "") -> bool:
    """
    Stores or updates Google API credentials for a user in the database.
    
    Input: user_id (int), credentials_json (str), token_json (str)
    Output: bool (success/failure)
    """
    try:
        from db.session import get_session
        from db.models import UserCredentials
        from datetime import datetime, timezone
        
        session = get_session()
        try:
            user_cred = session.query(UserCredentials).filter_by(user_id=user_id).first()
            now = datetime.now(tz=timezone.utc).isoformat()
            
            if user_cred:
                user_cred.credentials_json = credentials_json
                if token_json:
                    user_cred.token_json = token_json
                user_cred.updated_at = now
            else:
                user_cred = UserCredentials(
                    user_id=user_id,
                    credentials_json=credentials_json,
                    token_json=token_json or "",
                    created_at=now,
                    updated_at=now,
                )
            
            session.add(user_cred)
            session.commit()
            return True
        finally:
            session.close()
    except Exception as e:
        print(f"Error storing credentials for user {user_id}: {e}")
        return False


    return creds
