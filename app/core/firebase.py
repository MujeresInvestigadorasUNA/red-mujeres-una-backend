import logging
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from app.core.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def _initialize():
    global _initialized
    if _initialized:
        return
    if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        import json
        cred = credentials.Certificate(json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON))
    elif settings.FIREBASE_SERVICE_ACCOUNT_PATH:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    else:
        raise RuntimeError("Firebase credentials not configured")
    firebase_admin.initialize_app(cred)
    _initialized = True


def ensure_initialized():
    _initialize()


def generate_password_reset_link(email: str) -> str:
    _initialize()
    return firebase_auth.generate_password_reset_link(email)


def generate_email_verification_link(email: str) -> str:
    _initialize()
    return firebase_auth.generate_email_verification_link(email)


def delete_firebase_user_by_email(email: str) -> bool:
    """Delete a Firebase user by email. Returns True if deleted, False if not found."""
    _initialize()
    try:
        user = firebase_auth.get_user_by_email(email)
        firebase_auth.delete_user(user.uid)
        logger.info("Firebase user deleted: %s", email)
        return True
    except firebase_auth.UserNotFoundError:
        return False
    except Exception as e:
        logger.error("Error deleting Firebase user %s: %s", email, e)
        raise
