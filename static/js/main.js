/* ==============================================
   NOVA KHVULIA - Main Frontend Logic (локальна версія: каталог, кошик, пошук)
   ============================================== */

document.addEventListener('DOMContentLoaded', () => {
    UI.init();
    Cart.init();
    Search.init();
    UserTracker.init();

    if (document.querySelector('.card-slider')) HeroSlider.init();
    if (document.querySelector('.product-detail-grid')) ProductPage.init();
    if (document.querySelector('.checkout-page-v2')) Checkout.init();

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
            if (!btn || btn.disabled) return;
            if (btn.classList.contains('in-cart')) {
                // Товар уже в кошику -> відкриваємо сайдбар кошика
                this.fetchCart();
                UI.openModal(this.sidebar);
            } else {
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

    syncCardButtons(idSet) {
        document.querySelectorAll('.add-to-cart-btn[data-id]').forEach(btn => {
            if (btn.disabled) return;
            const inCart = idSet.has(String(btn.dataset.id));
            if (inCart && !btn.classList.contains('in-cart')) {
                btn.classList.add('in-cart');
                btn.innerHTML = `<i class="fas fa-check"></i> <span class="btn-text">В кошику</span>`;
            } else if (!inCart && btn.classList.contains('in-cart')) {
                btn.classList.remove('in-cart');
                btn.innerHTML = `<i class="fas fa-shopping-cart"></i> <span class="btn-text">В кошик</span>`;
            }
        });
    },

    async fetchCart(render = true) {
        try {
            const res = await fetch('/get_cart');
            const data = await res.json();
            const totalQty = data.items.reduce((acc, item) => acc + item.quantity, 0);
            this.updateBadge(totalQty);
            this.syncCardButtons(new Set(data.items.map(i => String(i.id))));

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
   CHECKOUT SYSTEM (локальний — місто/відділення вводяться вручну)
   ============================================== */
const Checkout = {
    subtotal: 0,

    init() {
        const form = document.getElementById('checkout-form');
        if (!form) return;

        const tokenField = document.getElementById('csrf_token_field');
        if (tokenField) tokenField.value = getCsrfToken() || '';

        form.setAttribute('action', '/checkout' + window.location.search);

        this.setupSummary();
        this.setupDeliveryToggle();
        this.setupFormValidation(form);
    },

    async setupSummary() {
        const list = document.getElementById('checkout-items-list');
        if (!list) return;
        try {
            const res = await fetch('/api/checkout_summary' + window.location.search);
            const data = await res.json();
            this.subtotal = data.subtotal || 0;
            this.renderSummary(data.items || []);
        } catch (e) {
            list.innerHTML = '<p class="text-danger text-center">Не вдалося завантажити кошик</p>';
        }
    },

    renderSummary(items) {
        const list = document.getElementById('checkout-items-list');
        if (!list) return;

        if (!items.length) {
            list.innerHTML = '<p class="text-muted text-center" style="padding:15px;">Кошик порожній</p>';
        } else {
            list.innerHTML = items.map(item => `
                <div class="summary-item">
                    <img src="${item.image}" alt="${item.name}" onerror="this.onerror=null;this.src='https://placehold.co/400x400/f8fafc/94a3b8?text=No+Image';">
                    <div class="summary-item-details">
                        <div class="name">${item.name}</div>
                        <div class="price">${item.price.toFixed(2)} ₴ x ${item.quantity}</div>
                    </div>
                    <div style="font-weight: 600;">${item.line_total.toFixed(2)} ₴</div>
                </div>
            `).join('');
        }

        const subEl = document.getElementById('summary-subtotal');
        const grandEl = document.getElementById('summary-grand-total');
        if (subEl) subEl.textContent = `${this.subtotal.toFixed(2)} ₴`;
        if (grandEl) grandEl.textContent = `${this.subtotal.toFixed(2)} ₴`;
        this.updateDeliveryUI();
    },

    setupDeliveryToggle() {
        const npBlock = document.getElementById('nova-poshta-details');
        document.querySelectorAll('input[name="delivery_method"]').forEach(radio => {
            radio.addEventListener('change', () => {
                if (npBlock) npBlock.style.display = (radio.value === 'Нова Пошта' && radio.checked) ? 'block' : 'none';
                this.updateDeliveryUI();
            });
        });
    },

    updateDeliveryUI() {
        const deliveryEl = document.getElementById('summary-delivery');
        if (!deliveryEl) return;
        const selected = document.querySelector('input[name="delivery_method"]:checked');
        if (!selected) { deliveryEl.textContent = '—'; return; }
        deliveryEl.textContent = (selected.value === 'Нова Пошта')
            ? 'За тарифами перевізника'
            : 'Безкоштовно';
    },

    setupFormValidation(form) {
        const submitBtn = form.querySelector('button[type="submit"]');
        const phoneInput = document.getElementById('customer_phone');
        const firstNameInput = document.getElementById('customer_first_name');

        const showError = (input, msg) => {
            if (!input) return;
            input.classList.add('input-error');
            const err = document.querySelector(`.field-error[data-error-for="${input.id}"]`);
            if (err) { err.textContent = msg; err.style.display = 'block'; }
        };
        const clearError = (input) => {
            if (!input) return;
            input.classList.remove('input-error');
            const err = document.querySelector(`.field-error[data-error-for="${input.id}"]`);
            if (err) { err.textContent = ''; err.style.display = 'none'; }
        };

        form.querySelectorAll('input, select, textarea').forEach(el => {
            el.addEventListener('input', () => clearError(el));
            el.addEventListener('change', () => clearError(el));
        });

        form.addEventListener('submit', (e) => {
            let valid = true;
            let firstInvalid = null;

            if (!firstNameInput || !firstNameInput.value.trim()) {
                showError(firstNameInput, "Вкажіть ім'я");
                valid = false; firstInvalid = firstInvalid || firstNameInput;
            }

            const digits = (phoneInput.value || '').replace(/\D/g, '');
            if (digits.length !== 12) {
                showError(phoneInput, 'Введіть коректний номер (+380...)');
                valid = false; firstInvalid = firstInvalid || phoneInput;
            }

            const method = document.querySelector('input[name="delivery_method"]:checked');
            if (!method) {
                UI.toast('Оберіть спосіб доставки', 'error');
                valid = false;
            } else if (method.value === 'Нова Пошта') {
                const cityInput = document.getElementById('delivery_city');
                const whInput = document.getElementById('delivery_warehouse');
                if (cityInput && !cityInput.value.trim()) {
                    showError(cityInput, 'Вкажіть місто');
                    valid = false; firstInvalid = firstInvalid || cityInput;
                }
                if (whInput && !whInput.value.trim()) {
                    showError(whInput, 'Вкажіть відділення');
                    valid = false; firstInvalid = firstInvalid || whInput;
                }
            }

            if (!valid) {
                e.preventDefault();
                if (firstInvalid) firstInvalid.focus();
                UI.toast('Перевірте правильність заповнення полів', 'error');
                return;
            }
            UI.setLoading(submitBtn, true);
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

/* ==============================================
   CATALOG ENHANCEMENTS (price slider, reset, pagination)
   ============================================== */
document.addEventListener('DOMContentLoaded', () => {
    const filterForm = document.getElementById('filter-form');
    if (!filterForm) return;

    const minInput = filterForm.querySelector('input[name=min_price]');
    const maxInput = filterForm.querySelector('input[name=max_price]');

    if (minInput && maxInput) {
        const FLOOR = 0, CEIL = 100000, STEP = 50;
        const num = (v, def) => { const n = parseFloat(v); return isNaN(n) ? def : n; };
        const clamp = (v) => Math.min(Math.max(v, num(rMin.min, FLOOR)), num(rMax.max, CEIL));

        const wrap = document.createElement('div');
        wrap.className = 'price-slider';
        wrap.innerHTML = `<div class='price-slider-track'><div class='price-slider-range'></div></div><input type='range' class='price-range-min' min='${FLOOR}' max='${CEIL}' step='${STEP}'><input type='range' class='price-range-max' min='${FLOOR}' max='${CEIL}' step='${STEP}'>`;
        const container = minInput.closest('.price-filter-container');
        if (container) container.parentNode.insertBefore(wrap, container.nextSibling);

        const rMin = wrap.querySelector('.price-range-min');
        const rMax = wrap.querySelector('.price-range-max');
        const fill = wrap.querySelector('.price-slider-range');

        const THUMB = 20; // ширина повзунка (px), синхронізовано з CSS
        const paint = () => {
            const floor = num(rMin.min, FLOOR), ceil = num(rMax.max, CEIL);
            const span = (ceil - floor) || 1;
            let pLo = (num(rMin.value, floor) - floor) / span;
            let pHi = (num(rMax.value, ceil) - floor) / span;
            pLo = Math.min(Math.max(pLo, 0), 1);
            pHi = Math.min(Math.max(pHi, 0), 1);
            fill.style.left = 'calc(' + (pLo * 100) + '% + ' + ((0.5 - pLo) * THUMB) + 'px)';
            fill.style.right = 'calc(' + ((1 - pHi) * 100) + '% - ' + ((0.5 - pHi) * THUMB) + 'px)';
        };
        wrap.__repaint = paint;

        rMin.value = clamp(num(minInput.value, FLOOR));
        rMax.value = clamp(num(maxInput.value, CEIL));
        paint();

        rMin.addEventListener('input', () => {
            const floor = num(rMin.min, FLOOR), ceil = num(rMax.max, CEIL);
            let lo = num(rMin.value, floor), hi = num(rMax.value, ceil);
            if (lo > hi - STEP) { lo = hi - STEP; rMin.value = lo; }
            minInput.value = lo > floor ? lo : '';
            paint();
        });
        rMax.addEventListener('input', () => {
            const floor = num(rMin.min, FLOOR), ceil = num(rMax.max, CEIL);
            let lo = num(rMin.value, floor), hi = num(rMax.value, ceil);
            if (hi < lo + STEP) { hi = lo + STEP; rMax.value = hi; }
            maxInput.value = hi < ceil ? hi : '';
            paint();
        });
        minInput.addEventListener('input', () => { rMin.value = clamp(num(minInput.value, FLOOR)); paint(); });
        maxInput.addEventListener('input', () => { rMax.value = clamp(num(maxInput.value, CEIL)); paint(); });
    }

    if (!filterForm.querySelector('.reset-filters-btn')) {
        const resetBtn = document.createElement('a');
        resetBtn.href = window.location.pathname;
        resetBtn.className = 'btn reset-filters-btn btn-block';
        resetBtn.innerHTML = `<i class='fas fa-rotate-left'></i> Скинути фільтри`;
        filterForm.appendChild(resetBtn);
    }
});

function enhancePagination() {
    const pag = document.querySelector('.pagination-container');
    const info = pag ? pag.querySelector('.pagination-info') : null;
    if (!pag || !info) return;

    const m = info.textContent.match(/(\d+)\s*з\s*(\d+)/i);
    if (!m) return;
    const current = parseInt(m[1], 10), total = parseInt(m[2], 10);
    if (!total || total <= 1) return;

    const buildUrl = (p) => { const u = new URL(window.location.href); u.searchParams.set('page', p); return u.toString(); };

    const nav = document.createElement('div');
    nav.className = 'pagination-pages';
    const addPage = (p) => {
        const a = document.createElement('a');
        a.className = 'page-num' + (p === current ? ' active' : '');
        a.textContent = p;
        a.href = buildUrl(p);
        nav.appendChild(a);
    };
    const addDots = () => { const s = document.createElement('span'); s.className = 'page-dots'; s.textContent = '…'; nav.appendChild(s); };

    const wanted = [1, 2, current - 1, current, current + 1, total - 1, total];
    const pages = [...new Set(wanted)].filter(p => p >= 1 && p <= total).sort((a, b) => a - b);
    let prev = 0;
    pages.forEach(p => { if (p - prev > 1) addDots(); addPage(p); prev = p; });

    const jump = document.createElement('div');
    jump.className = 'page-jump';
    jump.innerHTML = `<input type='number' min='1' max='${total}' placeholder='№' class='page-jump-input'><button type='button' class='page-jump-btn'>Перейти</button>`;
    const ji = jump.querySelector('.page-jump-input');
    const jb = jump.querySelector('.page-jump-btn');
    const go = () => { let p = parseInt(ji.value, 10); if (isNaN(p)) return; p = Math.min(Math.max(p, 1), total); window.location.href = buildUrl(p); };
    jb.addEventListener('click', go);
    ji.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); go(); } });

    info.replaceWith(nav);
    pag.appendChild(jump);
}
document.addEventListener('DOMContentLoaded', enhancePagination);

/* ==============================================
   FAVORITES SYSTEM (обране)
   ============================================== */
const Favorites = {
    sidebar: null,
    listEl: null,
    badge: null,
    guestKey: 'guest_favorites',
    ids: new Set(),

    init() {
        this.sidebar = document.getElementById('favorites-modal');
        this.listEl = document.getElementById('favorites-list-container');
        this.badge = document.getElementById('favorites-count');

        document.getElementById('open-favorites-btn')?.addEventListener('click', () => this.open());
        document.getElementById('open-favorites-btn-sidebar')?.addEventListener('click', (e) => { e.preventDefault(); this.open(); });

        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('.favorite-btn');
            if (!btn) return;
            e.preventDefault();
            const card = btn.closest('[data-id]');
            const id = card ? card.dataset.id : btn.dataset.id;
            if (id) this.toggle(String(id));
        });

        this.listEl?.addEventListener('click', (e) => {
            const rm = e.target.closest('.fav-remove');
            if (rm) {
                const row = rm.closest('[data-id]');
                if (row) this.toggle(String(row.dataset.id));
            }
        });

        this.refresh();
    },

    getGuestIds() {
        try { return JSON.parse(localStorage.getItem(this.guestKey) || '[]').map(String); }
        catch (e) { return []; }
    },
    setGuestIds(arr) {
        localStorage.setItem(this.guestKey, JSON.stringify([...new Set(arr.map(String))]));
    },

    async refresh() {
        try {
            const res = await fetch('/favorites/ids');
            const data = await res.json();
            let ids = (data.ids || []).map(String);
            if (ids.length === 0) {
                const guest = this.getGuestIds();
                if (guest.length) ids = guest;
            }
            this.ids = new Set(ids);
        } catch (e) {
            this.ids = new Set(this.getGuestIds());
        }
        this.updateBadge();
        this.syncButtons();
    },

    async toggle(id) {
        try {
            const res = await fetch('/favorites/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: id })
            });
            const data = await res.json();

            if (data.status === 'guest') {
                const guest = this.getGuestIds();
                let active;
                if (guest.includes(id)) {
                    this.setGuestIds(guest.filter(x => x !== id));
                    this.ids.delete(id);
                    active = false;
                } else {
                    guest.push(id);
                    this.setGuestIds(guest);
                    this.ids.add(id);
                    active = true;
                }
                UI.toast(active ? 'Додано в обране' : 'Видалено з обраного', active ? 'success' : 'info');
            } else if (data.status === 'success') {
                if (data.active) { this.ids.add(id); UI.toast('Додано в обране'); }
                else { this.ids.delete(id); UI.toast('Видалено з обраного', 'info'); }
            } else {
                throw new Error(data.message || 'error');
            }
        } catch (e) {
            UI.toast('Не вдалося оновити обране', 'error');
            return;
        }
        this.updateBadge();
        this.syncButtons();
        if (this.sidebar && this.sidebar.classList.contains('active')) this.render();
    },

    syncButtons() {
        document.querySelectorAll('.favorite-btn').forEach(btn => {
            const card = btn.closest('[data-id]');
            const id = card ? String(card.dataset.id) : btn.dataset.id;
            btn.classList.toggle('active', this.ids.has(String(id)));
        });
    },

    updateBadge() {
        if (!this.badge) return;
        const n = this.ids.size;
        this.badge.textContent = n;
        this.badge.style.display = n > 0 ? 'flex' : 'none';
    },

    open() {
        UI.openModal(this.sidebar);
        this.render();
    },

    async render() {
        if (!this.listEl) return;
        this.listEl.innerHTML = `<div class="text-center" style="padding:30px;color:var(--text-tertiary);"><i class="fas fa-spinner fa-spin"></i></div>`;
        let items = [];
        try {
            const res = await fetch('/favorites/items', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: [...this.ids] })
            });
            const data = await res.json();
            items = data.items || [];
        } catch (e) { /* ignore */ }

        if (!items.length) {
            this.listEl.innerHTML = `
                <div class="text-center" style="padding:40px;color:var(--text-tertiary);">
                    <i class="far fa-heart" style="font-size:3rem;margin-bottom:15px;"></i>
                    <p>У вас ще немає обраних товарів</p>
                    <button onclick="UI.closeAllModals()" class="btn btn-sm btn-outline mt-3">Перейти до покупок</button>
                </div>`;
            return;
        }

        this.listEl.innerHTML = items.map(item => `
            <div class="cart-item" data-id="${item.id}">
                <div class="cart-item-left">
                    <a href="${item.url}"><img src="${item.image}" alt="${item.name}" onerror="this.onerror=null;this.src='https://placehold.co/400x400/f8fafc/94a3b8?text=No+Image';"></a>
                </div>
                <div class="cart-item-right">
                    <div class="cart-item-top">
                        <a href="${item.url}" class="cart-item-title">${item.name}</a>
                        <button class="remove-item fav-remove" title="Видалити з обраного"><i class="fas fa-times"></i></button>
                    </div>
                    <div class="cart-item-bottom">
                        <div class="cart-item-price">${item.price.toFixed(2)} ₴</div>
                        <button class="btn btn-sm add-to-cart-btn" data-id="${item.id}"><i class="fas fa-shopping-cart"></i> <span class="btn-text">В кошик</span></button>
                    </div>
                </div>
            </div>
        `).join('');
        if (typeof Cart !== 'undefined' && Cart.fetchCart) Cart.fetchCart(false);
    }
};

/* ==============================================
   REVIEWS / QUESTIONS modal triggers
   ============================================== */
const ReviewsUI = {
    init() {
        document.getElementById('open-review-modal-btn')?.addEventListener('click', () => {
            UI.openModal(document.getElementById('review-modal'));
        });
        document.getElementById('open-question-modal-btn')?.addEventListener('click', () => {
            UI.openModal(document.getElementById('question-modal'));
        });
        document.body.addEventListener('click', (e) => {
            const rb = e.target.closest('.reply-btn');
            if (rb) {
                e.preventDefault();
                openReplyModal(rb.dataset.reviewId, window.location.href);
            }
        });
    }
};

/* ==============================================
   NOVA POSHTA autocomplete (checkout)
   ============================================== */
const NovaPoshta = {
    cityRef: '',
    init() {
        const cityInput = document.getElementById('delivery_city');
        const whInput = document.getElementById('delivery_warehouse');
        const citySug = document.getElementById('city-suggestions');
        const whSug = document.getElementById('warehouse-suggestions');
        if (!cityInput || !whInput) return;

        let cityTimer, whTimer;
        const hide = (el) => { if (el) { el.innerHTML = ''; el.style.display = 'none'; } };
        const show = (el) => { if (el) el.style.display = 'block'; };

        hide(citySug); hide(whSug);

        cityInput.addEventListener('input', () => {
            this.cityRef = '';
            whInput.value = '';
            whInput.disabled = true;
            whInput.placeholder = 'Спочатку оберіть місто';
            const q = cityInput.value.trim();
            clearTimeout(cityTimer);
            if (q.length < 2) { hide(citySug); return; }
            cityTimer = setTimeout(async () => {
                citySug.innerHTML = '<div class="suggestion-loading">Пошук...</div>'; show(citySug);
                try {
                    const res = await fetch(`/api/np/cities?q=${encodeURIComponent(q)}`);
                    const data = await res.json();
                    if (data.error) { citySug.innerHTML = `<div class="suggestion-empty">${data.error}</div>`; return; }
                    if (!data.cities.length) { citySug.innerHTML = '<div class="suggestion-empty">Нічого не знайдено</div>'; return; }
                    citySug.innerHTML = data.cities.map(c =>
                        `<button type="button" class="suggestion-item" data-ref="${c.ref}" data-name="${c.name}">${c.name}${c.area ? ` <span style="color:#94a3b8">(${c.area} обл.)</span>` : ''}</button>`
                    ).join('');
                } catch (e) { citySug.innerHTML = '<div class="suggestion-empty">Помилка завантаження</div>'; }
            }, 350);
        });

        citySug && citySug.addEventListener('click', (e) => {
            const item = e.target.closest('.suggestion-item');
            if (!item) return;
            cityInput.value = item.dataset.name;
            this.cityRef = item.dataset.ref;
            hide(citySug);
            whInput.disabled = false;
            whInput.placeholder = 'Введіть номер або адресу відділення';
            whInput.focus();
        });

        whInput.addEventListener('input', () => {
            const q = whInput.value.trim();
            clearTimeout(whTimer);
            if (!this.cityRef) { hide(whSug); return; }
            whTimer = setTimeout(async () => {
                whSug.innerHTML = '<div class="suggestion-loading">Пошук...</div>'; show(whSug);
                try {
                    const res = await fetch(`/api/np/warehouses?city_ref=${encodeURIComponent(this.cityRef)}&q=${encodeURIComponent(q)}`);
                    const data = await res.json();
                    if (data.error) { whSug.innerHTML = `<div class="suggestion-empty">${data.error}</div>`; return; }
                    if (!data.warehouses.length) { whSug.innerHTML = '<div class="suggestion-empty">Відділень не знайдено</div>'; return; }
                    whSug.innerHTML = data.warehouses.map(w =>
                        `<button type="button" class="suggestion-item" data-name="${w.name}">${w.name}</button>`
                    ).join('');
                } catch (e) { whSug.innerHTML = '<div class="suggestion-empty">Помилка завантаження</div>'; }
            }, 350);
        });

        whInput.addEventListener('focus', () => {
            if (this.cityRef && whInput.value.trim() === '') whInput.dispatchEvent(new Event('input'));
        });

        whSug && whSug.addEventListener('click', (e) => {
            const item = e.target.closest('.suggestion-item');
            if (!item) return;
            whInput.value = item.dataset.name;
            hide(whSug);
        });

        document.addEventListener('click', (e) => {
            if (citySug && !cityInput.contains(e.target) && !citySug.contains(e.target)) hide(citySug);
            if (whSug && !whInput.contains(e.target) && !whSug.contains(e.target)) hide(whSug);
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Favorites.init();
    ReviewsUI.init();
    if (document.querySelector('.checkout-page-v2')) NovaPoshta.init();
});

/* ==============================================
   GUEST GATING — блокуємо кошик/обране для неавторизованих
   ============================================== */
document.addEventListener('click', (e) => {
    if (document.body.classList.contains('user-logged-in')) return;
    const cartBtn = e.target.closest('.add-to-cart-btn');
    const favBtn = e.target.closest('.favorite-btn');
    const buyBtn = e.target.closest('.buy-now-btn');
    if (cartBtn || favBtn || buyBtn) {
        e.preventDefault();
        e.stopImmediatePropagation();
        const modal = document.getElementById('auth-required-modal');
        if (modal && typeof UI !== 'undefined') UI.openModal(modal);
    }
}, true);

/* ==============================================
   CATALOG — миттєва AJAX-фільтрація без перезавантаження
   + реальні мінімальна/максимальна ціни
   ============================================== */
(function () {
    const catalogPage = document.querySelector('.catalog-page');
    if (!catalogPage) return;

    const getContainer = () => document.querySelector('.products-container');

    function setActiveCategory(url) {
        try {
            const target = new URL(url, window.location.origin).pathname;
            document.querySelectorAll('.cat-name-link').forEach(a => {
                const href = a.getAttribute('href');
                if (!href) return;
                const path = new URL(href, window.location.origin).pathname;
                a.classList.toggle('active', path === target);
            });
        } catch (e) { /* ignore */ }
    }

    async function loadCatalog(url, push = true) {
        const container = getContainer();
        if (!container) { window.location.href = url; return; }
        container.style.transition = 'opacity .15s';
        container.style.opacity = '0.45';
        container.style.pointerEvents = 'none';
        try {
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const html = await res.text();
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const fresh = doc.querySelector('.products-container');
            if (!fresh) { window.location.href = url; return; }
            container.innerHTML = fresh.innerHTML;
            if (typeof enhancePagination === 'function') enhancePagination();
            setActiveCategory(url);
            if (push) history.pushState({ catalogUrl: url }, '', url);
            window.scrollTo({ top: catalogPage.offsetTop - 80, behavior: 'smooth' });
            applyPriceRange();
        } catch (e) {
            window.location.href = url;
        } finally {
            container.style.opacity = '';
            container.style.pointerEvents = '';
        }
    }

    // Кліки по категоріях (разом із "Всі товари") — фільтруємо без перезавантаження
    document.addEventListener('click', (e) => {
        const pageLink = e.target.closest('.page-num, .pagination-btn');
        if (pageLink) {
            if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
            if (pageLink.classList.contains('disabled')) { e.preventDefault(); return; }
            const phref = pageLink.getAttribute('href');
            if (phref && phref !== '#') { e.preventDefault(); loadCatalog(phref); }
            return;
        }
        const link = e.target.closest('.cat-name-link');
        if (!link) return;
        const href = link.getAttribute('href');
        if (!href || href === '#') return;
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        loadCatalog(href);
    });

    // Застосування фільтрів (ціна / наявність) без перезавантаження
    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        const submitForm = () => {
            const params = new URLSearchParams(window.location.search);
            params.delete('in_stock');
            params.delete('min_price');
            params.delete('max_price');
            params.delete('page');
            const fd = new FormData(filterForm);
            for (const [k, v] of fd.entries()) { if (v) params.set(k, v); }
            const qs = params.toString();
            loadCatalog(qs ? `${window.location.pathname}?${qs}` : window.location.pathname);
        };
        filterForm.addEventListener('submit', (e) => { e.preventDefault(); submitForm(); });
        const inStock = filterForm.querySelector('input[name="in_stock"]');
        if (inStock) inStock.addEventListener('change', submitForm);
    }

    window.addEventListener('popstate', () => { loadCatalog(window.location.href, false); });

    // Реальні мін/макс ціни на основі наявних товарів
    async function applyPriceRange() {
        const minInput = document.querySelector('#filter-form input[name="min_price"]');
        const maxInput = document.querySelector('#filter-form input[name="max_price"]');
        if (!minInput && !maxInput) return;
        const slug = catalogPage.dataset.categorySlug || '';
        try {
            const res = await fetch(`/api/price_range?category_slug=${encodeURIComponent(slug)}`);
            const data = await res.json();
            if (typeof data.min !== 'number' || typeof data.max !== 'number') return;
            [minInput, maxInput].forEach(inp => { if (inp) { inp.min = data.min; inp.max = data.max; } });
            if (minInput) minInput.placeholder = `Від ${data.min}`;
            if (maxInput) maxInput.placeholder = `До ${data.max}`;
            const sMin = document.querySelector('.price-range-min');
            const sMax = document.querySelector('.price-range-max');
            [sMin, sMax].forEach(s => { if (s) { s.min = data.min; s.max = data.max; } });
            if (sMin && !sMin.dataset.userSet) sMin.value = data.min;
            if (sMax && !sMax.dataset.userSet) sMax.value = data.max;
            const sliderWrap = document.querySelector('.price-slider');
            if (sliderWrap && typeof sliderWrap.__repaint === 'function') sliderWrap.__repaint();
        } catch (e) { /* мовчки ігноруємо */ }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyPriceRange);
    } else {
        applyPriceRange();
    }
})();

/* ==============================================
   REVIEWS — на сторінці питань кнопка "Написати відгук" веде до сторінки відгуків
   ============================================== */
document.addEventListener('DOMContentLoaded', () => {
    if (/\/questions\/?$/.test(window.location.pathname)) {
        document.querySelectorAll('#open-review-modal-btn').forEach(btn => {
            const clone = btn.cloneNode(true);
            btn.parentNode.replaceChild(clone, btn);
            clone.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = window.location.pathname.replace(/\/questions\/?$/, '/reviews');
            });
        });
    }
});
