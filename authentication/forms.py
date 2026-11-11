from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from .models import CustomUser as User

from django.utils.html import strip_tags

class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'license']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        # strip_tags se <script> jaise tags remove ho jaate hain.
        # Note: Django templates `{{ user.username }}` ko auto-escape karte hain,
        # isliye save-time pe HTML escape karna nahi chahiye.
        return strip_tags(username).strip()

class LoginForm(forms.Form):
    email = forms.EmailField(max_length=255)
    password = forms.CharField(widget=forms.PasswordInput)


class PharmaHubPasswordResetForm(PasswordResetForm):
    """
    Allow password-reset emails for active users even if password is currently unusable
    (e.g. social login users). This avoids silent "email sent" with no email delivered.
    """
    def get_users(self, email):
        UserModel = get_user_model()
        email_field_name = UserModel.get_email_field_name()
        lookup = {f"{email_field_name}__iexact": email}
        return UserModel._default_manager.filter(**lookup, is_active=True)
