from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views
from .views import MyPasswordResetConfirmView
from .forms import PharmaHubPasswordResetForm

app_name = 'authentication'

urlpatterns = [
    path('login-signup/', views.login_signup_view, name='login_signup'),
    path('redirect/', views.post_auth_redirect, name='post_auth_redirect'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # authentication/urls.py mein check karein ke name='verification_view' lazmi ho
    path('verify/', views.verification_view, name='verification_view'),
    path('settings/', views.account_settings_view, name='account_settings'),
    path('forgot-password-ajax/', views.forgot_password_ajax, name='forgot_password_ajax'),
    # Authenticated change password flow
    path(
        'change-password/',
        auth_views.PasswordChangeView.as_view(
            template_name='authentication/password_change_form.html',
            success_url=reverse_lazy('authentication:password_change_done')
        ),
        name='change_password'
    ),
    path(
        'change-password/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='authentication/password_change_done.html'
        ),
        name='password_change_done'
    ),
    # 1. Password Reset Request (Iska name 'password_reset' hi rahega)
    path('reset_password/', 
        auth_views.PasswordResetView.as_view(
            form_class=PharmaHubPasswordResetForm,
            template_name="authentication/password_reset_form.html", 
            email_template_name='authentication/password_reset_email.html',
            success_url=reverse_lazy('authentication:password_reset_done')
        ), 
        name="password_reset"),
    # 2. Email bhejne ke baad ka page (Confirmation)
    path('reset_password_sent/', 
        auth_views.PasswordResetDoneView.as_view(
            template_name="authentication/password_reset_done.html"
        ), 
        name="password_reset_done"),
    # 3. Jab user email ke link par click karega (New Password Form)
    path('reset/<uidb64>/<token>/', 
         MyPasswordResetConfirmView.as_view(
        success_url=reverse_lazy('authentication:password_reset_complete')
         ), 
         name="password_reset_confirm"),
    # 4. Final Step: Jab password badal jaye (Wapas Login page par bhej rahe hain)
    path('reset_password_complete/', 
        auth_views.PasswordResetCompleteView.as_view(
            template_name="authentication/login_signup.html"
        ), 
        name="password_reset_complete"),
]
