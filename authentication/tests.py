# =============================================================================
# authentication/tests.py  —  Django Unit Tests (Backend)
#
# REAL DATABASE PE KOI EFFECT NAHI
# Django apna alag temporary test DB banata hai, tests ke baad delete ho jata hai
#
# COMMANDS:
#   Sab tests:        python manage.py test authentication
#   Sirf ye file:     python manage.py test authentication.tests
#   Specific class:   python manage.py test authentication.tests.SignupViewTest
#   Specific test:    python manage.py test authentication.tests.SignupViewTest.test_valid_customer_signup
#   Verbose:          python manage.py test authentication --verbosity=2
# =============================================================================

from django.test import TestCase, Client
from django.contrib.messages import get_messages
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta

from .models import CustomUser


# =============================================================================
# HELPER FUNCTION
# =============================================================================

def make_user(email='test@example.com', password='Test@1234',
              role='customer', username='TestUser', is_active=True):
    """Test ke liye CustomUser banata hai — direct DB insert, signup view bypass."""
    return CustomUser.objects.create_user(
        email=email, password=password,
        username=username, role=role, is_active=is_active,
    )


# =============================================================================
# TC-01 to TC-03 — PAGE LOAD TESTS
# =============================================================================

class PageLoadTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_login_signup_page_loads_200(self):
        """TC-01: /auth/login-signup/ 200 status ke saath load honi chahiye."""
        response = self.client.get('/auth/login-signup/')
        self.assertEqual(response.status_code, 200)

    def test_correct_template_used(self):
        """TC-01: Sahi template render ho rahi hai."""
        response = self.client.get('/auth/login-signup/')
        self.assertTemplateUsed(response, 'authentication/login_signup.html')

    def test_show_signup_param_passed_to_context(self):
        """TC-02: ?show=signup context mein 'signup' hona chahiye."""
        response = self.client.get('/auth/login-signup/?show=signup')
        self.assertEqual(response.context['show'], 'signup')

    def test_show_login_param_passed_to_context(self):
        """TC-03: ?show=login context mein 'login' hona chahiye."""
        response = self.client.get('/auth/login-signup/?show=login')
        self.assertEqual(response.context['show'], 'login')

    def test_default_show_is_login(self):
        """TC-03: Koi param na ho to default 'login' context mein aana chahiye."""
        response = self.client.get('/auth/login-signup/')
        self.assertEqual(response.context['show'], 'login')


# =============================================================================
# TC-06 to TC-21 — SIGNUP VIEW TESTS
# =============================================================================

class SignupViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = '/auth/signup/'

    def _post(self, **kwargs):
        """Signup POST shortcut."""
        defaults = {
            'name_or_pharmacy_name': 'Test User',
            'email': 'test@example.com',
            'password': 'Test@1234',
            'confirm_password': 'Test@1234',
            'signup-role': 'customer',
        }
        defaults.update(kwargs)
        return self.client.post(self.url, defaults)

    # ── TC-06: Valid customer signup ──────────────────────────────
    def test_valid_customer_signup_creates_user(self):
        """TC-06: Sahi data se customer account banna chahiye."""
        self._post(email='ali@example.com', **{'name_or_pharmacy_name': 'Ali'})
        self.assertTrue(CustomUser.objects.filter(email='ali@example.com').exists())

    def test_valid_customer_signup_redirects_to_login(self):
        """TC-06: Signup ke baad login page pe redirect hona chahiye."""
        response = self._post(email='ali@example.com', **{'name_or_pharmacy_name': 'Ali'})
        self.assertRedirects(response, '/auth/login-signup/?show=login')

    # ── TC-07: Valid pharmacy signup ──────────────────────────────
    def test_valid_pharmacy_signup_role_set(self):
        """TC-07: Pharmacy signup ke baad role 'pharmacy' hona chahiye."""
        self._post(email='ph@example.com', **{'signup-role': 'pharmacy', 'name_or_pharmacy_name': 'City Pharma'})
        user = CustomUser.objects.filter(email='ph@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, 'pharmacy')

    # ── TC-08: New user is active ─────────────────────────────────
    def test_new_user_is_active_after_signup(self):
        """TC-08: Signup ke baad user active hona chahiye (login kar sake)."""
        self._post(email='active@example.com')
        user = CustomUser.objects.get(email='active@example.com')
        self.assertTrue(user.is_active)

    # ── TC-09: Empty name ─────────────────────────────────────────
    def test_empty_name_blocks_signup(self):
        """TC-09: Name khali ho to user nahi banna chahiye."""
        self._post(email='noname@example.com', **{'name_or_pharmacy_name': ''})
        self.assertFalse(CustomUser.objects.filter(email='noname@example.com').exists())

    # ── TC-10: Empty email ────────────────────────────────────────
    def test_empty_email_shows_error(self):
        """TC-10: Email khali ho to 'required' error aana chahiye."""
        response = self._post(email='')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('required' in str(m).lower() for m in msgs))

    # ── TC-11/12: Empty password / confirm ───────────────────────
    def test_empty_password_shows_error(self):
        """TC-11/12: Password khali ho to error aana chahiye."""
        response = self._post(password='', confirm_password='')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('required' in str(m).lower() for m in msgs))

    # ── TC-13: Password too short ─────────────────────────────────
    def test_password_too_short_error(self):
        """TC-13: 8 chars se kam password — length error aana chahiye."""
        response = self._post(email='short@example.com', password='Ab@1', confirm_password='Ab@1')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('8' in str(m) or 'character' in str(m).lower() for m in msgs))
        self.assertFalse(CustomUser.objects.filter(email='short@example.com').exists())

    # ── TC-14: No uppercase ───────────────────────────────────────
    def test_password_no_uppercase_error(self):
        """TC-14: Uppercase nahi — error aana chahiye."""
        response = self._post(email='noupper@example.com', password='test@1234', confirm_password='test@1234')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('uppercase' in str(m).lower() for m in msgs))

    # ── TC-15: No number ──────────────────────────────────────────
    def test_password_no_number_error(self):
        """TC-15: Number nahi — error aana chahiye."""
        response = self._post(email='nonum@example.com', password='Test@abcd', confirm_password='Test@abcd')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('number' in str(m).lower() for m in msgs))

    # ── TC-16: No special char ────────────────────────────────────
    def test_password_no_special_char_error(self):
        """TC-16: Special char nahi — error aana chahiye."""
        response = self._post(email='nospec@example.com', password='Testabcd1', confirm_password='Testabcd1')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('special' in str(m).lower() for m in msgs))

    # ── TC-17: Strong password Abcd@123 ──────────────────────────
    def test_strong_password_abcd_at_123_passes(self):
        """TC-17: Abcd@123 — sab rules fulfill — account banna chahiye."""
        self._post(email='strong@example.com', password='Abcd@123', confirm_password='Abcd@123')
        self.assertTrue(CustomUser.objects.filter(email='strong@example.com').exists())

    # ── TC-18: Password mismatch ──────────────────────────────────
    def test_password_mismatch_shows_error(self):
        """TC-18: Password != confirm_password — 'do not match' error."""
        response = self._post(email='mis@example.com', password='Test@1234', confirm_password='Wrong@9999')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('match' in str(m).lower() for m in msgs))
        self.assertFalse(CustomUser.objects.filter(email='mis@example.com').exists())

    # ── TC-19/20: Invalid email formats ──────────────────────────
    def test_invalid_email_formats_blocked(self):
        """TC-19/20: 'invalidemail', 'test@', '@example.com' — sab block hone chahiye."""
        for bad in ['invalidemail', 'test@', '@example.com', 'no-at-sign']:
            response = self._post(email=bad)
            msgs = list(get_messages(response.wsgi_request))
            self.assertTrue(
                any('valid email' in str(m).lower() or 'required' in str(m).lower() for m in msgs),
                f"Email '{bad}' pe validation error nahi aaya"
            )

    # ── TC-21: Duplicate email ────────────────────────────────────
    def test_duplicate_email_shows_already_registered_error(self):
        """TC-21: Pehle se registered email pe 'already registered' error."""
        make_user(email='dup@example.com')
        response = self._post(email='dup@example.com')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('already' in str(m).lower() or 'registered' in str(m).lower() for m in msgs))

    # ── TC-27/28: Invalid role ────────────────────────────────────
    def test_invalid_role_blocked(self):
        """TC-27/28: 'hacker' ya blank role — signup nahi hona chahiye."""
        for bad_role in ['hacker', '', 'superuser']:
            self._post(email=f'{bad_role}@example.com', **{'signup-role': bad_role})
            self.assertFalse(CustomUser.objects.filter(email=f'{bad_role}@example.com').exists())

    # ── TC-51: SQL Injection ──────────────────────────────────────
    def test_sql_injection_in_email_does_not_crash(self):
        """TC-51: SQL injection email mein — server crash nahi hona chahiye."""
        response = self._post(email="'; DROP TABLE users; --")
        self.assertIn(response.status_code, [200, 302])
        self.assertEqual(CustomUser.objects.count(), 0)

    # ── TC-52: XSS in name ────────────────────────────────────────
    def test_xss_in_name_not_stored_raw(self):
        """TC-52: XSS name mein — agar user bane to raw <script> tag nahi hona chahiye."""
        self._post(email='xss@example.com', **{'name_or_pharmacy_name': '<script>alert("x")</script>'})
        user = CustomUser.objects.filter(email='xss@example.com').first()
        if user:
            self.assertNotIn('<script>', user.username or '')


# =============================================================================
# TC-22 to TC-26, TC-47, TC-49, TC-50, TC-54 — LOGIN VIEW TESTS
# =============================================================================

class LoginViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = '/auth/login/'
        self.customer = make_user(email='cust@example.com', password='Login@1234', role='customer')
        self.pharmacy  = make_user(email='pharm@example.com', password='Login@1234', role='pharmacy', username='PharmU')

    # ── TC-22: Correct login ──────────────────────────────────────
    def test_correct_credentials_redirect(self):
        """TC-22: Sahi email+password — 302 redirect hona chahiye."""
        response = self.client.post(self.url, {'email': 'cust@example.com', 'password': 'Login@1234'})
        self.assertEqual(response.status_code, 302)

    # ── TC-23: Wrong password ─────────────────────────────────────
    def test_wrong_password_shows_invalid_error(self):
        """TC-23: Galat password — 'invalid' error message aana chahiye."""
        response = self.client.post(self.url, {'email': 'cust@example.com', 'password': 'Wrong@999'})
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('invalid' in str(m).lower() for m in msgs))

    # ── TC-24: Wrong email ────────────────────────────────────────
    def test_wrong_email_shows_invalid_error(self):
        """TC-24: Registered nahi email — 'invalid' error aana chahiye."""
        response = self.client.post(self.url, {'email': 'ghost@example.com', 'password': 'Test@1234'})
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('invalid' in str(m).lower() for m in msgs))

    # ── TC-25: Empty fields ───────────────────────────────────────
    def test_empty_login_fields_show_error(self):
        """TC-25: Khali fields — error aana chahiye."""
        response = self.client.post(self.url, {'email': '', 'password': ''})
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any('required' in str(m).lower() or 'email' in str(m).lower() for m in msgs))

    # ── TC-26: Login after signup ─────────────────────────────────
    def test_login_after_signup_works(self):
        """TC-26: Naya signup karo, phir login karo — 302 redirect hona chahiye."""
        self.client.post('/auth/signup/', {
            'name_or_pharmacy_name': 'Fresh', 'email': 'fresh@example.com',
            'password': 'Fresh@123', 'confirm_password': 'Fresh@123', 'signup-role': 'customer',
        })
        response = self.client.post(self.url, {'email': 'fresh@example.com', 'password': 'Fresh@123'})
        self.assertEqual(response.status_code, 302)

    # ── TC-47: Logged-in user login page khole ────────────────────
    def test_logged_in_user_redirected_from_login_page(self):
        """TC-47: Pehle se logged in user login page khole — dashboard redirect."""
        self.client.force_login(self.customer)
        response = self.client.get('/auth/login-signup/')
        self.assertEqual(response.status_code, 302)

    # ── TC-49: Customer redirect ──────────────────────────────────
    def test_customer_redirected_to_customer_dashboard(self):
        """TC-49: Customer login — pharmacy URL mein nahi aana chahiye."""
        response = self.client.post(self.url, {'email': 'cust@example.com', 'password': 'Login@1234'})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('pharmacy', response['Location'])

    # ── TC-50: Pharmacy redirect ──────────────────────────────────
    def test_pharmacy_redirected_to_pharmacy_dashboard(self):
        """TC-50: Pharmacy login — pharmacy URL mein hona chahiye."""
        response = self.client.post(self.url, {'email': 'pharm@example.com', 'password': 'Login@1234'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('pharmacy', response['Location'])

    # ── TC-54: CSRF protection ────────────────────────────────────
    def test_login_without_csrf_token_blocked(self):
        """TC-54: CSRF token ke bina POST — 403 Forbidden aana chahiye."""
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(self.url, {'email': 'cust@example.com', 'password': 'Login@1234'})
        self.assertEqual(response.status_code, 403)


# =============================================================================
# TC-48 — LOGOUT VIEW TESTS
# =============================================================================

class LogoutViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = make_user()

    def test_logout_redirects(self):
        """TC-48: Logout ke baad redirect hona chahiye."""
        self.client.force_login(self.user)
        response = self.client.get('/auth/logout/')
        self.assertEqual(response.status_code, 302)

    def test_logout_clears_session_protected_page_blocked(self):
        """TC-48: Logout ke baad protected page access block honi chahiye."""
        self.client.force_login(self.user)
        self.client.get('/auth/logout/')
        response = self.client.get('/auth/settings/')
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_logout_does_not_crash(self):
        """TC-48: Bina login ke logout URL crash nahi karna chahiye."""
        response = self.client.get('/auth/logout/')
        self.assertEqual(response.status_code, 302)


# =============================================================================
# TC-38 to TC-42 — FORGOT PASSWORD AJAX TESTS
# =============================================================================

class ForgotPasswordAjaxTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = '/auth/forgot-password-ajax/'
        self.user = make_user(email='forgot@example.com')

    @patch('authentication.views.PharmaHubPasswordResetForm')
    def test_valid_email_returns_ok_true(self, mock_form_class):
        """TC-38/39: Registered email pe ok:True response aana chahiye."""
        mock_form = MagicMock()
        mock_form.is_valid.return_value = True
        mock_form.save.return_value = None
        mock_form_class.return_value = mock_form
        response = self.client.post(self.url, {'email': 'forgot@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('ok'))

    def test_unregistered_email_returns_404(self):
        """TC-40: Unregistered email — 404 aana chahiye."""
        response = self.client.post(self.url, {'email': 'ghost@example.com'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json().get('ok'))

    def test_empty_email_returns_400(self):
        """TC-41: Khali email — 400 bad request aana chahiye."""
        response = self.client.post(self.url, {'email': ''})
        self.assertEqual(response.status_code, 400)

    def test_get_request_not_allowed(self):
        """TC-42: GET pe 405 Method Not Allowed aana chahiye."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_inactive_user_email_returns_404(self):
        """TC-40 variant: Inactive user ka email bhi 404 return kare."""
        make_user(email='inactive@example.com', is_active=False, username='InactiveU')
        response = self.client.post(self.url, {'email': 'inactive@example.com'})
        self.assertEqual(response.status_code, 404)


# =============================================================================
# TC-43 to TC-46 — GOOGLE OAUTH TESTS (Mock-based, real Google nahi)
# =============================================================================

class GoogleOAuthViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_google_signup_customer_sets_session(self):
        """TC-43: action=signup&role=customer — session mein role save ho."""
        self.client.get('/auth/login-signup/?action=signup&role=customer')
        self.assertEqual(self.client.session.get('selected_role'), 'customer')
        self.assertEqual(self.client.session.get('google_auth_action'), 'signup')

    def test_google_signup_customer_redirects_to_google(self):
        """TC-43: action=signup&role=customer — Google pe redirect hona chahiye."""
        response = self.client.get('/auth/login-signup/?action=signup&role=customer')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/google/login/', response['Location'])

    def test_google_signup_pharmacy_sets_pharmacy_role_in_session(self):
        """TC-44: action=signup&role=pharmacy — session mein pharmacy role save ho."""
        self.client.get('/auth/login-signup/?action=signup&role=pharmacy')
        self.assertEqual(self.client.session.get('selected_role'), 'pharmacy')

    def test_google_signup_without_role_redirects_to_signup_with_error(self):
        """TC-45: Role select kiye bina Google signup — error + signup page redirect."""
        response = self.client.get('/auth/login-signup/?action=signup&role=')
        self.assertEqual(response.status_code, 302)
        self.assertIn('show=signup', response['Location'])

    def test_google_signup_invalid_role_safely_redirects(self):
        """TC-45: Galat role pe crash nahi hona chahiye."""
        response = self.client.get('/auth/login-signup/?action=signup&role=hacker')
        self.assertEqual(response.status_code, 302)
        self.assertIn('show=signup', response['Location'])

    def test_google_login_action_sets_session(self):
        """TC-46: action=login — session mein 'login' action save ho."""
        self.client.get('/auth/login-signup/?action=login')
        self.assertEqual(self.client.session.get('google_auth_action'), 'login')

    def test_google_multiple_calls_last_role_wins(self):
        """TC-46: Multiple clicks — last request ki session value win kare."""
        self.client.get('/auth/login-signup/?action=signup&role=customer')
        self.client.get('/auth/login-signup/?action=signup&role=pharmacy')
        self.assertEqual(self.client.session.get('selected_role'), 'pharmacy')

    def test_google_adapter_pre_social_login_connects_existing_user(self):
        """
        TC-43/44: Same email pehle registered ho to Google auto-connect kare.
        Adapter ka pre_social_login logic test karta hai (mock-based).
        """
        from authentication.adapters import CustomSocialAccountAdapter

        adapter = CustomSocialAccountAdapter()
        mock_request = MagicMock()

        existing_user = make_user(email='google@example.com')
        sociallogin = MagicMock()
        sociallogin.account.extra_data = {'email': 'google@example.com'}
        sociallogin.is_existing = False

        with patch('authentication.adapters.User.objects.get', return_value=existing_user):
            try:
                adapter.pre_social_login(mock_request, sociallogin)
                sociallogin.connect.assert_called_once_with(mock_request, existing_user)
            except Exception as e:
                self.fail(f"pre_social_login crash ho gaya: {e}")

    def test_google_adapter_new_user_no_crash(self):
        """
        TC-43: Naya email (pehle registered nahi) pe adapter silently pass kare.
        """
        from authentication.adapters import CustomSocialAccountAdapter

        adapter = CustomSocialAccountAdapter()
        mock_request = MagicMock()
        sociallogin = MagicMock()
        sociallogin.account.extra_data = {'email': 'brand_new@example.com'}
        sociallogin.is_existing = False

        with patch('authentication.adapters.User.objects.get', side_effect=CustomUser.DoesNotExist):
            try:
                adapter.pre_social_login(mock_request, sociallogin)
            except Exception as e:
                self.fail(f"New user pe adapter crash ho gaya: {e}")


# =============================================================================
# TC-53 — MIDDLEWARE / ROLE-BASED ACCESS TESTS
# =============================================================================

class MiddlewareAccessTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.customer = make_user(email='cust@example.com', role='customer')
        self.pharmacy = make_user(email='ph@example.com', role='pharmacy', username='PhMW')

    def test_unauthenticated_pharmacy_dashboard_redirects(self):
        """TC-53: Login ke bina /pharmacy_dashboard/ — login page redirect."""
        response = self.client.get('/pharmacy_dashboard/')
        self.assertEqual(response.status_code, 302)

    def test_customer_blocked_from_pharmacy_dashboard(self):
        """TC-53: Customer ko pharmacy dashboard access nahi milna chahiye."""
        self.client.force_login(self.customer)
        response = self.client.get('/pharmacy_dashboard/')
        self.assertIn(response.status_code, [302, 403])

    def test_account_settings_requires_login(self):
        """TC-53: /auth/settings/ bina login ke accessible nahi honi chahiye."""
        response = self.client.get('/auth/settings/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login-signup/', response['Location'])


# =============================================================================
# CUSTOM USER MODEL TESTS
# =============================================================================

class CustomUserModelTest(TestCase):

    def test_customer_role_properties(self):
        """Customer user — is_customer_user True, baaki False."""
        u = make_user(role='customer')
        self.assertTrue(u.is_customer_user)
        self.assertFalse(u.is_pharmacist_user)
        self.assertFalse(u.is_admin_user)

    def test_pharmacy_role_properties(self):
        """Pharmacy user — is_pharmacist_user True hona chahiye."""
        u = make_user(role='pharmacy', email='ph@example.com')
        self.assertTrue(u.is_pharmacist_user)

    def test_email_is_username_field(self):
        """USERNAME_FIELD 'email' hona chahiye."""
        self.assertEqual(CustomUser.USERNAME_FIELD, 'email')

    def test_failed_login_attempts_default_zero(self):
        """Naya user — failed_login_attempts 0 hona chahiye."""
        u = make_user()
        self.assertEqual(u.failed_login_attempts, 0)

    def test_failed_attempts_save_to_db(self):
        """Failed attempts DB mein persist hone chahiye."""
        u = make_user()
        u.failed_login_attempts = 3
        u.save()
        self.assertEqual(CustomUser.objects.get(pk=u.pk).failed_login_attempts, 3)

    def test_inactive_user_cannot_authenticate(self):
        """Inactive user authenticate nahi ho sakta."""
        from django.contrib.auth import authenticate
        make_user(email='off@example.com', is_active=False, username='OffUser')
        self.assertIsNone(authenticate(None, email='off@example.com', password='Test@1234'))

    def test_str_contains_email_and_role(self):
        """__str__ mein email aur role dono hone chahiye."""
        u = make_user(email='str@example.com', role='customer')
        self.assertIn('str@example.com', str(u))
        self.assertIn('customer', str(u))


# =============================================================================
# EMAIL BACKEND + ACCOUNT LOCKOUT TESTS
# =============================================================================

class EmailBackendTest(TestCase):

    def setUp(self):
        self.user = make_user(email='be@example.com', password='Back@1234')

    def test_correct_credentials_return_user(self):
        """Sahi email+password — user object milna chahiye."""
        from django.contrib.auth import authenticate
        self.assertIsNotNone(authenticate(None, email='be@example.com', password='Back@1234'))

    def test_wrong_password_returns_none(self):
        """Galat password — None milna chahiye."""
        from django.contrib.auth import authenticate
        self.assertIsNone(authenticate(None, email='be@example.com', password='Wrong@999'))

    def test_wrong_email_returns_none(self):
        """Registered nahi email — None milna chahiye."""
        from django.contrib.auth import authenticate
        self.assertIsNone(authenticate(None, email='ghost@example.com', password='Back@1234'))

    def test_case_insensitive_email_login(self):
        """UPPERCASE email bhi login kare (normalize hoti hai)."""
        from django.contrib.auth import authenticate
        self.assertIsNotNone(authenticate(None, email='BE@EXAMPLE.COM', password='Back@1234'))

    def test_account_locked_after_5_failures(self):
        """
        5 failed attempts ke baad sahi password se bhi login block hona chahiye.
        backends.py mein lockout logic laga ho to ye pass hoga.
        """
        from django.contrib.auth import authenticate
        self.user.failed_login_attempts = 5
        self.user.last_failed_login = timezone.now()
        self.user.save()
        self.assertIsNone(authenticate(None, email='be@example.com', password='Back@1234'))

    def test_lockout_expires_after_15_minutes(self):
        """hours 2 purana lockout — expire ho jana chahiye, login hona chahiye."""
        from django.contrib.auth import authenticate
        self.user.failed_login_attempts = 5
        self.user.last_failed_login = timezone.now() - timedelta(hours=2)
        self.user.save()
        self.assertIsNotNone(authenticate(None, email='be@example.com', password='Back@1234'))

    def test_failed_attempts_reset_after_successful_login(self):
        """
        Successful login ke baad views.py failed_login_attempts ko 0 kare.
        views.py mein reset logic laga ho to ye pass hoga.
        """
        self.user.failed_login_attempts = 3
        self.user.save()
        Client().post('/auth/login/', {'email': 'be@example.com', 'password': 'Back@1234'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)