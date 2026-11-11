// --- Tab and Content Management ---
        const signInTab = document.getElementById('signInTab');
        const registerTab = document.getElementById('registerTab');
        const signInContent = document.getElementById('signInContent');
        const registerContent = document.getElementById('registerContent');
        const switchToSignInLink = document.getElementById('switchToSignInLink');
        const switchToRegisterLink = document.getElementById('switchToRegisterLink');

        function showContent(tabToShow) {
            if (tabToShow === 'register') {
                registerTab.classList.add('tab-active');
                registerTab.classList.remove('tab-inactive');
                signInTab.classList.remove('tab-active');
                signInTab.classList.add('tab-inactive');
                registerContent.classList.remove('hidden');
                signInContent.classList.add('hidden');
            } else {
                signInTab.classList.add('tab-active');
                signInTab.classList.remove('tab-inactive');
                registerTab.classList.remove('tab-active');
                registerTab.classList.add('tab-inactive');
                signInContent.classList.remove('hidden');
                registerContent.classList.add('hidden');
            }
        }

        // --- Event Listeners ---
        registerTab.addEventListener('click', () => showContent('register'));
        signInTab.addEventListener('click', () => showContent('signIn'));
        switchToSignInLink.addEventListener('click', () => showContent('signIn'));
        switchToRegisterLink.addEventListener('click', () => showContent('register'));

        // Initialize to show register content on load
        showContent('register');
    