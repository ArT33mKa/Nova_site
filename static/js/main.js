/* ==============================================
   NOVA KHVYLIA - Main Frontend Logic
   ============================================== */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Core Systems Initialization
    UI.init();
    Cart.init();
    Auth.init();
    Favorites.init();
    Search.init();

    // 2. Page Specific Initialization
    if (document.querySelector('.card-slider')) HeroSlider.init();
    if (document.querySelector('.product-detail-grid')) ProductPage.init();
    if (document.querySelector('.checkout-page-v2')) Checkout.init();
    if (document.querySelector('.profile-page-container')) Profile.init();

    // 3. Global Helpers
    GlobalHelpers.initPhoneMasks();
});

/* ==============================================
   UI CONTROLLER
   ============================================== */
const UI = {
    overlay: document.getElementById('page-overlay'),

    init() {
        this.overlay?.addEventListener('click', () => this.closeAllModals());
        document.addEventListener('click', (e) => {
            if (e.target.closest('.close-modal, .close-modal-white')) {
                const modal = e.target.closest('.modal, .cart-sidebar, .cabinet-sidebar');
                if (modal) this.closeModal(modal);
            }
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeAllModals();
        });
        document.getElementById('open-cabinet-btn')?.addEventListener('click', () => {
            this.openModal(document.getElementById('cabinet-modal'));
        });
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
    },

    toast(message, type = 'success', actionsHtml = '') {
        const existingToast = document.querySelector('.toast-notification');
        if (existingToast) existingToast.remove();

        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        toast.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
            <span>${message}</span>
            ${actionsHtml ? `<div class="toast-actions">${actionsHtml}</div>` : ''}
        `;
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('show'));
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    setLoading(btn, isLoading) {
        if (!btn) return;
        if (isLoading) {
            if (!btn.querySelector('.btn-spinner') && !btn.classList.contains('loading')) {
                btn.dataset.originalContent = btn.innerHTML;
            }
            btn.disabled = true;
            btn.classList.add('loading');
            btn.innerHTML = `<span class="btn-spinner"></span>`;
        } else {
            btn.disabled = false;
            btn.classList.remove('loading');
            if (btn.dataset.originalContent) {
                btn.innerHTML = btn.dataset.originalContent;
            }
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
                <a href="${item.url}" class="cart-item-link">
                    <img src="${item.image}" alt="${item.name}" class="cart-item-img">
                </a>
                <div class="cart-item-info">
                    <h4><a href="${item.url}">${item.name}</a></h4>
                    <div class="price">${item.price.toFixed(2)} ₴</div>
                </div>
                <div class="cart-item-sidebar-controls">
                    <button class="remove-item" title="Видалити">
                        <i class="fas fa-times"></i>
                    </button>
                    <div style="display:flex; gap:5px; align-items:center;">
                        <button class="qty-btn minus">-</button>
                        <input class="quantity-input" type="text" readonly value="${item.quantity}">
                        <button class="qty-btn plus">+</button>
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

        if (document.body.dataset.showCompleteReg === 'true') {
            UI.openModal(this.modal);
            this.showScreen('google-complete');
            this.setupRecaptcha();
        }
    },

    setupRecaptcha() {
        const container = document.getElementById('recaptcha-container');
        if (!container) return;
        container.innerHTML = '';
        if (this.recaptchaVerifier) {
            try { this.recaptchaVerifier.clear(); } catch(e) {}
        }
        this.recaptchaVerifier = new firebase.auth.RecaptchaVerifier('recaptcha-container', {
            'size': 'invisible',
            'callback': () => { }
        });
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
                    throw new Error("Акаунт не знайдено. Будь ласка, натисніть 'Зареєструватись'.");
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

                    const codeInput = document.getElementById('verify_code_input');
                    if(codeInput) codeInput.value = '';
                    document.querySelectorAll('.code-digit').forEach(s => { s.textContent = ''; s.classList.remove('filled'); });
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

                    if (data.status === 'success') {
                        window.location.reload();
                    } else {
                        throw new Error(data.message);
                    }

                } else {
                    const result = await this.confirmationResult.confirm(code);
                    const token = await result.user.getIdToken();

                    const res = await fetch('/api/auth/firebase_verify', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            token,
                            intent: window.authIntent,
                            first_name: window.regData?.first_name,
                            last_name: window.regData?.last_name,
                            password: window.regData?.password
                        })
                    });
                    const data = await res.json();

                    if (data.status === 'success') {
                        window.location.reload();
                    } else {
                        throw new Error(data.message);
                    }
                }
            } catch (err) {
                errorEl.textContent = err.message || "Невірний код";
                errorEl.style.display = 'block';
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
    init() {
        const form = document.getElementById('checkout-form');
        if (!form) return;

        this.setupDeliveryLogic();
        this.setupFormValidation(form);
    },

    setupDeliveryLogic() {
        const radios = document.querySelectorAll('input[name="delivery_method"]');
        const npContainer = document.getElementById('nova-poshta-details');
        const cityInput = document.getElementById('delivery_city');
        const cityList = document.getElementById('city-suggestions');
        const whSelect = document.getElementById('delivery_warehouse');

        if (!cityInput) return;

        radios.forEach(r => r.addEventListener('change', () => {
            const isNP = r.value === 'Нова Пошта';
            npContainer.style.display = isNP ? 'block' : 'none';
            cityInput.required = isNP;
            whSelect.required = isNP;
        }));

        let timer;
        cityInput.addEventListener('input', () => {
            clearTimeout(timer);
            const q = cityInput.value.trim();

            if (q.length < 2) {
                cityList.style.display = 'none';
                return;
            }

            cityList.style.display = 'block';
            cityList.innerHTML = '<div class="suggestion-item" style="color:#888">Пошук...</div>';

            timer = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/np/cities?q=${encodeURIComponent(q)}`);
                    const data = await res.json();

                    if (data.length === 0) {
                        cityList.innerHTML = '<div class="suggestion-item">Нічого не знайдено</div>';
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
                    cityList.innerHTML = '<div class="suggestion-item text-danger">Помилка API</div>';
                }
            }, 400);
        });

        document.addEventListener('click', (e) => {
            if (!cityInput.contains(e.target) && !cityList.contains(e.target)) {
                cityList.style.display = 'none';
            }
        });
    },

    async loadWarehouses(cityRef) {
        const whSelect = document.getElementById('delivery_warehouse');
        whSelect.innerHTML = '<option value="">Завантаження відділень...</option>';
        whSelect.disabled = true;

        try {
            const res = await fetch(`/api/np/warehouses?city_ref=${cityRef}`);
            const data = await res.json();

            whSelect.disabled = false;
            whSelect.innerHTML = '<option value="">-- Оберіть відділення --</option>' +
                data.map(wh => `<option value="${wh}">${wh}</option>`).join('');
        } catch (e) {
            whSelect.innerHTML = '<option value="">Помилка завантаження</option>';
        }
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
        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('.favorite-btn');
            if (btn) {
                e.preventDefault();
                e.stopPropagation();
                this.toggle(btn);
            }
        });

        this.refreshUI();

        document.getElementById('open-favorites-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.renderModal();
            UI.openModal(document.getElementById('favorites-modal'));
        });
    },

    toggle(btn) {
        const id = btn.closest('.product-card').dataset.id;
        let favs = this.get();

        if (favs.includes(id)) {
            favs = favs.filter(i => i !== id);
            btn.classList.remove('active');
            UI.toast('Видалено з обраного');
        } else {
            favs.push(id);
            btn.classList.add('active');
            UI.toast('Додано до обраного');
        }

        localStorage.setItem('favorites', JSON.stringify(favs));
        this.updateBadge(favs.length);
    },

    get() {
        return JSON.parse(localStorage.getItem('favorites') || '[]');
    },

    refreshUI() {
        const favs = this.get();
        this.updateBadge(favs.length);

        favs.forEach(id => {
            const btn = document.querySelector(`.product-card[data-id="${id}"] .favorite-btn`);
            if (btn) btn.classList.add('active');
        });
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

        const favs = this.get();
        if (favs.length === 0) {
            container.innerHTML = '<p class="text-center text-muted p-4">Список порожній</p>';
            return;
        }

        container.innerHTML = '<div class="text-center p-4"><span class="btn-spinner" style="border-color:#333; display:inline-block"></span></div>';

        try {
            const res = await fetch('/get_products_by_ids', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ ids: favs })
            });
            const products = await res.json();

            container.innerHTML = products.map(p => `
                <div class="product-card" data-id="${p.id}" style="box-shadow:none; border:1px solid #eee">
                    <div class="product-image" style="padding-top:0; height:120px; background:none;">
                        <a href="${p.url}"><img src="${p.image}" style="width:100%; height:100%; object-fit:contain"></a>
                        <button class="favorite-btn active" style="top:5px; right:5px; width:30px; height:30px;"><i class="fas fa-heart"></i></button>
                    </div>
                    <div class="product-info" style="padding:10px;">
                        <h4 style="font-size:0.9rem; margin-bottom:5px;"><a href="${p.url}">${p.name}</a></h4>
                        <div class="product-footer" style="margin-bottom:5px;">
                            <div class="price" style="font-size:1rem;">${p.price.toFixed(2)} <small>₴</small></div>
                        </div>
                        <button class="btn btn-sm btn-primary add-to-cart-btn btn-block" data-id="${p.id}">В кошик</button>
                    </div>
                </div>
            `).join('');

            this.refreshUI();
        } catch (e) {
            container.innerHTML = '<p class="text-danger text-center">Помилка завантаження</p>';
        }
    }
};

/* ==============================================
   SEARCH SYSTEM
   ============================================== */
const Search = {
    init() {
        const input = document.getElementById('search-input');
        const popup = document.getElementById('search-suggestions-container');
        const clearBtn = document.getElementById('clear-search-btn');
        if (!input || !popup) return;

        let timer;

        input.addEventListener('input', () => {
            const q = input.value.trim();
            clearBtn.classList.toggle('visible', q.length > 0);
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
                            html += `<a href="${c.url}" class="suggestion-item">
                                <span class="suggestion-icon"><i class="fas fa-folder"></i></span>
                                <span>${c.name}</span>
                            </a>`;
                        });
                        data.products.forEach(p => {
                            html += `<a href="${p.url}" class="suggestion-item">
                                <span class="suggestion-icon"><i class="fas fa-box"></i></span>
                                <div class="suggestion-text-group">
                                    <span style="font-weight:600">${p.name}</span>
                                    <span class="suggestion-sub-text">${p.category}</span>
                                </div>
                            </a>`;
                        });
                    }

                    popup.innerHTML = html;
                    popup.classList.add('active');
                } catch(e) { console.error(e); }
            }, 300);
        });

        clearBtn.addEventListener('click', () => {
            input.value = '';
            clearBtn.classList.remove('visible');
            popup.classList.remove('active');
            input.focus();
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !popup.contains(e.target)) {
                popup.classList.remove('active');
            }
        });
    }
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
        const container = document.querySelector('.products-carousel');
        const nextBtn = document.querySelector('.carousel-next-btn');
        const prevBtn = document.querySelector('.carousel-prev-btn');

        if (track && container && nextBtn && prevBtn) {
            let currentOffset = 0;
            const gap = 20;

            const moveCarousel = (direction) => {
                const card = track.querySelector('.product-card');
                if (!card) return;

                const cardWidth = card.offsetWidth + gap;
                const visibleWidth = container.clientWidth;
                const totalWidth = track.scrollWidth;

                if (direction === 'next') {
                    const maxOffset = totalWidth - visibleWidth;
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

        document.querySelector('.buy-now-btn')?.addEventListener('click', async function() {
            const btn = this;
            const id = document.querySelector('.product-detail-grid').dataset.id;
            if(!id) return;

            UI.setLoading(btn, true);
            try {
                await fetch('/add_to_cart', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ product_id: id })
                });
                window.location.href = "/checkout";
            } catch(e) {
                UI.setLoading(btn, false);
                UI.toast('Помилка', 'error');
            }
        });
    }
};

const Profile = {
    init() {
        const verifyBtn = document.getElementById('update-phone-btn');
        if(verifyBtn) {
            verifyBtn.addEventListener('click', (e) => {
                e.preventDefault();
                UI.openModal(document.getElementById('phone-verify-modal'));
            });
        }
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