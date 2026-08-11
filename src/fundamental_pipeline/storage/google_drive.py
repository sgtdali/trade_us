"""Thin Google Drive client for archiving raw/{TICKER} source documents
outside git. Auth is a cached OAuth token under .secrets/google_drive/
(never committed -- see .gitignore)."""
from __future__ import annotations

from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_MIME = "application/vnd.google-apps.folder"


def _secrets_dir(repo_root: Path) -> Path:
    return repo_root / ".secrets" / "google_drive"


def get_service(repo_root: Path):
    secrets = _secrets_dir(repo_root)
    token_path = secrets / "token.json"
    client_secret_path = secrets / "client_secret.json"

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = True
            except RefreshError:
                refreshed = False
        if not refreshed:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name: str, parent_id: str | None = None) -> str:
    query = f"name = '{name}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    else:
        query += " and 'root' in parents"
    results = service.files().list(q=query, fields="files(id, name)", spaces="drive").execute()
    matches = results.get("files", [])
    if matches:
        return matches[0]["id"]
    metadata = {"name": name, "mimeType": FOLDER_MIME}
    if parent_id:
        metadata["parents"] = [parent_id]
    created = service.files().create(body=metadata, fields="id").execute()
    return created["id"]


def find_file(service, name: str, parent_id: str) -> str | None:
    query = f"name = '{name}' and '{parent_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)", spaces="drive").execute()
    matches = results.get("files", [])
    return matches[0]["id"] if matches else None


def upload_file(service, local_path: Path, parent_id: str) -> str:
    existing_id = find_file(service, local_path.name, parent_id)
    media = MediaFileUpload(str(local_path), resumable=True)
    if existing_id:
        service.files().update(fileId=existing_id, media_body=media).execute()
        return existing_id
    metadata = {"name": local_path.name, "parents": [parent_id]}
    created = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return created["id"]


def download_file(service, file_id: str, dest_path: Path) -> None:
    from googleapiclient.http import MediaIoBaseDownload

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
