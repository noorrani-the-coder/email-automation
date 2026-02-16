from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from pathlib import Path
import os
import sys
import httplib2
import certifi

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
    Retrieves or refreshes Google API credentials.

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
