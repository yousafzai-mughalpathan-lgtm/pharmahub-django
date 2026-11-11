from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from allauth.account.auth_backends import AuthenticationBackend

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def _is_locked_out(user):
    """
    Check if account is locked.
    """
    # User abhi threshold tak nahi pohncha
    if user.failed_login_attempts < MAX_FAILED_ATTEMPTS:
        return False

    now = timezone.now()

    # 1. Agar lockout_until explicit set hai (Standard Flow)
    if user.lockout_until:
        if now < user.lockout_until:
            return True

        # Lock expire ho gaya → reset
        user.failed_login_attempts = 0
        user.lockout_until = None
        user.last_failed_login = None

        user.save(update_fields=[
            'failed_login_attempts',
            'lockout_until',
            'last_failed_login'
        ])
        return False

    # 2. Safety Fallback: Agar lockout_until missing hai par last_failed_login maujood hai (Unit Tests ke liye)
    if user.last_failed_login:
        lockout_expiry = user.last_failed_login + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        if now < lockout_expiry:
            return True
        
        # 15 minutes guzar chuke hain → Fields reset karein
        user.failed_login_attempts = 0
        user.lockout_until = None
        user.last_failed_login = None
        user.save(update_fields=[
            'failed_login_attempts',
            'lockout_until',
            'last_failed_login'
        ])
        return False

    # Safety fallback agar dynamic tracks empty hain par attempts >= 5 hain
    return True


class EmailBackend(ModelBackend):

    def authenticate(
        self,
        request,
        username=None,
        email=None,
        password=None,
        **kwargs
    ):
        email = email or username

        if not email or not password:
            return None

        try:
            user = User.objects.get(email__iexact=email)
            user.refresh_from_db()

        except User.DoesNotExist:
            return None

        # ✅ LOCK CHECK FIRST
        if _is_locked_out(user):
            return None

        # ✅ CORRECT PASSWORD
        if user.check_password(password):

            # inactive users block
            if not user.is_active:
                return None

            # reset counters
            user.failed_login_attempts = 0
            user.lockout_until = None
            user.last_failed_login = None

            user.save(update_fields=[
                'failed_login_attempts',
                'lockout_until',
                'last_failed_login'
            ])

            return user

        # ✅ WRONG PASSWORD
        user.failed_login_attempts += 1
        user.last_failed_login = timezone.now()

        # lock account
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.lockout_until = timezone.now() + timedelta(
                minutes=LOCKOUT_DURATION_MINUTES
            )

        user.save(update_fields=[
            'failed_login_attempts',
            'lockout_until',
            'last_failed_login'
        ])

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


# Optional compatibility backend
class LockoutAwareModelBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get("email") or username

        if not email or not password:
            return None

        try:
            user = User.objects.get(email__iexact=email)
            user.refresh_from_db()

        except User.DoesNotExist:
            return None

        # lock check
        if _is_locked_out(user):
            return None

        # correct password
        if user.check_password(password):

            if not user.is_active:
                return None

            user.failed_login_attempts = 0
            user.lockout_until = None
            user.last_failed_login = None

            user.save(update_fields=[
                'failed_login_attempts',
                'lockout_until',
                'last_failed_login'
            ])

            return user

        # wrong password
        user.failed_login_attempts += 1
        user.last_failed_login = timezone.now()

        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.lockout_until = timezone.now() + timedelta(
                minutes=LOCKOUT_DURATION_MINUTES
            )

        user.save(update_fields=[
            'failed_login_attempts',
            'lockout_until',
            'last_failed_login'
        ])

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        

class LockoutAwareAllauthBackend(AuthenticationBackend):
    """Allauth backend with lockout check — replaces raw allauth backend."""

    def authenticate(self, request, **credentials):
        email = credentials.get('email') or credentials.get('username')
        if email:
            try:
                user = User.objects.get(email__iexact=email)
                if _is_locked_out(user):
                    return None
            except User.DoesNotExist:
                pass
        return super().authenticate(request, **credentials)