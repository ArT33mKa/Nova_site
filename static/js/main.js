/* ==============================================
   NOVA KHVULIA - Main Frontend Logic
   ============================================== */

document.addEventListener('DOMContentLoaded', () => {
    UI.init();
    Cart.init();
    Auth.init();
    Favorites.init();
    Search.init();
    Reviews.init();
    UserTracker.init();

    if (document.querySelector('.card-slider')) HeroSlider.init();
    if (document.querySelector('.product-detail-grid')) ProductPage.init();
    if (document.querySelector('.checkout-page-v2')) Checkout.init();
    if (document.querySelector('.profile-page-container')) Profile.init();

    GlobalHelpers.initPhoneMasks();
});

/* ==============================================
   UI CONTROLLER
   ============================================== */
const UI = {
    overlay: document.getElementById('page-overlay'),

    init() {
        this.initToasts();
        this.overlay?.addEventListener('click', () => this.closeAllModals());

        document.addEventListener('click', (e) => {
            if (e.target.closest('.close-modal, .close-modal-white')) {
                const modal = e.target.closest('.modal, .cart-sidebar, .cabinet-sidebar');
                if (modal) this.closeModal(modal);
            }
        });

        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('mousedown', (e) => {
                if (e.target === modal) this.closeModal(modal);
            });
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeAllModals();
        });

        document.getElementById('open-cabinet-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.openModal(document.getElementById('cabinet-modal'));
        });
    },

    initToasts() {
        if (!document.querySelector('.toast-container')) {
            const container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
    },

    toast(message, type = 'success') {
        const container = document.querySelector('.toast-container') || document.body;
        let icon = 'fa-check-circle';
        if (type === 'error') icon = 'fa-times-circle';
        if (type === 'warning') icon = 'fa-exclamation-triangle';
        if (type === 'info') icon = 'fa-info-circle';

        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        toast.innerHTML = `<i class="fas ${icon}"></i> <span>${message}</span>`;

        if (container.classList.contains('toast-container')) {
            container.appendChild(toast);
        } else {
            toast.style.position = 'fixed'; toast.style.bottom = '20px'; toast.style.right = '20px';
            document.body.appendChild(toast);
        }

        requestAnimationFrame(() => toast.classList.add('show'));
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    },

    setLoading(btn, isLoading) {
        if (!btn) return;
        if (isLoading) {
            btn.style.width = `${btn.offsetWidth}px`;
            if (!btn.dataset.originalHtml) btn.dataset.originalHtml = btn.innerHTML;
            btn.classList.add('loading');
            const spinner = document.createElement('span');
            spinner.className = 'btn-spinner';
            btn.appendChild(spinner);
        } else {
            btn.classList.remove('loading');
            btn.style.width = '';
            const spinner = btn.querySelector('.btn-spinner');
            if (spinner) spinner.remove();
        }
    },

    openModal(modal) {
        if (!modal) return;
        this.closeAllModals(false);
        modal.classList.add('active');
        this.overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    },

    closeModal(modal) {
        if (!modal) return;
        modal.classList.remove('active');
        if (!document.querySelector('.modal.active, .cart-sidebar.active, .cabinet-sidebar.active')) {
            this.overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    },

    closeAllModals(removeOverlay = true) {
        document.querySelectorAll('.modal.active, .cart-sidebar.active, .cabinet-sidebar.active').forEach(el => {
            el.classList.remove('active');
        });
        if (removeOverlay) {
            this.overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    }
};

/* ==============================================
   CART SYSTEM
   ============================================== */
const Cart = {
    sidebar: document.getElementById('cart-modal'),
    container: document.querySelector('.cart-items-container'),
    badge: document.getElementById('cart-count'),
    totalEl: document.getElementById('cart-modal-total'),
    debounceTimer: null,

    init() {
        document.getElementById('open-cart-btn')?.addEventListener('click', () => {
            this.fetchCart();
            UI.openModal(this.sidebar);
        });

        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('.add-to-cart-btn');
            if (btn && !btn.disabled && !btn.classList.contains('in-cart')) {
                this.addItem(btn);
            }
        });

        if (this.container) {
            this.container.addEventListener('click', (e) => {
                const target = e.target;
                const row = target.closest('.cart-item');
                if (!row) return;
                const id = row.dataset.id;

                if (target.closest('.remove-item')) {
                    this.removeItem(id, row);
                } else if (target.classList.contains('qty-btn')) {
                    const input = row.querySelector('.quantity-input');
                    let val = parseInt(input.value);
                    if (target.classList.contains('plus')) val++;
                    if (target.classList.contains('minus') && val > 1) val--;

                    input.value = val;
                    this.updateQuantityDebounced(id, val);
                }
            });

            this.container.addEventListener('change', (e) => {
                if (e.target.classList.contains('quantity-input')) {
                    const row = e.target.closest('.cart-item');
                    const id = row.dataset.id;
                    let val = parseInt(e.target.value);

                    if (isNaN(val) || val < 1) {
                        val = 1;
                        e.target.value = 1;
                    }

                    this.updateQuantityDebounced(id, val);
                }
            });
        }
        this.fetchCart(false);
    },

    async addItem(btn) {
        const productId = btn.dataset.id;
        const originalContent = btn.innerHTML;
        btn.classList.add('in-cart');
        btn.innerHTML = `<i class="fas fa-check"></i> <span class="btn-text-desktop">В кошику</span>`;

        try {
            const res = await fetch('/add_to_cart', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ product_id: productId })
            });
            const data = await res.json();

            if (data.status === 'success') {
                this.updateBadge(data.cart_count);
                UI.toast('Товар додано до кошика');
            } else {
                throw new Error(data.message);
            }
        } catch (err) {
            console.error(err);
            UI.toast('Помилка додавання товару', 'error');
            btn.classList.remove('in-cart');
            btn.innerHTML = originalContent;
        }
    },

    async removeItem(id, rowElement) {
        rowElement.style.opacity = '0.5';
        rowElement.style.pointerEvents = 'none';

        try {
            await fetch(`/remove_from_cart/${id}`, { method: 'POST' });
            this.fetchCart();
        } catch (err) {
            UI.toast('Не вдалося видалити товар', 'error');
            rowElement.style.opacity = '1';
            rowElement.style.pointerEvents = 'all';
        }
    },

    updateQuantityDebounced(id, quantity) {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(async () => {
            try {
                await fetch(`/update_cart_quantity/${id}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ quantity })
                });
                this.fetchCart();
            } catch (err) {
                console.error(err);
            }
        }, 500);
    },

    async fetchCart(render = true) {
        try {
            const res = await fetch('/get_cart');
            const data = await res.json();
            const totalQty = data.items.reduce((acc, item) => acc + item.quantity, 0);
            this.updateBadge(totalQty);

            if (render && this.container) {
                this.renderSidebar(data);
            }
        } catch (err) {
            console.error("Cart fetch error:", err);
        }
    },

    renderSidebar(data) {
        if (data.items.length === 0) {
            this.container.innerHTML = `
                <div class="text-center" style="padding: 40px; color: var(--text-tertiary);">
                    <i class="fas fa-shopping-basket" style="font-size: 3rem; margin-bottom: 15px;"></i>
                    <p>Ваш кошик порожній</p>
                    <button onclick="UI.closeAllModals()" class="btn btn-sm btn-outline mt-3">Перейти до покупок</button>
                </div>`;
            this.totalEl.textContent = '0.00 ₴';
            document.getElementById('checkout-link').style.display = 'none';
            return;
        }

        document.getElementById('checkout-link').style.display = 'block';
        this.totalEl.textContent = `${data.total.toFixed(2)} ₴`;

        this.container.innerHTML = data.items.map(item => `
            <div class="cart-item" data-id="${item.id}">
                <div class="cart-item-left">
                    <a href="${item.url}">
                        <img src="${item.image}" alt="${item.name}" onerror="this.onerror=null;this.src='https://placehold.co/400x400/f8fafc/94a3b8?text=No+Image';">
                    </a>
                </div>

                <div class="cart-item-right">
                    <div class="cart-item-top">
                        <a href="${item.url}" class="cart-item-title">${item.name}</a>
                        <button class="remove-item" title="Видалити">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <div class="cart-item-bottom">
                        <div class="cart-item-price">${item.price.toFixed(2)} ₴</div>
                        <div class="qty-control-sm">
                            <button class="qty-btn minus">-</button>
                            <input class="quantity-input" type="number" min="1" value="${item.quantity}">
                            <button class="qty-btn plus">+</button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    },

    updateBadge(count) {
        if (this.badge) {
            this.badge.textContent = count;
            this.badge.style.display = count > 0 ? 'flex' : 'none';
        }
    }
};

/* ==============================================
   AUTH SYSTEM
   ============================================== */
const Auth = {
    modal: document.getElementById('auth-modal'),
    recaptchaVerifier: null,
    confirmationResult: null,
    authMethod: 'phone',

    init() {
        if (!this.modal) return;

        document.querySelectorAll('[data-trigger="auth"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                UI.closeAllModals(false);
                UI.openModal(this.modal);
                this.showScreen('phone');
                this.setupRecaptcha();
            });
        });

        this.setupPhoneLogin();
        this.setupEmailFlow();
        this.setupVerification();
        this.setupRegistration();
        this.setupGoogleCompletion();

        const codeInput = document.getElementById('verify_code_input');
        const codeDisplay = document.getElementById('verify_code_display');
        if (codeInput && codeDisplay) GlobalHelpers.setupCodeInput(codeInput, codeDisplay);
    },

    setupRecaptcha() {
        const container = document.getElementById('recaptcha-container');
        if (!container) return;

        if (this.recaptchaVerifier) {
            try { this.recaptchaVerifier.clear(); } catch(e) {}
            this.recaptchaVerifier = null;
        }
        container.innerHTML = '';

        try {
            this.recaptchaVerifier = new firebase.auth.RecaptchaVerifier('recaptcha-container', {
                'size': 'invisible',
                'callback': () => { console.log("Recaptcha solved"); },
                'expired-callback': () => {
                    console.log("Recaptcha expired");
                    if(this.recaptchaVerifier) { try { this.recaptchaVerifier.clear(); } catch(e){} }
                }
            });
        } catch (e) {
            console.error("Критична помилка ініціалізації Recaptcha:", e);
            container.innerHTML = '';
        }
    },

    showScreen(id) {
        document.querySelectorAll('.auth-screen').forEach(s => s.classList.remove('active'));
        const target = document.getElementById(`auth-screen-${id}`);
        if(target) target.classList.add('active');
        document.querySelectorAll('.text-danger').forEach(el => el.style.display = 'none');
    },

    setupPhoneLogin() {
        const form = document.getElementById('phone-form');
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button');
            const phone = document.getElementById('auth_phone').value;
            const errorEl = document.getElementById('phone-error');

            UI.setLoading(btn, true);
            errorEl.style.display = 'none';

            try {
                const checkRes = await fetch('/api/auth/check_user_exists', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ phone })
                });
                const checkData = await checkRes.json();

                if (!checkData.exists) {
                    throw new Error("Акаунт не знайдено. Будь ласка, натисніть 'Зареєструватись' знизу.");
                }

                this.setupRecaptcha();
                this.confirmationResult = await firebase.auth().signInWithPhoneNumber(phone, this.recaptchaVerifier);

                document.getElementById('verify-dest-display').textContent = phone;
                this.authMethod = 'phone';
                window.authIntent = 'login';
                this.showScreen('verify');

            } catch (err) {
                console.error(err);
                errorEl.textContent = err.message || "Помилка відправки СМС.";
                errorEl.style.display = 'block';
                this.setupRecaptcha();
            } finally {
                UI.setLoading(btn, false);
            }
        });
    },

    setupRegistration() {
        const form = document.getElementById('register-form');
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button');
            const errorEl = document.getElementById('register-error');

            const phone = document.getElementById('register_phone').value;
            const email = document.getElementById('register_email').value;
            const pass = document.getElementById('register_password').value;
            const confirm = document.getElementById('register_confirm_password').value;

            if (pass !== confirm) {
                errorEl.textContent = "Паролі не співпадають";
                errorEl.style.display = 'block';
                return;
            }

            window.regData = {
                first_name: document.getElementById('register_first_name').value,
                last_name: document.getElementById('register_last_name').value,
                email: email,
                password: pass
            };

            UI.setLoading(btn, true);
            errorEl.style.display = 'none';

            try {
                const checkRes = await fetch('/api/auth/check_user_exists', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ phone })
                });
                const checkData = await checkRes.json();

                if (checkData.exists) {
                    throw new Error("Цей номер вже зареєстровано. Спробуйте увійти.");
                }

                this.setupRecaptcha();
                this.confirmationResult = await firebase.auth().signInWithPhoneNumber(phone, this.recaptchaVerifier);

                document.getElementById('verify-dest-display').textContent = phone;
                this.authMethod = 'phone';
                window.authIntent = 'register';

                this.showScreen('verify');
            } catch (err) {
                console.error(err);
                let msg = err.message || "Помилка. Спробуйте пізніше.";
                if (err.code === 'auth/invalid-phone-number') msg = "Невірний формат телефону";
                errorEl.textContent = msg;
                errorEl.style.display = 'block';
                this.setupRecaptcha();
            } finally {
                UI.setLoading(btn, false);
            }
        });
    },

    setupVerification() {
        const form = document.getElementById('verify-form');
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button');
            const code = document.getElementById('verify_code_input').value;
            const errorEl = document.getElementById('verify-error');

            if (code.length < 6) {
                errorEl.textContent = "Введіть повний код (6 цифр)";
                errorEl.style.display = 'block';
                return;
            }

            UI.setLoading(btn, true);
            errorEl.style.display = 'none';

            try {
                if (this.authMethod === 'email') {
                    const res = await fetch('/api/auth/verify_email_code', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ code })
                    });
                    const data = await res.json();
                    if(data.status !== 'success') throw new Error(data.message);
                    window.location.reload();
                } else {
                    const result = await this.confirmationResult.confirm(code);
                    const token = await result.user.getIdToken();

                    const res = await fetch('/api/auth/firebase_verify', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            token: token,
                            intent: window.authIntent,
                            first_name: window.regData?.first_name,
                            last_name: window.regData?.last_name,
                            email: window.regData?.email,
                            password: window.regData?.password
                        })
                    });
                    const data = await res.json();

                    if (data.status === 'success') {
                        window.regData = null;
                        if (window.nextRedirectUrl) window.location.href = window.nextRedirectUrl;
                        else window.location.reload();
                    } else {
                        throw new Error(data.message);
                    }
                }
            } catch (err) {
                errorEl.textContent = err.message || "Невірний код або помилка сервера";
                errorEl.style.display = 'block';
            } finally {
                UI.setLoading(btn, false);
            }
        });
    },

    setupEmailFlow() {
        const form = document.getElementById('email-input-form');
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button');
            const email = document.getElementById('auth_email').value;

            let errorEl = form.querySelector('.text-danger');
            if(!errorEl) {
                errorEl = document.createElement('div');
                errorEl.className = 'text-danger text-center mb-3';
                errorEl.style.display = 'none';
                form.insertBefore(errorEl, btn);
            }

            UI.setLoading(btn, true);
            errorEl.style.display = 'none';

            try {
                const res = await fetch('/api/auth/start_email_login', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email })
                });
                const data = await res.json();

                if (data.status === 'success') {
                    document.getElementById('verify-dest-display').textContent = email;
                    this.authMethod = 'email';
                    this.showScreen('verify');
                } else {
                    throw new Error(data.message);
                }
            } catch(e) {
                errorEl.textContent = e.message || 'Помилка сервера';
                errorEl.style.display = 'block';
            } finally {
                UI.setLoading(btn, false);
            }
        });
    },

    setupGoogleCompletion() {
        const phoneForm = document.getElementById('google-phone-form');
        const finalizeForm = document.getElementById('google-finalize-form');

        phoneForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('google-send-sms-btn');
            const phone = document.getElementById('google_complete_phone').value;
            const errorEl = document.getElementById('google-phone-error');

            UI.setLoading(btn, true);
            errorEl.style.display = 'none';

            try {
                const checkRes = await fetch('/api/auth/check_user_exists', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ phone })
                });
                const checkData = await checkRes.json();

                if (checkData.exists) {
                    throw new Error("Цей номер вже використовується іншим акаунтом.");
                }

                this.setupRecaptcha();
                this.confirmationResult = await firebase.auth().signInWithPhoneNumber(phone, this.recaptchaVerifier);

                phoneForm.style.display = 'none';
                finalizeForm.style.display = 'block';
                setTimeout(() => document.getElementById('google_verify_code').focus(), 100);

            } catch (err) {
                console.error(err);
                errorEl.textContent = err.message || "Помилка відправки СМС";
                errorEl.style.display = 'block';
                this.setupRecaptcha();
            } finally {
                UI.setLoading(btn, false);
            }
        });

        finalizeForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = finalizeForm.querySelector('button[type="submit"]');
            const code = document.getElementById('google_verify_code').value;
            const password = document.getElementById('google_new_password').value;
            const errorEl = document.getElementById('google-finalize-error');

            if(password.length < 6) {
                errorEl.textContent = "Пароль має бути не менше 6 символів";
                errorEl.style.display = 'block';
                return;
            }

            UI.setLoading(btn, true);
            errorEl.style.display = 'none';

            try {
                const result = await this.confirmationResult.confirm(code);
                const firebaseToken = await result.user.getIdToken();

                const res = await fetch('/api/auth/finalize_google', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        firebase_token: firebaseToken,
                        password: password
                    })
                });

                const data = await res.json();

                if (data.status === 'success') {
                    window.location.href = "/";
                } else {
                    throw new Error(data.message);
                }

            } catch (err) {
                errorEl.textContent = err.message || "Невірний код або помилка сервера";
                errorEl.style.display = 'block';
            } finally {
                UI.setLoading(btn, false);
            }
        });
    }
};

/* ==============================================
   CHECKOUT SYSTEM
   ============================================== */
const Checkout = {
    cachedWarehouses: [],

    init() {
        const form = document.getElementById('checkout-form');
        if (!form) return;

        this.setupDeliveryLogic();
        this.setupFormValidation(form);
    },

    setupDeliveryLogic() {
        const cityInput = document.getElementById('delivery_city');
        const cityList = document.getElementById('city-suggestions');
        const whInput = document.getElementById('delivery_warehouse');
        const whList = document.getElementById('warehouse-suggestions');

        if (!cityInput || !whInput) return;

        let timer;
        cityInput.addEventListener('input', () => {
            clearTimeout(timer);
            const q = cityInput.value.trim();

            whInput.value = '';
            whInput.disabled = true;
            whInput.placeholder = "Спочатку оберіть місто";
            this.cachedWarehouses = [];

            if (q.length < 2) {
                cityList.style.display = 'none';
                return;
            }

            timer = setTimeout(async () => {
                cityList.style.display = 'block';
                cityList.innerHTML = '<div class="suggestion-loading"><i class="fas fa-spinner fa-spin"></i> Пошук...</div>';

                try {
                    const res = await fetch(`/api/np/cities?q=${encodeURIComponent(q)}`);
                    const data = await res.json();

                    if (data.length === 0) {
                        cityList.innerHTML = '<div class="suggestion-item text-muted">Місто не знайдено</div>';
                        return;
                    }

                    cityList.innerHTML = data.map(c =>
                        `<div class="suggestion-item" data-ref="${c.ref}">${c.name}</div>`
                    ).join('');

                    cityList.querySelectorAll('.suggestion-item').forEach(item => {
                        item.addEventListener('click', () => {
                            cityInput.value = item.textContent;
                            cityList.style.display = 'none';
                            this.loadWarehouses(item.dataset.ref);
                        });
                    });

                } catch (e) {
                    cityList.innerHTML = '<div class="suggestion-item text-danger">Помилка з\'єднання</div>';
                }
            }, 400);
        });

        whInput.addEventListener('input', () => {
            const q = whInput.value.toLowerCase();
            if(!this.cachedWarehouses.length) return;

            whList.style.display = 'block';
            const filtered = this.cachedWarehouses.filter(w => w.toLowerCase().includes(q));
            this.renderWarehouseList(filtered.slice(0, 50));
        });

        whInput.addEventListener('focus', () => {
            if(this.cachedWarehouses.length > 0) {
                whList.style.display = 'block';
                const q = whInput.value.toLowerCase();
                const filtered = q ? this.cachedWarehouses.filter(w => w.toLowerCase().includes(q)) : this.cachedWarehouses;
                this.renderWarehouseList(filtered.slice(0, 50));
            }
        });

        document.addEventListener('click', (e) => {
            if (!cityInput.contains(e.target) && !cityList.contains(e.target)) {
                cityList.style.display = 'none';
            }
            if (!whInput.contains(e.target) && !whList.contains(e.target)) {
                whList.style.display = 'none';
            }
        });
    },

    async loadWarehouses(cityRef) {
        const whInput = document.getElementById('delivery_warehouse');
        whInput.value = '';
        whInput.placeholder = "Завантаження...";
        whInput.disabled = true;

        try {
            const res = await fetch(`/api/np/warehouses?city_ref=${cityRef}`);
            const data = await res.json();
            this.cachedWarehouses = data;

            if (data.length === 0) {
                whInput.placeholder = "У цьому місті немає відділень";
            } else {
                whInput.disabled = false;
                whInput.placeholder = "Оберіть відділення або введіть номер";
                whInput.focus();
            }
        } catch (e) {
            whInput.placeholder = "Помилка завантаження";
        }
    },

    renderWarehouseList(items) {
        const whList = document.getElementById('warehouse-suggestions');
        const whInput = document.getElementById('delivery_warehouse');

        if (items.length === 0) {
            whList.innerHTML = '<div class="suggestion-item text-muted">Нічого не знайдено</div>';
            return;
        }

        whList.innerHTML = items.map(w =>
            `<div class="suggestion-item warehouse-item">${w}</div>`
        ).join('');

        whList.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                whInput.value = item.textContent;
                whList.style.display = 'none';
            });
        });
    },

    setupFormValidation(form) {
        const submitBtn = form.querySelector('button[type="submit"]');
        const phoneInput = document.getElementById('customer_phone');

        form.addEventListener('submit', (e) => {
            const digits = phoneInput.value.replace(/\D/g, '');
            if (digits.length !== 12) {
                e.preventDefault();
                UI.toast('Введіть коректний номер телефону (+380...)', 'error');
                phoneInput.focus();
                return;
            }
            UI.setLoading(submitBtn, true);
        });
    }
};

/* ==============================================
   FAVORITES SYSTEM
   ============================================== */
const Favorites = {
    init() {
        this.isAuth = document.body.classList.contains('user-logged-in');

        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('.favorite-btn');
            if (btn) {
                e.preventDefault();
                e.stopPropagation();
                this.toggle(btn);
            }
        });

        if (this.isAuth) {
            this.syncInitialState();
        }

        document.getElementById('open-favorites-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.renderModal();
            UI.openModal(document.getElementById('favorites-modal'));
        });
    },

    async syncInitialState() {
        try {
            const res = await fetch('/api/favorites/list');
            const data = await res.json();
            const ids = data.ids || [];

            this.updateBadge(ids.length);
            ids.forEach(id => {
                const btn = document.querySelector(`.product-card[data-id="${id}"] .favorite-btn`);
                if (btn) btn.classList.add('active');
            });
        } catch (e) { console.error(e); }
    },

    async toggle(btn) {
        const isUserLoggedIn = document.body.classList.contains('user-logged-in');

        if (!isUserLoggedIn) {
            UI.toast('Увійдіть або зареєструйтесь, щоб зберігати товари', 'info');
            UI.openModal(document.getElementById('auth-modal'));
            return;
        }

        const card = btn.closest('.product-card');
        const id = card.dataset.id;
        const wasActive = btn.classList.contains('active');
        btn.classList.toggle('active');

        try {
            const res = await fetch('/api/favorites/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ product_id: id })
            });
            const data = await res.json();

            if (data.status === 'success') {
                this.updateBadge(data.count);
                UI.toast(data.action === 'added' ? 'Додано до обраного' : 'Видалено з обраного');

                document.querySelectorAll(`.product-card[data-id="${id}"] .favorite-btn`).forEach(b => {
                    if (data.action === 'added') b.classList.add('active');
                    else b.classList.remove('active');
                });

                if (data.action === 'removed' && card.classList.contains('fav-modal-card')) {
                    card.remove();
                    if (data.count === 0) this.renderModal();
                }

            } else {
                throw new Error('Server error');
            }
        } catch (err) {
            btn.classList.toggle('active', wasActive);
            UI.toast('Помилка з\'єднання', 'error');
        }
    },

    updateBadge(count) {
        const badge = document.getElementById('favorites-count');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
    },

    async renderModal() {
        const container = document.getElementById('favorites-list-container');
        if (!container) return;

        const isUserLoggedIn = document.body.classList.contains('user-logged-in');
        if (!isUserLoggedIn) {
            container.innerHTML = `
                <div class="empty-favs">
                    <i class="fas fa-lock"></i>
                    <p>Увійдіть, щоб переглянути обране</p>
                    <button onclick="UI.openModal(document.getElementById('auth-modal'))" class="btn btn-primary">Увійти</button>
                </div>`;
            return;
        }

        container.innerHTML = '<div class="text-center p-4"><span class="btn-spinner" style="border-color:var(--color-brand-primary); display:inline-block"></span></div>';

        try {
            const res = await fetch('/api/favorites/render');
            const products = await res.json();

            if (products.length === 0) {
                container.innerHTML = `
                    <div class="empty-favs">
                        <i class="far fa-heart"></i>
                        <p>Список порожній</p>
                        <button onclick="UI.closeAllModals()" class="btn btn-sm btn-primary">До каталогу</button>
                    </div>`;
                return;
            }

            container.innerHTML = products.map(p => `
                <div class="product-card fav-modal-card" data-id="${p.id}">
                    <div class="product-image">
                        <a href="${p.url}">
                            <img src="${p.image}" alt="${p.name}"
                                 onerror="this.onerror=null;this.src='https://placehold.co/400x400/f8fafc/94a3b8?text=No+Image';">
                        </a>
                        ${!p.in_stock ? '<div class="stock-status out-of-stock" style="font-size:0.6rem; padding:4px;">Закінчився</div>' : ''}
                        <button class="favorite-btn active" title="Видалити з обраного">
                            <i class="fas fa-heart"></i>
                        </button>
                    </div>
                    <div class="product-info">
                        <h4><a href="${p.url}">${p.name}</a></h4>
                        <div class="product-footer">
                            <div class="price">${p.price.toFixed(2)} <small>₴</small></div>
                        </div>
                        ${p.in_stock
                            ? `<button class="btn btn-sm btn-primary add-to-cart-btn btn-block" data-id="${p.id}"><i class="fas fa-shopping-basket"></i></button>`
                            : `<button class="btn btn-sm btn-block" disabled style="background:#f1f5f9; color:#94a3b8; cursor:not-allowed;"><i class="fas fa-ban"></i></button>`
                        }
                    </div>
                </div>
            `).join('');
        } catch (e) {
            container.innerHTML = '<p class="text-danger text-center">Помилка завантаження</p>';
        }
    },
};

/* ==============================================
   PAGE SPECIFIC LOGIC
   ============================================== */
const HeroSlider = {
    init() {
        const slides = document.querySelectorAll('.hero-slide');
        if (slides.length < 2) {
            if(slides[0]) slides[0].classList.add('active');
            return;
        }

        let current = 0;
        const showSlide = (idx) => {
            slides.forEach(s => s.classList.remove('active'));
            slides[idx].classList.add('active');
        };

        const next = () => { current = (current + 1) % slides.length; showSlide(current); };
        const prev = () => { current = (current - 1 + slides.length) % slides.length; showSlide(current); };

        document.querySelector('.next-btn')?.addEventListener('click', next);
        document.querySelector('.prev-btn')?.addEventListener('click', prev);

        setInterval(next, 6000);
        showSlide(0);
    }
};

const ProductPage = {
    init() {
        const descWrapper = document.getElementById('description-wrapper');
        const descBtn = document.getElementById('toggle-description-btn');
        if (descWrapper && descWrapper.scrollHeight > 120) {
            descBtn.style.display = 'inline-block';
            descBtn.addEventListener('click', () => {
                const expanded = descWrapper.classList.toggle('expanded');
                descBtn.textContent = expanded ? 'Згорнути' : 'Читати далі';
            });
        } else if (descWrapper) {
            descWrapper.classList.add('no-fade');
        }

        const track = document.querySelector('.products-grid-carousel');
        const nextBtn = document.querySelector('.carousel-next-btn');
        const prevBtn = document.querySelector('.carousel-prev-btn');

        if (track && nextBtn && prevBtn) {
            let currentOffset = 0;
            const gap = 20;
            const moveCarousel = (direction) => {
                const card = track.querySelector('.product-card');
                if (!card) return;
                const cardWidth = card.offsetWidth + gap;
                const containerWidth = track.parentElement.clientWidth;
                const totalWidth = track.scrollWidth;

                if (direction === 'next') {
                    const maxOffset = totalWidth - containerWidth;
                    if (currentOffset < maxOffset) {
                        currentOffset = Math.min(currentOffset + cardWidth, maxOffset);
                    }
                } else {
                    if (currentOffset > 0) {
                        currentOffset = Math.max(currentOffset - cardWidth, 0);
                    }
                }
                track.style.transform = `translateX(-${currentOffset}px)`;
            };
            nextBtn.addEventListener('click', () => moveCarousel('next'));
            prevBtn.addEventListener('click', () => moveCarousel('prev'));
        }

        const buyNowBtn = document.querySelector('.buy-now-btn');
        if (buyNowBtn) {
            buyNowBtn.addEventListener('click', function() {
                const id = this.dataset.id;
                if(!id) return;
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                this.style.pointerEvents = 'none';
                window.location.href = `/checkout?buy_now_id=${id}`;
            });
        }
    }
};

const Profile = {
    init() {
        document.body.addEventListener('click', (e) => {
            const link = e.target.closest('a[href*="/profile/orders"]');
            const isUserLoggedIn = document.body.classList.contains('user-logged-in');

            if (link && !isUserLoggedIn) {
                e.preventDefault();
                e.stopPropagation();
                UI.closeModal(document.getElementById('cabinet-modal'));
                UI.toast('Увійдіть, щоб переглянути історію замовлень', 'info');
                UI.openModal(document.getElementById('auth-modal'));
            }
        });
    }
};

const Search = {
    init() {
        const input = document.getElementById('search-input');
        const popup = document.getElementById('search-suggestions-container');
        const clearBtn = document.getElementById('clear-search-btn');
        const form = input ? input.closest('form') : null;

        if (!input || !popup) return;

        if (clearBtn && input.value.trim().length > 0) {
            clearBtn.classList.add('visible');
        }

        input.addEventListener('focus', () => {
            if (input.value.trim().length >= 2) {
                input.dispatchEvent(new Event('input'));
            }
        });

        input.addEventListener('input', () => {
            const val = input.value.trim();
            if (clearBtn) clearBtn.classList.toggle('visible', val.length > 0);

            const filterForm = document.getElementById('filter-form');
            if (filterForm) {
                let hiddenInput = filterForm.querySelector('input[name="search"]');
                if (val === '') {
                    if (hiddenInput) hiddenInput.remove();
                } else {
                    if (!hiddenInput) {
                        hiddenInput = document.createElement('input');
                        hiddenInput.type = 'hidden';
                        hiddenInput.name = 'search';
                        filterForm.appendChild(hiddenInput);
                    }
                    hiddenInput.value = val;
                }
            }
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                const url = new URL(window.location.href);
                url.searchParams.delete('search');
                window.location.href = url.toString();
            });
        }

        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const q = input.value.trim();
                if (!q) {
                    const url = new URL(window.location.href);
                    url.searchParams.delete('search');
                    window.location.href = url.toString();
                    return;
                }
                window.location.href = `/catalog?search=${encodeURIComponent(q)}`;
            });
        }

        let timer;
        input.addEventListener('input', () => {
            const q = input.value.trim();
            clearTimeout(timer);
            if (q.length < 2) {
                popup.classList.remove('active');
                return;
            }
            timer = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/search_suggestions?q=${encodeURIComponent(q)}`);
                    const data = await res.json();
                    let html = `<div class="suggestions-header"><h4>Результати</h4></div>`;
                    if (data.products.length === 0 && data.categories.length === 0) {
                        html += `<div style="padding:20px; text-align:center; color:#94a3b8">Нічого не знайдено</div>`;
                    } else {
                        data.categories.forEach(c => {
                            html += `<a href="${c.url}" class="suggestion-item"><span class="suggestion-icon"><i class="fas fa-folder"></i></span><span>${c.name}</span></a>`;
                        });
                        data.products.forEach(p => {
                            html += `<a href="${p.url}" class="suggestion-item">
                                <span class="suggestion-icon"><i class="fas fa-box"></i></span>
                                <div class="suggestion-text-group"><span style="font-weight:600">${p.name}</span><span class="suggestion-sub-text">${p.category}</span></div>
                            </a>`;
                        });
                    }
                    popup.innerHTML = html;
                    popup.classList.add('active');
                } catch(e) { console.error(e); }
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !popup.contains(e.target)) {
                popup.classList.remove('active');
            }
        });
    }
};

/* ==============================================
   GLOBAL HELPERS
   ============================================== */
const GlobalHelpers = {
    initPhoneMasks() {
        document.querySelectorAll('.js-phone-mask').forEach(input => {
            this.applyPhoneMask(input);
            if(input.value) input.dispatchEvent(new Event('input'));
        });
    },

    applyPhoneMask(input) {
        if (window.IMask) {
            try {
                const maskOptions = {
                    mask: '+{380} (00) 000-00-00',
                    lazy: false,
                    placeholderChar: '_'
                };
                const mask = IMask(input, maskOptions);

                input.addEventListener('blur', () => {
                    if (mask.unmaskedValue === '') {
                        mask.value = '';
                    }
                });
            } catch (e) {
                console.error("IMask init error:", e);
            }
        } else {
            const prefix = "+380";
            input.addEventListener('input', (e) => {
                let value = input.value.replace(/\D/g, "");
                if (value.startsWith("380")) value = value.substring(3);

                let x = value.match(/(\d{0,2})(\d{0,3})(\d{0,2})(\d{0,2})/);
                input.value = !x[2] ? prefix + " (" + x[1] : prefix + " (" + x[1] + ") " + x[2] + (x[3] ? "-" + x[3] : "") + (x[4] ? "-" + x[4] : "");
            });
        }
    },

    setupCodeInput(hiddenInput, displayContainer) {
        if (!hiddenInput) return;

        const updateDisplay = () => {
            const val = hiddenInput.value;
            const spans = displayContainer.querySelectorAll('.code-digit');

            spans.forEach((span, idx) => {
                const char = val[idx] || '';
                span.textContent = char;

                if (char) {
                    span.classList.add('filled');
                    span.classList.remove('active');
                } else {
                    span.classList.remove('filled');
                }

                if (document.activeElement === hiddenInput) {
                    if (idx === val.length) {
                        span.classList.add('active');
                    } else {
                        span.classList.remove('active');
                    }
                } else {
                    span.classList.remove('active');
                }
            });
        };

        hiddenInput.addEventListener('input', () => {
            hiddenInput.value = hiddenInput.value.replace(/\D/g, '').substring(0, 6);
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

        displayContainer.addEventListener('click', () => {
            hiddenInput.focus();
        });
    }
};

const Reviews = {
    init() {
        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('.vote-btn');
            if (btn) this.handleVote(btn);
        });
    },

    async handleVote(btn) {
        const isUserLoggedIn = document.body.classList.contains('user-logged-in');
        if (!isUserLoggedIn) {
            UI.toast('Увійдіть, щоб оцінювати відгуки', 'info');
            UI.openModal(document.getElementById('auth-modal'));
            return;
        }

        const reviewId = btn.dataset.id;
        const value = parseInt(btn.dataset.value);
        const container = btn.closest('.review-votes');

        btn.style.transform = 'scale(1.2)';
        setTimeout(() => btn.style.transform = 'scale(1)', 200);

        try {
            const res = await fetch('/api/reviews/vote', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ review_id: reviewId, value: value })
            });
            const data = await res.json();

            if (data.status === 'success') {
                container.querySelector('.likes-count').textContent = data.likes;
                container.querySelector('.dislikes-count').textContent = data.dislikes;

                const likeBtn = container.querySelector('.vote-btn[data-value="1"]');
                const dislikeBtn = container.querySelector('.vote-btn[data-value="-1"]');

                likeBtn.classList.remove('active');
                dislikeBtn.classList.remove('active');

                if (data.action !== 'removed') {
                    if (value === 1) likeBtn.classList.add('active');
                    else dislikeBtn.classList.add('active');
                }
            }
        } catch (e) {
            console.error(e);
            UI.toast('Помилка з\'єднання', 'error');
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const filterBtn = document.getElementById('mobile-filter-trigger');
    const sidebar = document.querySelector('.filters-sidebar');
    const overlay = document.getElementById('filter-overlay');

    if (filterBtn && sidebar && overlay) {
        const toggleFilters = () => {
            const isActive = sidebar.classList.toggle('active');
            overlay.classList.toggle('active');
            document.body.style.overflow = isActive ? 'hidden' : '';
        };

        filterBtn.addEventListener('click', toggleFilters);
        overlay.addEventListener('click', toggleFilters);

        const applyBtn = sidebar.querySelector('button[type="submit"]');
        if(applyBtn) applyBtn.addEventListener('click', toggleFilters);
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const minPriceInput = document.querySelector('input[name="min_price"]');
    const maxPriceInput = document.querySelector('input[name="max_price"]');
    const filterForm = document.getElementById('filter-form');

    function fixPrices() {
        if (minPriceInput && maxPriceInput) {
            let min = parseFloat(minPriceInput.value);
            let max = parseFloat(maxPriceInput.value);

            if (!isNaN(min) && !isNaN(max) && min > max) {
                minPriceInput.value = max;
                maxPriceInput.value = min;
            }
        }
    }

    if (minPriceInput) minPriceInput.addEventListener('blur', fixPrices);
    if (maxPriceInput) maxPriceInput.addEventListener('blur', fixPrices);

    if (filterForm) {
        filterForm.addEventListener('submit', () => {
            fixPrices();
        });
    }
});

const getCsrfToken = () => {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
};

const UserTracker = {
    storageKey: 'user_interests',
    timer: null,

    init() {
        const catalogPage = document.querySelector('.catalog-page');
        const productPage = document.querySelector('.product-detail-grid');

        if (catalogPage) {
            const category = catalogPage.dataset.categorySlug;
            if (category && category !== 'all') {
                this.addScore(category, 1);
            }
        }

        if (productPage) {
            const category = productPage.dataset.categorySlug;
            if (category) {
                this.timer = setTimeout(() => {
                    this.addScore(category, 3);
                }, 10000);
            }

            const addBtn = productPage.querySelector('.add-to-cart-btn');
            if (addBtn) {
                addBtn.addEventListener('click', () => {
                    this.addScore(category, 10);
                });
            }
        }

        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('.add-to-cart-btn');
            if (btn && btn.closest('.product-card')) {
                const card = btn.closest('.product-card');
                const catText = card.querySelector('.product-info > div > div:first-child')?.textContent.trim();
                if (catText) {
                    const slug = catText.toLowerCase().replace(/\s+/g, '-').replace(/\//g, '');
                    this.addScore(slug, 10);
                }
            }
        });

        this.syncToCookie();
    },

    addScore(category, points) {
        if (!category) return;
        let data = JSON.parse(localStorage.getItem(this.storageKey) || '{}');

        const now = Date.now();
        if (data.last_updated && (now - data.last_updated > 604800000)) data = {};

        if (!data.interests) data.interests = {};
        if (!data.interests[category]) data.interests[category] = 0;

        data.interests[category] += points;
        data.last_updated = now;
        localStorage.setItem(this.storageKey, JSON.stringify(data));

        this.syncToCookie();
    },

    getTopInterest() {
        const data = JSON.parse(localStorage.getItem(this.storageKey) || '{}');
        if (!data.interests) return null;
        const sorted = Object.keys(data.interests).sort((a, b) => data.interests[b] - data.interests[a]);
        return sorted.length > 0 ? sorted[0] : null;
    },

    syncToCookie() {
        const topCat = this.getTopInterest();
        if (!topCat) return;

        const currentCookie = document.cookie.split('; ').find(row => row.startsWith('user_top_interest='));
        const currentValue = currentCookie ? currentCookie.split('=')[1] : null;

        if (topCat !== currentValue) {
            const d = new Date();
            d.setTime(d.getTime() + (7 * 24 * 60 * 60 * 1000));
            document.cookie = `user_top_interest=${topCat};expires=${d.toUTCString()};path=/`;
        }
    }
};

const originalFetch = window.fetch;
window.fetch = async (url, options = {}) => {
    const urlString = url.toString();
    const isInternal = urlString.startsWith('/') || urlString.includes(window.location.origin);

    if (isInternal && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method?.toUpperCase())) {
        if (!options.headers) {
            options.headers = {};
        }
        if (options.headers instanceof Headers) {
            options.headers.append('X-CSRFToken', getCsrfToken());
        } else {
            options.headers['X-CSRFToken'] = getCsrfToken();
        }
    }
    return originalFetch(url, options);
};

function openReplyModal(parentId, redirectTo = '', productId = null) {
    const modal = document.getElementById('reply-modal');
    const inputId = document.getElementById('reply-parent-id');
    const form = modal.querySelector('form');

    if(modal && inputId) {
        inputId.value = parentId;

        let redirectInput = form.querySelector('input[name="redirect_to"]');
        if (!redirectInput) {
            redirectInput = document.createElement('input');
            redirectInput.type = 'hidden';
            redirectInput.name = 'redirect_to';
            form.appendChild(redirectInput);
        }
        redirectInput.value = redirectTo || window.location.href;

        if (productId) {
            form.action = `/product/${productId}/add_review`;
        }

        UI.openModal(modal);
    }
}