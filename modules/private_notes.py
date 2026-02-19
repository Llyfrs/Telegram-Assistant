import base64
import hashlib
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from pydantic import ConfigDict, Field

from modules.database import Document


class PrivateNote(Document):
    model_config = ConfigDict(collection_name="private_notes")

    encrypted_text: str
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def encrypt_note(note_text: str, password: str) -> str:
    key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
    return Fernet(key).encrypt(note_text.encode()).decode()


def save_private_note(note_text: str, password: str) -> None:
    PrivateNote(
        encrypted_text=encrypt_note(note_text, password),
    ).save()


def get_private_note_count() -> int:
    return PrivateNote._collection().count_documents({})
