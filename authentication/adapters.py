from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.contrib import messages
from customers_d.models import Customer

User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for handling social account connections
    Auto-connects Google accounts with existing users having same email
    """

    def pre_social_login(self, request, sociallogin):
        """
        Google login se pehle yeh function run hoga
        """

        # Email extract karo Google se
        email = sociallogin.account.extra_data.get('email')

        if not email:
            return

        try:
            existing_user = User.objects.get(email=email)

            # Existing Google account connect karo
            if not sociallogin.is_existing:
                sociallogin.connect(request, existing_user)

        except User.DoesNotExist:
            # New user automatically signup hoga
            pass

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Auto-signup allow karta hai
        """
        return True

    def save_user(self, request, sociallogin, form=None):
        """
        Google auth workflow
        """

        auth_action = request.session.get('google_auth_action')

        # ============================================
        # GOOGLE LOGIN FLOW
        # ============================================
        if auth_action == 'login':

            email = sociallogin.account.extra_data.get('email')

            try:
                # Existing user login
                existing_user = User.objects.get(email=email)

                # Session cleanup
                request.session.pop('selected_role', None)
                request.session.pop('google_auth_action', None)

                return existing_user

            except User.DoesNotExist:

                # Session cleanup
                request.session.pop('selected_role', None)
                request.session.pop('google_auth_action', None)

                messages.error(
                    request,
                    'No account found. Please sign up first.'
                )

                raise ImmediateHttpResponse(
                    redirect('/auth/login-signup/?show=signup')
                )

        # ============================================
        # GOOGLE SIGNUP FLOW
        # ============================================
        user = super().save_user(request, sociallogin, form)

        selected_role = request.session.get('selected_role')

        # Assign role
        if selected_role in ['customer', 'pharmacy']:

            user.role = selected_role
            user.save()

            if selected_role == 'customer':
                Customer.objects.get_or_create(user=user)

        # ============================================
        # SESSION CLEANUP
        # ============================================
        request.session.pop('selected_role', None)
        request.session.pop('google_auth_action', None)

        return user