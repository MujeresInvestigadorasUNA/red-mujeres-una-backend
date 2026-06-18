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
    if not settings.FIREBASE_SERVICE_ACCOUNT_PATH:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_PATH is not configured")
    cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    _initialized = True


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
