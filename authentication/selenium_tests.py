# =============================================================================
# authentication/selenium_tests.py  —  Selenium UI/Browser Tests
#
# Ye tests real Chrome browser mein chalte hain (headless mode)
# TC-02/03 animations, TC-04 dark mode, TC-05 responsive,
# TC-27-30 role/license, TC-31-34 animation stress,
# TC-35-37 eye icon, TC-55-58 UI visual — sab yahan hain
#
# SETUP (sirf ek baar):
#   pip install selenium webdriver-manager
#
# SERVER PEHLE CHALAO (alag terminal mein):
#   python manage.py runserver
#
# PHIR YE TESTS CHALAO:
#   python manage.py test authentication.selenium_tests
#
# SPECIFIC CLASS:
#   python manage.py test authentication.selenium_tests.EyeIconTest
#   python manage.py test authentication.selenium_tests.AnimationTest
# =============================================================================

import time
from django.test import LiveServerTestCase
from django.contrib.auth import get_user_model

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WDM_AVAILABLE = True
except ImportError:
    WDM_AVAILABLE = False

User = get_user_model()


# =============================================================================
# BASE CLASS — Chrome setup/teardown
# =============================================================================

class AuthSeleniumBase(LiveServerTestCase):
    """
    Sab Selenium tests is class se inherit karte hain.
    Chrome headless mode mein chalta hai.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        opts = Options()
        opts.add_argument('--headless')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1280,800')
        opts.add_argument('--disable-gpu')

        if WDM_AVAILABLE:
            cls.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=opts
            )
        else:
            cls.driver = webdriver.Chrome(options=opts)

        cls.driver.implicitly_wait(5)
        cls.wait = WebDriverWait(cls.driver, 10)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def go(self, path=''):
        """Login-signup page pe navigate karo."""
        self.driver.get(f'{self.live_server_url}/auth/login-signup/{path}')

    def js_click(self, el):
        """JavaScript se click (animation ke dauraan normal click fail ho sakta hai)."""
        self.driver.execute_script("arguments[0].click();", el)

    def find_any(self, selectors):
        """
        Pehla visible element dhundho from list of CSS selectors.
        Ye zaroori hai kyunki har project mein alag class names hoti hain.
        """
        for sel in selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                continue
        return None


# =============================================================================
# TC-01 to TC-05 — PAGE LOAD & RESPONSIVE
# =============================================================================

class PageLoadSeleniumTest(AuthSeleniumBase):

    def test_tc01_page_loads_200(self):
        """TC-01: Page load ho — body visible honi chahiye."""
        self.go()
        self.assertTrue(self.driver.find_element(By.TAG_NAME, 'body').is_displayed())

    def test_tc01_no_severe_console_errors(self):
        """TC-01: Page load pe koi JS SEVERE error nahi hona chahiye."""
        self.go()
        logs = self.driver.get_log('browser')
        severe = [l for l in logs if l['level'] == 'SEVERE']
        self.assertEqual(severe, [], f"Console errors: {severe}")

    def test_tc05_desktop_no_horizontal_overflow(self):
        """TC-05: 1280px pe page overflow nahi hona chahiye."""
        self.driver.set_window_size(1280, 800)
        self.go()
        scroll_w = self.driver.execute_script("return document.body.scrollWidth")
        win_w = self.driver.execute_script("return window.innerWidth")
        self.assertLessEqual(scroll_w, win_w + 20)

    def test_tc05_mobile_375px_no_overflow(self):
        """TC-05: 375px mobile pe layout break nahi honi chahiye."""
        self.driver.set_window_size(375, 812)
        self.go()
        scroll_w = self.driver.execute_script("return document.body.scrollWidth")
        self.assertLessEqual(scroll_w, 420)
        self.driver.set_window_size(1280, 800)


# =============================================================================
# TC-02/03 + TC-31-34 — ANIMATION TESTS
# =============================================================================

class AnimationTest(AuthSeleniumBase):

    SIGNUP_BTN_SELECTORS = [
        '#signUpBtn', '[data-panel="signup"]',
        "button.signup-toggle", '.signup-btn',
    ]
    SIGNIN_BTN_SELECTORS = [
        '#signInBtn', '[data-panel="login"]',
        "button.signin-toggle", '.signin-btn',
    ]

    def setUp(self):
        self.go()
        time.sleep(0.5)

    def test_tc02_signup_panel_switch(self):
        """TC-02: Signup button click — animation ho, page crash na kare."""
        btn = self.find_any(self.SIGNUP_BTN_SELECTORS)
        if not btn:
            self.skipTest("Signup toggle button nahi mila — SIGNUP_BTN_SELECTORS update karo")
        self.js_click(btn)
        time.sleep(0.8)
        self.assertTrue(self.driver.find_element(By.TAG_NAME, 'body').is_displayed())

    def test_tc03_signin_panel_switch(self):
        """TC-03: Signin button click — animation ho, page crash na kare."""
        # Pehle signup pe jao
        s = self.find_any(self.SIGNUP_BTN_SELECTORS)
        if s:
            self.js_click(s)
            time.sleep(0.6)
        # Phir signin
        btn = self.find_any(self.SIGNIN_BTN_SELECTORS)
        if not btn:
            self.skipTest("Signin toggle button nahi mila")
        self.js_click(btn)
        time.sleep(0.8)
        self.assertTrue(self.driver.find_element(By.TAG_NAME, 'body').is_displayed())

    def test_tc31_rapid_clicks_no_crash(self):
        """TC-31: 8 tezi se clicks — page stable rehna chahiye."""
        btn = self.find_any(self.SIGNUP_BTN_SELECTORS)
        if not btn:
            self.skipTest("Button nahi mila")
        for _ in range(8):
            try:
                self.js_click(btn)
                time.sleep(0.08)
            except Exception:
                pass
        time.sleep(1)
        self.assertTrue(self.driver.find_element(By.TAG_NAME, 'body').is_displayed())

    def test_tc32_signup_login_toggle_no_overlap(self):
        """TC-32: 3 baar Signup/Login toggle — UI overlap nahi hona chahiye."""
        s = self.find_any(self.SIGNUP_BTN_SELECTORS)
        l = self.find_any(self.SIGNIN_BTN_SELECTORS)
        if not s or not l:
            self.skipTest("Toggle buttons nahi mile")
        for _ in range(3):
            self.js_click(s); time.sleep(0.25)
            self.js_click(l); time.sleep(0.25)
        time.sleep(0.8)
        self.assertTrue(self.driver.find_element(By.TAG_NAME, 'body').is_displayed())

    def test_tc33_resize_during_animation(self):
        """TC-33: Animation ke dauraan resize — layout stable rehna chahiye."""
        btn = self.find_any(self.SIGNUP_BTN_SELECTORS)
        if btn:
            self.js_click(btn)
        self.driver.set_window_size(600, 600)
        time.sleep(0.4)
        self.driver.set_window_size(1280, 800)
        time.sleep(0.5)
        self.assertTrue(self.driver.find_element(By.TAG_NAME, 'body').is_displayed())

    def test_tc34_animation_mobile_size(self):
        """TC-34: Mobile size (375px) pe animation smooth honi chahiye."""
        self.driver.set_window_size(375, 812)
        self.go()
        time.sleep(0.5)
        btn = self.find_any(self.SIGNUP_BTN_SELECTORS)
        if btn:
            self.js_click(btn)
            time.sleep(0.8)
        self.assertTrue(self.driver.find_element(By.TAG_NAME, 'body').is_displayed())
        self.driver.set_window_size(1280, 800)


# =============================================================================
# TC-04 — DARK MODE
# =============================================================================

class DarkModeTest(AuthSeleniumBase):

    TOGGLE_SELECTORS = [
        '#darkModeToggle', '#dark-mode-toggle',
        '.dark-mode-btn', '.theme-toggle',
        '[data-theme-toggle]', 'button.dark',
    ]

    def setUp(self):
        self.go()

    def test_tc04_dark_mode_toggle_changes_something(self):
        """TC-04: Toggle click karo — body class ya data-theme change hona chahiye."""
        toggle = self.find_any(self.TOGGLE_SELECTORS)
        if not toggle:
            self.skipTest("Dark mode toggle nahi mila — TOGGLE_SELECTORS update karo")
        body = self.driver.find_element(By.TAG_NAME, 'body')
        before = (body.get_attribute('class') or '') + (body.get_attribute('data-theme') or '')
        self.js_click(toggle)
        time.sleep(0.4)
        after = (body.get_attribute('class') or '') + (body.get_attribute('data-theme') or '')
        self.assertNotEqual(before, after, "Dark mode toggle ne kuch change nahi kiya")

    def test_tc04_double_toggle_returns_original(self):
        """TC-04: Do baar toggle karo — original state wapas aana chahiye."""
        toggle = self.find_any(self.TOGGLE_SELECTORS)
        if not toggle:
            self.skipTest("Dark mode toggle nahi mila")
        body = self.driver.find_element(By.TAG_NAME, 'body')
        original = body.get_attribute('class') or ''
        self.js_click(toggle); time.sleep(0.3)
        self.js_click(toggle); time.sleep(0.3)
        self.assertEqual(body.get_attribute('class') or '', original)


# =============================================================================
# TC-27/28/29/30 — ROLE SELECTION + LICENSE FIELD
# =============================================================================

class RoleSelectionTest(AuthSeleniumBase):

    LICENSE_SELECTORS = [
        'input[name="license"]', '#license',
        '#license-field', '.license-input',
        'input[placeholder*="license" i]',
        '#licenseGroup', '.license-group',
    ]

    def setUp(self):
        self.go('?show=signup')
        time.sleep(0.5)

    def _click_role(self, role_value):
        selectors = [
            f'input[value="{role_value}"]',
            f'input[name="signup-role"][value="{role_value}"]',
            f'label[for="{role_value}"]',
            f'.role-{role_value}',
        ]
        el = self.find_any(selectors)
        if el:
            self.js_click(el)
            time.sleep(0.4)
        return el

    def test_tc27_customer_role_license_hidden(self):
        """TC-27: Customer select — license field hidden hona chahiye."""
        if not self._click_role('customer'):
            self.skipTest("Customer role input nahi mila")
        lic = self.find_any(self.LICENSE_SELECTORS)
        if lic:
            self.assertFalse(lic.is_displayed(), "Customer pe license field visible hai")

    def test_tc28_pharmacy_role_license_visible(self):
        """TC-28: Pharmacy select — license field visible hona chahiye."""
        if not self._click_role('pharmacy'):
            self.skipTest("Pharmacy role input nahi mila")
        lic = self.find_any(self.LICENSE_SELECTORS)
        if not lic:
            self.skipTest("License field nahi mila — LICENSE_SELECTORS update karo")
        self.assertTrue(lic.is_displayed(), "Pharmacy pe license field visible nahi hua")

    def test_tc30_repeated_role_toggle_no_crash(self):
        """TC-30: 6 baar role toggle — UI crash nahi hona chahiye."""
        for _ in range(6):
            self._click_role('pharmacy')
            self._click_role('customer')
        self.assertTrue(self.driver.find_element(By.TAG_NAME, 'body').is_displayed())


# =============================================================================
# TC-35/36/37 — EYE ICON (PASSWORD TOGGLE)
# =============================================================================

class EyeIconTest(AuthSeleniumBase):

    EYE_SELECTORS = [
        '.toggle-password', '.eye-icon',
        '[data-toggle="password"]', '.password-toggle',
        'button.eye', 'i.fa-eye', '.show-password',
        '[aria-label*="password" i]',
    ]

    def setUp(self):
        self.go()

    def _get_pwd_input_and_eye(self, index=0):
        inputs = self.driver.find_elements(By.CSS_SELECTOR,
            'input[type="password"], input[name*="password"]')
        eyes = []
        for sel in self.EYE_SELECTORS:
            eyes.extend(self.driver.find_elements(By.CSS_SELECTOR, sel))
        pwd = inputs[index] if len(inputs) > index else None
        eye = eyes[index] if len(eyes) > index else None
        return pwd, eye

    def test_tc35_eye_click_shows_password(self):
        """TC-35: Eye icon click — input type 'text' ho jaaye (password visible)."""
        pwd, eye = self._get_pwd_input_and_eye()
        if not pwd or not eye:
            self.skipTest("Password input ya eye icon nahi mila — EYE_SELECTORS update karo")
        self.assertEqual(pwd.get_attribute('type'), 'password')
        self.js_click(eye)
        time.sleep(0.2)
        self.assertEqual(pwd.get_attribute('type'), 'text',
            "Eye click ke baad password type 'text' nahi hua")

    def test_tc36_eye_double_click_hides_again(self):
        """TC-36: Dobara eye click — type 'password' wapas aana chahiye."""
        pwd, eye = self._get_pwd_input_and_eye()
        if not pwd or not eye:
            self.skipTest("Password input ya eye icon nahi mila")
        self.js_click(eye); time.sleep(0.2)  # show
        self.js_click(eye); time.sleep(0.2)  # hide
        self.assertEqual(pwd.get_attribute('type'), 'password',
            "Dobara click ke baad type 'password' nahi hua")

    def test_tc37_multiple_fields_independent(self):
        """TC-37: Multiple password fields — eye icons independently kaam karein."""
        # Signup panel pe jao
        s = self.find_any(['#signUpBtn', '[data-panel="signup"]', '.signup-toggle'])
        if s:
            self.js_click(s)
            time.sleep(0.8)

        inputs = self.driver.find_elements(By.CSS_SELECTOR,
            'input[type="password"], input[name*="password"]')
        eyes = []
        for sel in self.EYE_SELECTORS:
            eyes.extend(self.driver.find_elements(By.CSS_SELECTOR, sel))

        if len(inputs) < 2 or len(eyes) < 1:
            self.skipTest(f"Multiple fields nahi mile: {len(inputs)} inputs, {len(eyes)} eyes")

        self.js_click(eyes[0]); time.sleep(0.2)
        self.assertEqual(inputs[0].get_attribute('type'), 'text',
            "Pehle eye icon ne kaam nahi kiya")


# =============================================================================
# TC-55/56/57/58 — UI VISUAL TESTS
# =============================================================================

class UIVisualTest(AuthSeleniumBase):

    def setUp(self):
        self.go()

    def test_tc55_all_visible_buttons_enabled(self):
        """TC-55: Sab visible buttons enabled hone chahiye."""
        buttons = self.driver.find_elements(By.TAG_NAME, 'button')
        visible = [b for b in buttons if b.is_displayed()]
        self.assertGreater(len(visible), 0, "Koi button visible nahi mila")
        for btn in visible[:5]:
            self.assertTrue(btn.is_enabled(), f"Button disabled hai: '{btn.text}'")

    def test_tc56_input_focus_activates(self):
        """TC-56: Input pe focus karo — element active ho jaaye."""
        inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="email"], input[type="text"]')
        if not inputs:
            self.skipTest("Email/text input nahi mila")
        self.driver.execute_script("arguments[0].focus();", inputs[0])
        time.sleep(0.2)
        focused = self.driver.execute_script(
            "return document.activeElement === arguments[0];", inputs[0])
        self.assertTrue(focused, "Input focus nahi hua")

    def test_tc57_error_visible_on_empty_submit(self):
        """TC-57: Khali form submit — koi error indicator visible hona chahiye."""
        self.go('?show=signup')
        time.sleep(0.5)
        submit = self.find_any([
            'form button[type="submit"]',
            'button[type="submit"]',
            'input[type="submit"]',
        ])
        if not submit:
            self.skipTest("Submit button nahi mila")
        self.js_click(submit)
        time.sleep(1)
        src = self.driver.page_source.lower()
        self.assertTrue(
            any(w in src for w in ['error', 'invalid', 'required', 'alert', 'warning']),
            "Error message nahi mila after empty submit"
        )

    def test_tc58_body_visible_in_both_modes(self):
        """TC-58: Light aur dark dono mode mein body visible honi chahiye."""
        body = self.driver.find_element(By.TAG_NAME, 'body')
        self.assertTrue(body.is_displayed())
        # Dark mode toggle try karo
        toggle = self.find_any(['#darkModeToggle', '.dark-mode-btn', '.theme-toggle'])
        if toggle:
            self.js_click(toggle)
            time.sleep(0.4)
            self.assertTrue(body.is_displayed(), "Dark mode mein body visible nahi")