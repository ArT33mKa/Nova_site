document.addEventListener('DOMContentLoaded', function() {
    const pageOverlay = document.getElementById('page-overlay');

    if (pageOverlay) {
        pageOverlay.addEventListener('click', closeAllSidebars);
    }

    function closeAllSidebars() {
        document.querySelector('.cart-sidebar.active')?.classList.remove('active');
        document.querySelector('.cabinet-sidebar.active')?.classList.remove('active');
        if (pageOverlay) {
            pageOverlay.classList.remove('active');
            pageOverlay.classList.remove('dark');
        }
    }

    initAuth();
    initHeaderActions(pageOverlay, closeAllSidebars);
    initPhonePromptBanner();
    initContactForm();
    initReviewsPage();
    initHeroSlider();
    initProfileSettingsPhoneLogic();
    initSimilarProductsCarousel();
    initProductDescriptionToggle();
    initOptimizedCartLogic();
    initFavoritesLogic();
    initCabinetModal(pageOverlay, closeAllSidebars);
    initAutoApplyFilters();
    document.querySelectorAll('.js-phone-mask').forEach(input => {
        applyPhoneMaskToInput(input);
        // [ВИПРАВЛЕНО] Примусове форматування при завантаженні, якщо значення вже є
        if (input.value) {
            input.dispatchEvent(new Event('input'));
        }
    });

    initInfiniteScroll();
    initSearchSuggestions();

    updateCartView();
    updateFavoritesUI();
});


function initAuth() {
    const authModal = document.getElementById('auth-modal');
    if (!authModal) return;

    let recaptchaVerifier;
    // [ВИПРАВЛЕНО] Повністю перероблена функція ініціалізації reCAPTCHA
    // Коментар: Ця функція тепер безпечна для повторних викликів. Вона спочатку
    // намагається очистити попередній екземпляр reCAPTCHA, перш ніж створювати новий.
    // Це вирішує поширену помилку "reCAPTCHA container is already rendered".
    const initRecaptcha = () => {
        const container = document.getElementById('recaptcha-container');
        if (!container) return;

        // Якщо верифікатор вже існує, очищуємо його
        if (recaptchaVerifier) {
            try {
                recaptchaVerifier.clear();
            } catch (e) {
                console.warn("Recaptcha clear failed, likely already removed.", e);
            }
        }
        // Також очищуємо сам контейнер про всяк випадок
        container.innerHTML = '';

        // Створюємо новий екземпляр
        recaptchaVerifier = new firebase.auth.RecaptchaVerifier('recaptcha-container', {
          'size': 'invisible',
          'callback': (response) => {} // reCAPTCHA solved
        });
        recaptchaVerifier.render();
    };

    const screens = {
        phone: document.getElementById('auth-screen-phone'),
        register: document.getElementById('auth-screen-register'),
        verify: document.getElementById('auth-screen-verify'),
        emailInput: document.getElementById('auth-screen-email-input'),
        emailVerify: document.getElementById('auth-screen-email-verify'),
    };
    const forms = {
        phone: document.getElementById('phone-form'),
        register: document.getElementById('register-form'),
        verify: document.getElementById('verify-form'),
        emailInput: document.getElementById('email-input-form'),
        emailVerify: document.getElementById('email-verify-form'),
    };
    const errorMessages = {
        phone: document.getElementById('phone-error'),
        register: document.getElementById('register-error'),
        verify: document.getElementById('verify-error'),
        emailInput: document.getElementById('email-input-error'),
        emailVerify: document.getElementById('email-verify-error'),
    };

    const toRegisterLink = document.getElementById('go-to-register');
    const toLoginLink = document.getElementById('go-to-login');
    const toEmailLoginBtn = document.getElementById('go-to-email-login');
    const backToPhoneLink = document.getElementById('back-to-phone-login');

    let intent = 'login';
    let registrationData = {};
    let currentPhone = '';
    let currentEmail = '';
    let confirmationResult = null;

    const showScreen = (screenName) => {
        Object.values(screens).forEach(s => s && s.classList.remove('active'));
        if (screens[screenName]) {
            screens[screenName].classList.add('active');
            if (screenName === 'phone' || screenName === 'register') {
                initRecaptcha(); // Цей виклик тепер безпечний
            }
        }
    };
    const showError = (formName, message, isHtml = false) => {
        if (errorMessages[formName]) {
            errorMessages[formName][isHtml ? 'innerHTML' : 'textContent'] = message;
            errorMessages[formName].style.display = 'block';
        }
    };
    const hideAllErrors = () => Object.values(errorMessages).forEach(el => el && (el.style.display = 'none'));

    document.querySelector('[data-action="open-auth"]')?.addEventListener('click', () => {
        authModal.classList.add('active');
        initRecaptcha();
    });

    authModal.addEventListener('click', e => {
        if (e.target.classList.contains('close-modal') || e.target.id === 'auth-modal') {
            authModal.classList.remove('active');
            setTimeout(() => showScreen('phone'), 300);
        }
    });

    toRegisterLink?.addEventListener('click', (e) => { e.preventDefault(); showScreen('register'); });
    toLoginLink?.addEventListener('click', (e) => { e.preventDefault(); showScreen('phone'); });
    toEmailLoginBtn?.addEventListener('click', (e) => { e.preventDefault(); showScreen('emailInput'); });
    backToPhoneLink?.addEventListener('click', (e) => { e.preventDefault(); showScreen('phone'); });

    authModal.addEventListener('click', e => {
        if (e.target.id === 'error-link-to-register') { e.preventDefault(); showScreen('register'); }
        if (e.target.id === 'error-link-to-login') { e.preventDefault(); showScreen('phone'); }
    });

    setupCodeInput(document.getElementById('verify_code_input'), document.getElementById('verify_code_display'));
    setupCodeInput(document.getElementById('email_verify_code_input'), document.getElementById('email_verify_code_display'));

    forms.phone?.addEventListener('submit', (e) => {
        e.preventDefault();
        hideAllErrors();
        intent = 'login';
        currentPhone = document.getElementById('auth_phone').value;
        const submitBtn = e.target.querySelector('button[type="submit"]');
        submitBtn.disabled = true;

        fetch('/api/auth/check_user_exists', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: currentPhone })
        })
        .then(res => res.json())
        .then(data => {
            if (data.exists) {
                firebase.auth().signInWithPhoneNumber(currentPhone, recaptchaVerifier)
                    .then((result) => {
                        confirmationResult = result;
                        document.getElementById('verify-phone-display').textContent = currentPhone;
                        document.getElementById('verify-title').textContent = 'Вхід в кабінет';
                        showScreen('verify');
                    }).catch((error) => {
                        console.error("Firebase SMS Error:", error);
                        showError('phone', "Не вдалося надіслати SMS. Спробуйте пізніше або оновіть сторінку.");
                        initRecaptcha();
                    }).finally(() => { submitBtn.disabled = false; });
            } else {
                showError('phone', `Користувача не знайдено. <a href="#" id="error-link-to-register">Зареєструватись?</a>`, true);
                submitBtn.disabled = false;
            }
        });
    });

    forms.register?.addEventListener('submit', (e) => {
        e.preventDefault();
        hideAllErrors();
        intent = 'register';

        // [ЗМІНЕНО] Отримуємо та перевіряємо паролі
        const password = document.getElementById('register_password').value;
        const confirmPassword = document.getElementById('register_confirm_password').value;

        if (password.length < 6) {
            showError('register', 'Пароль має бути не менше 6 символів.');
            return;
        }
        if (password !== confirmPassword) {
            showError('register', 'Паролі не співпадають.');
            return;
        }

        currentPhone = document.getElementById('register_phone').value;
        registrationData = {
            first_name: document.getElementById('register_first_name').value,
            last_name: document.getElementById('register_last_name').value,
            password: password // [ДОДАНО] Зберігаємо пароль для відправки на сервер
        };
        const submitBtn = e.target.querySelector('button[type="submit"]');
        submitBtn.disabled = true;

        firebase.auth().signInWithPhoneNumber(currentPhone, recaptchaVerifier)
            .then((result) => {
                confirmationResult = result;
                document.getElementById('verify-phone-display').textContent = currentPhone;
                document.getElementById('verify-title').textContent = 'Завершення реєстрації';
                showScreen('verify');
            }).catch((error) => {
                console.error("Firebase SMS Error:", error);
                if (error.code === 'auth/invalid-phone-number') {
                    showError('register', 'Невірний формат номеру телефону.');
                } else {
                    showError('register', "Не вдалося надіслати SMS. Спробуйте пізніше або оновіть сторінку.");
                }
                initRecaptcha();
            }).finally(() => {
                submitBtn.disabled = false;
            });
    });

    forms.verify?.addEventListener('submit', (e) => {
        e.preventDefault();
        hideAllErrors();
        const code = document.getElementById('verify_code_input').value;
        const submitBtn = e.target.querySelector('button[type="submit"]');
        submitBtn.disabled = true;

        if (!confirmationResult) {
            showError('verify', 'Термін дії сесії минув. Спробуйте знову.');
            submitBtn.disabled = false;
            return;
        }

        confirmationResult.confirm(code).then((result) => {
            return result.user.getIdToken();
        }).then((idToken) => {
            let body = { token: idToken, intent, ...registrationData };
            return fetch('/api/auth/firebase_verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
        }).then(res => res.json()).then(data => {
            if (data.status === 'success') {
                window.location.reload();
            } else {
                showError('verify', data.message || 'Сталася помилка.');
                submitBtn.disabled = false;
            }
        }).catch((error) => {
            console.error('Verification error', error);
            showError('verify', 'Невірний код або помилка сервера.');
            submitBtn.disabled = false;
        });
    });

    forms.emailInput?.addEventListener('submit', e => {
        e.preventDefault();
        hideAllErrors();
        currentEmail = document.getElementById('auth_email').value;
        const submitBtn = e.target.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Надсилаємо...';

        fetch('/api/auth/start_email_login', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: currentEmail})
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById('verify-email-display').textContent = currentEmail;
                showScreen('emailVerify');
            } else {
                showError('emailInput', data.message || 'Сталася помилка');
            }
        }).finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Надіслати код';
        });
    });

    forms.emailVerify?.addEventListener('submit', e => {
        e.preventDefault();
        hideAllErrors();
        const code = document.getElementById('email_verify_code_input').value;
        const submitBtn = e.target.querySelector('button[type="submit"]');
        submitBtn.disabled = true;

        fetch('/api/auth/verify_email_code', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({code: code})
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                window.location.reload();
            } else {
                showError('emailVerify', data.message || 'Сталася помилка');
                submitBtn.disabled = false;
            }
        });
    });
}

function initProfileSettingsPhoneLogic() {
    const container = document.getElementById('phone-settings-container');
    if (!container) return;

    const updateBtn = document.getElementById('update-phone-btn');
    const phoneInput = document.getElementById('settings_phone');
    const errorContainer = document.getElementById('phone-settings-error');

    const modal = document.getElementById('phone-verify-modal');
    const modalForm = document.getElementById('phone-verify-form');
    const modalCodeHiddenInput = document.getElementById('phone_verify_code_input');
    const modalCodeDisplay = document.getElementById('phone_verify_code_display');
    const modalErrorContainer = document.getElementById('phone-verify-error');
    const phoneDisplay = document.getElementById('phone-verify-display');

    let confirmationResult = null;
    let recaptchaVerifier = null;

    const showError = (el, message) => {
        el.textContent = message;
        el.style.display = 'block';
    };
    const hideErrors = () => {
        errorContainer.style.display = 'none';
        modalErrorContainer.style.display = 'none';
    };

    // [ВИПРАВЛЕНО] Аналогічна логіка очищення для сторінки налаштувань
        const initRecaptcha = () => {
        const recaptchaContainer = document.getElementById('recaptcha-container-settings');
        if (!recaptchaContainer) return Promise.reject("Container not found");

        if (recaptchaVerifier) {
            try {
                recaptchaVerifier.clear();
            } catch(e) {
                console.warn("Settings recaptcha clear failed", e);
            }
        }
        recaptchaContainer.innerHTML = '';

        recaptchaVerifier = new firebase.auth.RecaptchaVerifier('recaptcha-container-settings', {
            'size': 'invisible'
        });
        return recaptchaVerifier.render();
    };

    setupCodeInput(modalCodeHiddenInput, modalCodeDisplay);

    updateBtn.addEventListener('click', async () => {
        hideErrors();
        const phoneNumber = phoneInput.value;
        const phoneDigits = phoneNumber.replace(/\D/g, '');

        if (phoneDigits.length !== 12) {
            showError(errorContainer, 'Будь ласка, введіть повний номер телефону.');
            return;
        }

        updateBtn.disabled = true;
        updateBtn.textContent = 'Чекайте...';

        try {
            await initRecaptcha();
            confirmationResult = await firebase.auth().signInWithPhoneNumber(phoneNumber, recaptchaVerifier);
            phoneDisplay.textContent = phoneNumber;
            modalCodeHiddenInput.value = '';
            setupCodeInput(modalCodeHiddenInput, modalCodeDisplay); // Reset display
            modal.classList.add('active');
            setTimeout(() => modalCodeHiddenInput.focus(), 100);
        } catch (error) {
            console.error("Firebase SMS Error:", error);
            showError(errorContainer, "Не вдалося надіслати SMS. Спробуйте пізніше або оновіть сторінку.");
        } finally {
            updateBtn.disabled = false;
            updateBtn.textContent = phoneInput.value.replace(/\D/g, '').length > 0 ? 'Змінити' : 'Додати';
        }
    });

    modalForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideErrors();
        const code = modalCodeHiddenInput.value;
        const submitBtn = modalForm.querySelector('button[type="submit"]');

        if (code.length < 6) {
            showError(modalErrorContainer, 'Код має складатися з 6 цифр.');
            return;
        }

        if (!confirmationResult) {
             showError(modalErrorContainer, 'Термін дії сесії минув. Закрийте вікно та спробуйте знову.');
             return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Перевірка...';

        try {
            const credential = await confirmationResult.confirm(code);
            const idToken = await credential.user.getIdToken();

            const response = await fetch('/api/settings/update_phone', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: idToken })
            });
            const data = await response.json();

            if (response.ok) {
                modal.classList.remove('active');
                showToast(data.message, 'success');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                showError(modalErrorContainer, data.message || 'Сталася помилка.');
            }

        } catch (error) {
            console.error("Code verification error:", error);
            showError(modalErrorContainer, 'Невірний код або помилка сервера.');
        } finally {
             submitBtn.disabled = false;
             submitBtn.textContent = 'Підтвердити номер';
        }
    });

    modal.addEventListener('click', (e) => {
        if (e.target.classList.contains('close-modal') || e.target.id === 'phone-verify-modal') {
            modal.classList.remove('active');
        }
    });
}

function initPhonePromptBanner() {
    const banner = document.getElementById('phone-prompt-banner');
    const closeBtn = document.getElementById('close-phone-prompt');

    if (banner && closeBtn) {
        closeBtn.addEventListener('click', () => {
            banner.style.transition = 'opacity 0.3s, transform 0.3s';
            banner.style.opacity = '0';
            banner.style.transform = 'translateY(-100%)';

            fetch('/api/hide_phone_prompt', { method: 'POST' })
                .catch(err => console.error("Could not hide prompt:", err));

            setTimeout(() => banner.remove(), 300);
        });
    }
}

function setupCodeInput(hiddenInput, displayContainer) {
    if (!hiddenInput || !displayContainer) return;

    const displaySpans = displayContainer.querySelectorAll('span');
    const MAX_DIGITS = 6;

    const updateDisplay = () => {
        const value = hiddenInput.value;
        for (let i = 0; i < MAX_DIGITS; i++) {
            const span = displaySpans[i];
            if (i < value.length) {
                span.textContent = value[i];
                span.classList.add('entered');
            } else {
                span.textContent = '_';
                span.classList.remove('entered');
            }
            span.classList.toggle('cursor', i === value.length && document.activeElement === hiddenInput);
        }
    };

    hiddenInput.addEventListener('input', () => {
        hiddenInput.value = hiddenInput.value.replace(/\D/g, '').substring(0, MAX_DIGITS);
        updateDisplay();
    });

    hiddenInput.addEventListener('focus', () => {
        displayContainer.classList.add('focused');
        updateDisplay();
    });
    hiddenInput.addEventListener('blur', () => {
        displayContainer.classList.remove('focused');
        updateDisplay();
    });

    displayContainer.addEventListener('click', () => hiddenInput.focus());

    updateDisplay();
}

function initCabinetModal(pageOverlay, closeAllSidebars) {
    const cabinetModal = document.getElementById('cabinet-modal');
    const authModal = document.getElementById('auth-modal');
    if (!cabinetModal) return;

    document.getElementById('open-cabinet-btn')?.addEventListener('click', () => {
        cabinetModal.classList.add('active');
        if (pageOverlay) {
            pageOverlay.classList.add('active');
            pageOverlay.classList.add('dark');
        }
    });

    cabinetModal.addEventListener('click', e => {
        if (e.target.classList.contains('cabinet-close') || e.target.id === 'cabinet-modal') {
            closeAllSidebars();
        }
    });

    document.getElementById('cabinet-action-login')?.addEventListener('click', () => {
        closeAllSidebars();
        setTimeout(() => {
            if (authModal) {
                authModal.classList.add('active');
                // Ініціалізуємо reCAPTCHA при відкритті модалки
                const recaptchaContainer = document.getElementById('recaptcha-container');
                if (recaptchaContainer) initAuth();
            }
        }, 300);
    });

    document.querySelectorAll('[data-requires-login="true"]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            closeAllSidebars();
            setTimeout(() => {
                if (authModal) {
                    authModal.classList.add('active');
                    initAuth();
                }
                showToast('Будь ласка, увійдіть, щоб продовжити', 'info');
            }, 300);
        });
    });

    document.getElementById('cabinet-open-favorites')?.addEventListener('click', (e) => {
        e.preventDefault();
        closeAllSidebars();
        setTimeout(() => {
            renderFavoritesModal();
            document.getElementById('favorites-modal')?.classList.add('active');
        }, 300);
    });
}

function initHeaderActions(pageOverlay, closeAllSidebars) {
    const cartModal = document.getElementById('cart-modal');
    if(!cartModal) return;

    document.getElementById('open-cart-btn')?.addEventListener('click', () => {
        updateCartView();
        cartModal.classList.add('active');
        if (pageOverlay) {
            pageOverlay.classList.add('active');
        }
    });

    cartModal.addEventListener('click', e => {
        if (e.target.matches('.close-modal') || e.target.id === 'cart-modal') {
            closeAllSidebars();
        }
    });
}

function initInfiniteScroll() {
    const loadMoreBtn = document.getElementById('load-more-btn');
    const productsGrid = document.getElementById('products-grid-container');

    if (!loadMoreBtn || !productsGrid) return;

    let currentPage = 1;
    let isLoading = false;
    let infiniteScrollEnabled = false;

    const loadMoreProducts = () => {
        if (isLoading) return;
        isLoading = true;
        currentPage++;

        loadMoreBtn.classList.add('loading');

        const params = new URLSearchParams();
        params.set('page', currentPage);
        if (loadMoreBtn.dataset.categorySlug) params.set('category_slug', loadMoreBtn.dataset.categorySlug);
        if (loadMoreBtn.dataset.search) params.set('search', loadMoreBtn.dataset.search);
        if (loadMoreBtn.dataset.minPrice) params.set('min_price', loadMoreBtn.dataset.minPrice);
        if (loadMoreBtn.dataset.maxPrice) params.set('max_price', loadMoreBtn.dataset.maxPrice);

        fetch(`/api/catalog/load_more?${params.toString()}`)
            .then(response => {
                const moreAvailable = response.headers.get('X-More-Available') === 'true';
                if (!moreAvailable) {
                    loadMoreBtn.style.display = 'none';
                    window.removeEventListener('scroll', handleScroll);
                }
                return response.text();
            })
            .then(html => {
                if (html.trim() !== "") {
                    productsGrid.insertAdjacentHTML('beforeend', html);
                    updateCartView();
                }
            })
            .catch(error => console.error('Error loading more products:', error))
            .finally(() => {
                isLoading = false;
                loadMoreBtn.classList.remove('loading');
            });
    };

    const handleScroll = () => {
        if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 500) {
            loadMoreProducts();
        }
    };

    loadMoreBtn.addEventListener('click', () => {
        if (!infiniteScrollEnabled) {
            infiniteScrollEnabled = true;
            window.addEventListener('scroll', handleScroll);
        }
        loadMoreProducts();
    });
}

function initOptimizedCartLogic() {
    let debounceTimer;

    const updateServerQuantity = (productId, quantity) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetch(`/update_cart_quantity/${productId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({quantity: quantity})
            })
            .then(res => res.json())
            .then(data => {
                if(data.status === 'success') {
                    updateCartView();
                }
            });
        }, 500);
    };

    document.body.addEventListener('click', e => {
        const button = e.target.closest('button');
        if (!button) return;

        const productId = button.dataset.id || button.closest('[data-id]')?.dataset.id;
        if (!productId) return;

        if (button.matches('.add-to-cart-btn') && !button.classList.contains('in-cart')) {
             const originalButtonHTML = button.innerHTML;
            setButtonAsInCart(button, true);
            showToast('Товар додано до кошика', 'success', `<a href="/checkout" class="btn btn-sm btn-primary">Оформити</a>`);
            fetch('/add_to_cart', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: productId })})
            .then(res => res.json())
            .then(data => {
                if (data.status !== 'success') {
                    button.classList.remove('in-cart');
                    button.innerHTML = originalButtonHTML;
                    showToast(data.message || 'Помилка додавання товару', 'error');
                }
                updateCartView();
            }).catch(() => {
                button.classList.remove('in-cart');
                button.innerHTML = originalButtonHTML;
                showToast('Мережева помилка', 'error');
                updateCartView();
            });
        }

        if (button.matches('.buy-now-btn')) {
             fetch('/buy_now', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: productId })})
             .then(res => res.json()).then(data => { if(data.status === 'success') window.location.href = '/checkout'; });
        }

        if (button.matches('.qty-btn')) {
            const cartItemRow = button.closest('.cart-item');
            if (!cartItemRow) return;
            const quantityInput = cartItemRow.querySelector('.quantity-input');
            const currentQuantity = parseInt(quantityInput.value);
            const newQuantity = button.classList.contains('plus') ? currentQuantity + 1 : currentQuantity - 1;

            if (newQuantity >= 1) {
                quantityInput.value = newQuantity;
                updateServerQuantity(productId, newQuantity);
            }
        }

        if (button.matches('.remove-item')) {
            const cartItemRow = button.closest('.cart-item');
            if (cartItemRow) {
                cartItemRow.style.transition = 'opacity 0.3s, transform 0.3s';
                cartItemRow.style.opacity = '0';
                cartItemRow.style.transform = 'translateX(50px)';
                setTimeout(() => {
                    fetch(`/remove_from_cart/${productId}`, { method: 'POST' })
                        .then(() => updateCartView());
                }, 300);
            }
        }
    });

    document.body.addEventListener('change', e => {
        if (e.target.matches('.quantity-input')) {
            const input = e.target;
            const productId = input.dataset.id;
            let newQuantity = parseInt(input.value);

            if (isNaN(newQuantity) || newQuantity < 1) {
                newQuantity = 1;
                input.value = newQuantity;
            }

            updateServerQuantity(productId, newQuantity);
        }
    });
}

function setButtonAsInCart(button, isInCart) {
    if (isInCart) {
        button.classList.add('in-cart');
        button.innerHTML = '<i class="fas fa-check"></i> В кошику';
    } else {
        button.classList.remove('in-cart');
        button.innerHTML = 'Додати в кошик';
    }
}

function applyPhoneMaskToInput(phoneInput) {
    if (!phoneInput) return;
    const matrix = "+380 (__) ___-__-__";
    const prefixNumber = "380";
    const setCursorPosition = (pos, elem) => requestAnimationFrame(() => { elem.focus(); elem.setSelectionRange(pos, pos); });
    const applyMask = (value) => {
        let digits = value.replace(/\D/g, "");
        digits = (digits.length < prefixNumber.length) ? prefixNumber : prefixNumber + digits.substring(prefixNumber.length);
        let i = 0;
        let formattedValue = matrix.replace(/[_\d]/g, (char) => (i < digits.length) ? digits.charAt(i++) : char);
        let cursorPos = formattedValue.indexOf('_');
        if (cursorPos === -1) cursorPos = formattedValue.length;
        return { formattedValue, cursorPos };
    };
    phoneInput.addEventListener('input', (e) => {
        const { formattedValue, cursorPos } = applyMask(e.target.value);
        e.target.value = formattedValue;
        setCursorPosition(cursorPos, e.target);
    });
    phoneInput.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace') {
            e.preventDefault();
            let digits = e.target.value.replace(/\D/g, "");
            if (digits.length > prefixNumber.length) {
                const { formattedValue, cursorPos } = applyMask(digits.slice(0, -1));
                e.target.value = formattedValue;
                setCursorPosition(cursorPos, e.target);
            }
        }
    });
    phoneInput.addEventListener('focus', (e) => { const { formattedValue, cursorPos } = applyMask(e.target.value); e.target.value = formattedValue; setCursorPosition(cursorPos, e.target); });
    phoneInput.addEventListener('click', (e) => { const { cursorPos } = applyMask(e.target.value); setCursorPosition(cursorPos, e.target); });
    phoneInput.addEventListener('blur', (e) => { if (e.target.value.replace(/\D/g, "") === prefixNumber) e.target.value = ''; });
}

function initProductDescriptionToggle() {
    const wrapper = document.getElementById('description-wrapper');
    const btn = document.getElementById('toggle-description-btn');
    if (!wrapper || !btn) return;
    if (wrapper.scrollHeight > 125) {
        btn.style.display = 'inline-block';
    } else {
        wrapper.style.maxHeight = 'none';
        wrapper.classList.add('no-fade');
        return;
    }
    btn.addEventListener('click', function() {
        const isExpanded = wrapper.classList.toggle('expanded');
        btn.textContent = isExpanded ? 'Приховати' : 'Читати далі';
    });
}

function updateCartView() {
    fetch('/get_cart', { cache: 'no-cache' })
        .then(res => res.json())
        .then(data => {
            const totalQuantity = data.items.reduce((sum, item) => sum + item.quantity, 0);

            const counter = document.getElementById('cart-count');
            if (counter) {
                counter.textContent = totalQuantity;
            }

            updateAllProductButtonStates(data.items);

            const itemsContainer = document.querySelector('.cart-items-container');
            const totalEl = document.getElementById('cart-modal-total');
            const checkoutLink = document.getElementById('checkout-link');
            if (!itemsContainer || !totalEl || !checkoutLink) return;

            itemsContainer.innerHTML = '';
            if (data.items.length > 0) {
                checkoutLink.style.display = 'block';
                data.items.forEach(item => {
                    const stockClass = item.in_stock ? 'in-stock' : 'out-of-stock';
                    const stockText = item.in_stock ? '✔ В наявності' : '✖ Немає в наявності';
                    itemsContainer.insertAdjacentHTML('beforeend', `
                    <div class="cart-item" data-id="${item.id}">
                        <a href="${item.url}" class="cart-item-link"><img src="${item.image}" alt="${item.name}" class="cart-item-img"></a>
                        <div class="cart-item-info">
                            <a href="${item.url}" class="cart-item-link"><h4>${item.name}</h4></a>
                            <p class="cart-item-price">${item.price.toFixed(2)} ₴</p>
                            <p class="cart-item-stock ${stockClass}">${stockText}</p>
                        </div>
                        <div class="cart-item-sidebar-controls">
                            <div class="cart-item-quantity-controls">
                                <button class="qty-btn minus" data-id="${item.id}" ${item.quantity <= 1 ? 'disabled' : ''}>-</button>
                                <input type="number" class="quantity-input" value="${item.quantity}" data-id="${item.id}" min="1" aria-label="Кількість">
                                <button class="qty-btn plus" data-id="${item.id}">+</button>
                            </div>
                            <button class="remove-item" data-id="${item.id}" title="Видалити"><i class="fas fa-trash-alt"></i></button>
                        </div>
                    </div>`);
                });
            } else {
                checkoutLink.style.display = 'none';
                itemsContainer.innerHTML = '<div class="empty-cart-message"><i class="fas fa-shopping-cart"></i><p>Ваш кошик порожній</p></div>';
            }
            totalEl.textContent = `${data.total.toFixed(2)} ₴`;
        });
}

function updateAllProductButtonStates(cartItems) {
    const cartProductIds = new Set(cartItems.map(item => String(item.id)));
    document.querySelectorAll('.add-to-cart-btn').forEach(button => {
        const productId = button.closest('[data-id]')?.dataset.id;
        if (productId) {
            const isInCart = cartProductIds.has(productId);
            button.classList.toggle('in-cart', isInCart);
            const isLargeButton = button.classList.contains('btn-lg');
            if (isInCart) {
                button.innerHTML = isLargeButton ? '<i class="fas fa-check"></i> Вже в кошику' : '<i class="fas fa-check"></i> В кошику';
            } else {
                button.innerHTML = isLargeButton ? '<i class="fas fa-shopping-cart"></i> В кошик' : 'Додати в кошик';
            }
        }
    });
}

function initFavoritesLogic() {
    document.body.addEventListener('click', e => {
        const favoriteBtn = e.target.closest('.favorite-btn');
        if (favoriteBtn) {
            const productId = favoriteBtn.closest('[data-id]')?.dataset.id;
            if (productId) {
                toggleFavorite(productId);
            }
        }
    });

    document.getElementById('open-favorites-btn')?.addEventListener('click', () => {
        renderFavoritesModal();
        document.getElementById('favorites-modal')?.classList.add('active');
    });

    const favModal = document.getElementById('favorites-modal');
    favModal?.addEventListener('click', e => {
        if (e.target.id === 'favorites-modal' || e.target.classList.contains('close-modal')) {
            favModal.classList.remove('active');
        }
    });
}

function toggleFavorite(productId) {
    let favorites = JSON.parse(localStorage.getItem('favorites')) || [];

    if (favorites.includes(productId)) {
        favorites = favorites.filter(id => id !== productId);
        showToast('Видалено з обраного');
    } else {
        favorites.push(productId);
        showToast('Додано до обраного');
    }

    localStorage.setItem('favorites', JSON.stringify(favorites));
    updateFavoritesUI();
}

function updateFavoritesUI() {
    const favorites = JSON.parse(localStorage.getItem('favorites')) || [];
    const counter = document.getElementById('favorites-count');

    if (counter) {
        counter.textContent = favorites.length;
    }

    document.querySelectorAll('.favorite-btn').forEach(btn => {
        const productId = btn.closest('[data-id]')?.dataset.id;
        if (productId) {
            btn.classList.toggle('active', favorites.includes(productId));
        }
    });
}

function renderFavoritesModal() {
    const container = document.getElementById('favorites-list-container');
    if (!container) return;
    const favoriteIds = JSON.parse(localStorage.getItem('favorites')) || [];
    container.innerHTML = '';
    if (favoriteIds.length === 0) {
        container.innerHTML = '<p class="text-center" style="grid-column: 1 / -1;">Список обраного порожній.</p>';
        return;
    }
    fetch('/get_products_by_ids', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids: favoriteIds })})
    .then(res => res.json()).then(products => {
        products.forEach(p => {
            const stockStatus = p.in_stock ? `<div class="stock-status in-stock">Є в наявності</div>` : `<div class="stock-status out-of-stock">Немає в наявності</div>`;
            let adminActionsHtml = window.isAdmin ? `
            <div class="admin-product-actions">
                <a href="/admin/edit_product/${p.id}" class="admin-action-btn edit-btn" title="Редагувати"><i class="fas fa-pencil-alt"></i></a>
                <form action="/admin/delete_product/${p.id}" method="POST" onsubmit="return confirm('Ви впевнені?');"><button type="submit" class="admin-action-btn delete-btn" title="Видалити"><i class="fas fa-trash-alt"></i></button></form>
            </div>` : '';
            container.insertAdjacentHTML('beforeend', `
            <div class="product-card" data-id="${p.id}">
                <div class="product-image">
                    <a href="${p.url}"><img src="${p.image}" alt="${p.name}"></a>
                    ${stockStatus}
                    <button class="favorite-btn active" title="Видалити з обраного"><i class="far fa-star"></i><i class="fas fa-star"></i></button>
                    ${adminActionsHtml}
                </div>
                <div class="product-info">
                    <h3 class="product-name"><a href="${p.url}">${p.name}</a></h3>
                     <div class="product-footer">
                        <span class="price">${p.price.toFixed(2)} ₴</span>
                    </div>
                    <div class="product-card-actions">
                        <button class="btn add-to-cart-btn" data-id="${p.id}" ${p.in_stock ? '' : 'disabled'}>Додати в кошик</button>
                    </div>
                </div>
            </div>`);
        });
        updateFavoritesUI();
        updateCartView();
    });
}

let activeToast = null;
let toastTimeout = null;

function showToast(message, type = 'success', actions = '') {
    if (activeToast) {
        clearTimeout(toastTimeout);
        activeToast.classList.remove('show');
        setTimeout(() => {
            if (document.body.contains(activeToast)) {
                activeToast.remove();
            }
        }, 500);
    }

    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;
    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    toast.appendChild(messageSpan);
    if (actions) {
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'toast-actions';
        actionsDiv.innerHTML = actions;
        toast.appendChild(actionsDiv);
    }
    document.body.appendChild(toast);

    activeToast = toast;

    setTimeout(() => {
        toast.classList.add('show');
        toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (document.body.contains(toast)) {
                    toast.remove();
                }
                if (activeToast === toast) {
                    activeToast = null;
                }
            }, 500);
        }, 3000);
    }, 10);
}

function initContactForm() {
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.innerHTML;

            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Надсилання...';

            fetch('/send_message', { method: 'POST', body: new FormData(this) })
            .then(response => response.json())
            .then(data => {
                showToast(data.message, data.status === 'success' ? 'success' : 'error');
                if (data.status === 'success') this.reset();
            })
            .catch(() => showToast('Сталася помилка при відправці.', 'error'))
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            });
        });
    }
}

function initReviewsPage() {
    const openModal = modal => modal?.classList.add('active');
    const closeModalOnClick = modal => {
        modal?.addEventListener('click', e => {
            if (e.target.classList.contains('close-modal') || e.target.id === modal.id) modal.classList.remove('active');
        });
    };
    const reviewModal = document.getElementById('review-modal');
    const questionModal = document.getElementById('question-modal');
    const replyModal = document.getElementById('reply-modal');
    document.getElementById('open-review-modal-btn')?.addEventListener('click', () => openModal(reviewModal));
    document.getElementById('open-question-modal-btn')?.addEventListener('click', () => openModal(questionModal));
    document.querySelectorAll('.reply-btn').forEach(button => {
        button.addEventListener('click', function() {
            document.getElementById('reply-parent-id').value = this.dataset.reviewId;
            openModal(replyModal);
        });
    });
    [reviewModal, questionModal, replyModal].forEach(closeModalOnClick);
}

function initHeroSlider() {
    const slider = document.querySelector('.card-slider');
    if (!slider) return;

    const sliderWrapper = document.querySelector('.card-slider-wrapper');
    const slides = Array.from(slider.querySelectorAll('.hero-slide'));
    const prevBtn = document.querySelector('.card-slider-wrapper .prev-btn');
    const nextBtn = document.querySelector('.card-slider-wrapper .next-btn');
    const dotsContainer = document.querySelector('.card-slider-wrapper .slider-dots');

    const totalSlides = slides.length;
    if (totalSlides <= 1) {
        if(prevBtn) prevBtn.style.display = 'none';
        if(nextBtn) nextBtn.style.display = 'none';
        if(dotsContainer) dotsContainer.style.display = 'none';
        return;
    }

    let currentIndex = 0;
    let autoPlayInterval;

    if (dotsContainer) {
        dotsContainer.innerHTML = '';
        slides.forEach((_, i) => {
            const dot = document.createElement('button');
            dot.classList.add('dot');
            dot.addEventListener('click', () => goToSlide(i));
            dotsContainer.appendChild(dot);
        });
    }
    const dots = dotsContainer ? dotsContainer.querySelectorAll('.dot') : [];

    function goToSlide(index) {
        if (index === currentIndex) return;
        clearInterval(autoPlayInterval);
        currentIndex = index;
        updateInitialPositions();
        updateDots();
        startAutoPlay();
    }

    function updateSlider(direction = 'next') {
        clearInterval(autoPlayInterval);

        if (direction === 'next') {
            currentIndex = (currentIndex + 1) % totalSlides;
        } else {
            currentIndex = (currentIndex - 1 + totalSlides) % totalSlides;
        }
        updateInitialPositions();
        updateDots();
        startAutoPlay();
    }

    function updateInitialPositions() {
        slides.forEach(s => s.className = 'hero-slide');
        const leftIndex = (currentIndex - 1 + totalSlides) % totalSlides;
        const rightIndex = (currentIndex + 1) % totalSlides;

        if (totalSlides === 2) {
            slides[currentIndex].classList.add('slide-center');
            slides[rightIndex].classList.add('slide-right');
        } else if (totalSlides >= 3) {
            slides[leftIndex].classList.add('slide-left');
            slides[currentIndex].classList.add('slide-center');
            slides[rightIndex].classList.add('slide-right');
        } else {
            slides[currentIndex].classList.add('slide-center');
        }
    }

    function updateDots() {
        if(dots.length > 0) {
            dots.forEach((dot, i) => dot.classList.toggle('active', i === currentIndex));
        }
    }

    function startAutoPlay() {
        clearInterval(autoPlayInterval);
        autoPlayInterval = setInterval(() => updateSlider('next'), 10000);
    }

    if(nextBtn) nextBtn.addEventListener('click', () => updateSlider('next'));
    if(prevBtn) prevBtn.addEventListener('click', () => updateSlider('prev'));

    if (sliderWrapper) {
        sliderWrapper.addEventListener('mouseenter', () => clearInterval(autoPlayInterval));
        sliderWrapper.addEventListener('mouseleave', () => startAutoPlay());
    }

    updateInitialPositions();
    updateDots();
    startAutoPlay();
}

function initSimilarProductsCarousel() {
    const container = document.querySelector('.similar-products-section');
    if (!container) return;
    const track = container.querySelector('.products-grid-carousel');
    const prevBtn = container.querySelector('.carousel-prev-btn');
    const nextBtn = container.querySelector('.carousel-next-btn');
    if (!track || !prevBtn || !nextBtn || track.children.length <= 4) {
       if(prevBtn) prevBtn.style.display = 'none';
       if(nextBtn) nextBtn.style.display = 'none';
        return;
    }
    let scrollAmount = 0;
    const itemWidth = track.children[0].offsetWidth + 20;
    const maxScroll = track.scrollWidth - track.clientWidth;
    const updateButtons = () => {
        prevBtn.disabled = scrollAmount <= 10;
        nextBtn.disabled = scrollAmount >= maxScroll - 10;
    };
    nextBtn.addEventListener('click', () => {
        scrollAmount = Math.min(scrollAmount + itemWidth, maxScroll);
        track.style.transform = `translateX(-${scrollAmount}px)`;
        updateButtons();
    });
    prevBtn.addEventListener('click', () => {
        scrollAmount = Math.max(scrollAmount - itemWidth, 0);
        track.style.transform = `translateX(-${scrollAmount}px)`;
        updateButtons();
    });
    updateButtons();
}

function initAutoApplyFilters() {
    const filtersForm = document.getElementById('filters-form');
    if (!filtersForm) return;

    const debounce = (func, delay) => {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    };

    const submitForm = () => {
        const searchInput = document.getElementById('search-input');
        if (searchInput && searchInput.value) {
            let hiddenSearch = filtersForm.querySelector('input[name="search"]');
            if (!hiddenSearch) {
                hiddenSearch = document.createElement('input');
                hiddenSearch.type = 'hidden';
                hiddenSearch.name = 'search';
                filtersForm.appendChild(hiddenSearch);
            }
            hiddenSearch.value = searchInput.value;
        }
        filtersForm.submit();
    };

    const debouncedSubmit = debounce(submitForm, 800);

    filtersForm.addEventListener('change', (e) => {
        if (e.target.type === 'checkbox') {
            submitForm();
        }
    });

    filtersForm.addEventListener('keyup', (e) => {
        if (e.target.type === 'number') {
            debouncedSubmit();
        }
    });
}

function initSearchSuggestions() {
    const searchInput = document.getElementById('search-input');
    const suggestionsContainer = document.getElementById('search-suggestions-container');
    const searchWrapper = searchInput ? searchInput.closest('.search-input-wrapper') : null;
    const clearButton = document.getElementById('clear-search-btn');

    if (!searchInput || !suggestionsContainer || !searchWrapper || !clearButton) return;

    let searchTimeout;

    const toggleClearButton = () => {
        clearButton.classList.toggle('visible', searchInput.value.length > 0);
    };

    const showSuggestions = () => {
        suggestionsContainer.classList.add('active');
        searchWrapper.classList.add('suggestions-active');
    };

    const hideSuggestions = () => {
        suggestionsContainer.classList.remove('active');
        searchWrapper.classList.remove('suggestions-active');
    };

    const getSearchHistory = () => JSON.parse(localStorage.getItem('searchHistory')) || [];

    const addToSearchHistory = (term) => {
        if (!term) return;
        let history = getSearchHistory();
        history = history.filter(item => item !== term);
        history.unshift(term);
        localStorage.setItem('searchHistory', JSON.stringify(history.slice(0, 5)));
    };

    const renderInitialState = () => {
        const history = getSearchHistory();
        let html = `
            <div class="suggestions-header">
                <h4 class="suggestions-main-title">Пошук товарів</h4>
                <button class="suggestions-close-btn" title="Закрити">&times;</button>
            </div>
            <div class="search-suggestions-body">`;

        if (history.length > 0) {
            html += `
                <div class="suggestions-section">
                    <div class="suggestions-section-header">
                        <h4 class="suggestions-section-title">Історія пошуку</h4>
                        <button class="clear-history-btn">Очистити все</button>
                    </div>
                    ${history.map(term => `
                        <div class="suggestion-item">
                            <a href="/catalog?search=${encodeURIComponent(term)}" class="suggestion-item-link">
                                <span class="suggestion-icon"><i class="fas fa-history"></i></span>
                                <span class="suggestion-text">${term}</span>
                            </a>
                            <button class="remove-history-btn" data-term="${term}" title="Видалити">&times;</button>
                        </div>
                    `).join('')}
                </div>`;
        }

        html += '</div>';
        suggestionsContainer.innerHTML = html;

        fetch('/api/popular_searches')
            .then(res => res.json())
            .then(popular => {
                if (popular && popular.length > 0) {
                    const popularHtml = `
                        <div class="suggestions-section">
                            <div class="suggestions-section-header">
                                <h4 class="suggestions-section-title">Популярні запити</h4>
                            </div>
                            <div class="popular-searches">
                                ${popular.map(cat => `<a href="/catalog/${cat.slug}">${cat.name}</a>`).join('')}
                            </div>
                        </div>`;
                    suggestionsContainer.querySelector('.search-suggestions-body').insertAdjacentHTML('beforeend', popularHtml);
                }
            });

        showSuggestions();
    };

    const renderResults = (data) => {
        let html = `
            <div class="suggestions-header">
                 <h4 class="suggestions-main-title">Результати пошуку</h4>
                 <button class="suggestions-close-btn" title="Закрити">&times;</button>
            </div>
            <div class="search-suggestions-body">`;

        if (data.categories.length > 0) {
            html += `
                <div class="suggestions-section">
                    <h4 class="suggestions-section-title">Категорії</h4>
                    ${data.categories.map(c => `
                         <a href="${c.url}" class="suggestion-item">
                            <span class="suggestion-icon"><i class="fas fa-list"></i></span>
                            <span class="suggestion-text">${c.name}</span>
                          </a>`).join('')}
                </div>`;
        }

        if (data.products.length > 0) {
            html += `
                <div class="suggestions-section">
                    <h4 class="suggestions-section-title">Товари</h4>
                    ${data.products.map(p => `
                        <a href="${p.url}" class="suggestion-item">
                            <span class="suggestion-icon"><i class="fas fa-box-open"></i></span>
                            <div class="suggestion-text-group">
                                <span class="suggestion-main-text">${p.name}</span>
                                ${p.category ? `<span class="suggestion-sub-text">в категорії: ${p.category}</span>` : ''}
                            </div>
                        </a>`).join('')}
                </div>`;
        }

        if (html.endsWith('<div class="search-suggestions-body">')) {
            html += `<p style="text-align: center; color: var(--gray-color); padding: 20px 0;">За вашим запитом нічого не знайдено</p>`;
        }

        html += '</div>';
        suggestionsContainer.innerHTML = html;
        showSuggestions();
    };

    searchInput.addEventListener('focus', () => {
        if (searchInput.value.length < 2) {
            renderInitialState();
        }
    });

    searchInput.addEventListener('input', () => {
        const query = searchInput.value.trim();
        clearTimeout(searchTimeout);
        toggleClearButton();
        if (query.length < 2) {
            renderInitialState();
            return;
        }
        searchTimeout = setTimeout(() => {
            fetch(`/api/search_suggestions?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => renderResults(data));
        }, 250);
    });

    if(searchInput.form) {
        searchInput.form.addEventListener('submit', () => {
            addToSearchHistory(searchInput.value.trim());
        });
    }

    clearButton.addEventListener('click', () => {
        searchInput.value = '';
        toggleClearButton();
        searchInput.focus();
        renderInitialState();
    });

    suggestionsContainer.addEventListener('click', (e) => {
        const clearBtn = e.target.closest('.clear-history-btn');
        const removeBtn = e.target.closest('.remove-history-btn');
        const closeBtn = e.target.closest('.suggestions-close-btn');

        if (clearBtn) {
            e.preventDefault();
            localStorage.removeItem('searchHistory');
            renderInitialState();
        }
        if (removeBtn) {
            e.preventDefault();
            const termToRemove = removeBtn.dataset.term;
            let history = getSearchHistory();
            history = history.filter(item => item !== termToRemove);
            localStorage.setItem('searchHistory', JSON.stringify(history));
            removeBtn.closest('.suggestion-item').remove();
        }
        if (closeBtn) {
            e.preventDefault();
            hideSuggestions();
        }
    });

    toggleClearButton();
}