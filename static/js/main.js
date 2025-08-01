document.addEventListener('DOMContentLoaded', function() {
    // Ініціалізація всіх основних модулів
    initAuth();
    initHeaderActions();
    initContactForm();
    initReviewsPage();
    initHeroSlider();
    initSimilarProductsCarousel();
    initProductDescriptionToggle();
    initOptimizedCartLogic();
    initFavoritesLogic();

    // Ініціалізуємо маску для полів вводу телефону
    setupPhoneMaskAdvanced('#customer_phone');
    setupPhoneMaskAdvanced('#register_phone');

    // Первинне завантаження стану кошика та кнопок при завантаженні сторінки
    updateCartView();
    updateFavoritesUI();
});

// ===================================================================
//  ОПТИМІЗОВАНА ЛОГІКА КОШИКА
// ===================================================================

function initOptimizedCartLogic() {
    document.body.addEventListener('click', e => {
        const button = e.target.closest('button');
        if (!button) return;

        const productCard = button.closest('[data-id]');
        const productId = productCard?.dataset.id;

        if (!productId) return;

        // --- ДІЯ 1: ДОДАТИ В КОШИК ---
        if (button.matches('.add-to-cart-btn') && !button.classList.contains('in-cart')) {
            setButtonAsInCart(button, true);
            updateCartCounter(1);
            showToast('Товар додано до кошика', 'success', `<a href="/checkout" class="btn btn-sm btn-primary">Оформити</a>`);

            fetch('/add_to_cart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status !== 'success') {
                    setButtonAsInCart(button, false);
                    updateCartCounter(-1);
                    showToast(data.message || 'Помилка додавання товару', 'error');
                } else {
                    updateCartView();
                }
            }).catch(() => {
                setButtonAsInCart(button, false);
                updateCartCounter(-1);
                showToast('Мережева помилка', 'error');
            });
        }

        // --- ДІЯ 2: КУПИТИ ЗАРАЗ ---
        if (button.matches('.buy-now-btn')) {
             fetch('/buy_now', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: productId })})
             .then(res => res.json()).then(data => { if(data.status === 'success') window.location.href = '/checkout'; });
        }

        // --- ДІЯ 3: КНОПКИ +/- У БІЧНОМУ КОШИКУ ---
        if (button.matches('.qty-btn')) {
             const cartItemRow = button.closest('.cart-item');
             const quantityDisplay = cartItemRow.querySelector('.quantity-display');
             const currentQuantity = parseInt(quantityDisplay.textContent);
             const newQuantity = button.classList.contains('plus') ? currentQuantity + 1 : currentQuantity - 1;

             if (newQuantity >= 1) {
                updateCartView();
                fetch(`/update_cart_quantity/${productId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({quantity: newQuantity})
                }).then(() => updateCartView());
             }
        }

        // --- ДІЯ 4: ВИДАЛИТИ З БІЧНОГО КОШИКА ---
        if (button.matches('.remove-item')) {
            const cartItemRow = button.closest('.cart-item');
            if (cartItemRow) {
                cartItemRow.style.transition = 'opacity 0.3s, transform 0.3s';
                cartItemRow.style.opacity = '0';
                cartItemRow.style.transform = 'translateX(50px)';
                setTimeout(() => {
                     updateCartView();
                }, 300);
                fetch(`/remove_from_cart/${productId}`, { method: 'POST' });
            }
        }
    });
}

function updateCartCounter(change) {
    const counter = document.getElementById('cart-count');
    if (counter) {
        const currentValue = parseInt(counter.textContent, 10) || 0;
        counter.textContent = Math.max(0, currentValue + change);
    }
}

function setButtonAsInCart(button, isInCart) {
    const isLargeButton = button.classList.contains('btn-lg');
    button.classList.toggle('in-cart', isInCart);
    if (isInCart) {
        button.innerHTML = isLargeButton ? '<i class="fas fa-check"></i> Вже в кошику' : '<i class="fas fa-check"></i>';
    } else {
        button.innerHTML = isLargeButton ? '<i class="fas fa-shopping-cart"></i> В кошик' : 'Додати в кошик';
    }
}

function setupPhoneMaskAdvanced(selector) {
    const phoneInput = document.querySelector(selector);
    if (!phoneInput) return;
    const matrix = "+380 (__) ___-__-__";
    const prefixNumber = "380";
    const setCursorPosition = (pos, elem) => {
        requestAnimationFrame(() => {
            elem.focus();
            elem.setSelectionRange(pos, pos);
        });
    };
    const applyMask = (value) => {
        let digits = value.replace(/\D/g, "");
        if (digits.length < prefixNumber.length) {
            digits = prefixNumber;
        } else {
            digits = prefixNumber + digits.substring(prefixNumber.length);
        }
        let i = 0;
        let formattedValue = matrix.replace(/[_\d]/g, (char) => {
            return i < digits.length ? digits.charAt(i++) : char;
        });
        let cursorPos = formattedValue.indexOf('_');
        if (cursorPos === -1) {
            cursorPos = formattedValue.length;
        }
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
                const newDigits = digits.slice(0, -1);
                const { formattedValue, cursorPos } = applyMask(newDigits);
                e.target.value = formattedValue;
                setCursorPosition(cursorPos, e.target);
            }
        }
    });
    phoneInput.addEventListener('focus', (e) => {
        if (!e.target.value) {
            const { formattedValue, cursorPos } = applyMask("");
            e.target.value = formattedValue;
            setCursorPosition(cursorPos, e.target);
        }
    });
    phoneInput.addEventListener('click', (e) => {
        const { cursorPos } = applyMask(e.target.value);
        setCursorPosition(cursorPos, e.target);
    });
    phoneInput.addEventListener('blur', (e) => {
        if (e.target.value.replace(/\D/g, "") === prefixNumber) {
            e.target.value = '';
        }
    });
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
    fetch('/get_cart').then(res => res.json()).then(data => {
        document.getElementById('cart-count').textContent = data.items.reduce((sum, item) => sum + item.quantity, 0);
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
                            <span class="quantity-display">${item.quantity}</span>
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
        updateAllProductButtonStates(data.items);
    });
}

function updateAllProductButtonStates(cartItems) {
    const cartProductIds = new Set(cartItems.map(item => String(item.id)));
    document.querySelectorAll('.add-to-cart-btn').forEach(button => {
        const productId = button.closest('[data-id]')?.dataset.id;
        if (productId) {
            const isInCart = cartProductIds.has(productId);
            setButtonAsInCart(button, isInCart);
        }
    });
}

function initFavoritesLogic() {
    document.body.addEventListener('click', e => {
        const favoriteBtn = e.target.closest('.favorite-btn');
        if (favoriteBtn) {
            const productId = favoriteBtn.closest('[data-id]')?.dataset.id;
            if (productId) toggleFavorite(productId);
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
    // Re-render modal if it's open
    if (document.getElementById('favorites-modal')?.classList.contains('active')) {
        renderFavoritesModal();
    }
}

function updateFavoritesUI() {
    const favorites = JSON.parse(localStorage.getItem('favorites')) || [];
    document.getElementById('favorites-count').textContent = favorites.length;
    document.querySelectorAll('.favorite-btn').forEach(btn => {
        const productId = btn.closest('[data-id]')?.dataset.id;
        btn.classList.toggle('active', favorites.includes(productId));
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
        fetch('/get_cart').then(r => r.json()).then(cartData => {
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
                        <button class="favorite-btn active" title="Видалити з обраного"><i class="fas fa-star"></i></button>
                        ${adminActionsHtml}
                    </div>
                    <div class="product-info">
                        <h3><a href="${p.url}">${p.name}</a></h3>
                        <div class="product-footer">
                            <span class="price">${p.price.toFixed(2)} ₴</span>
                            <button class="btn btn-sm add-to-cart-btn" data-id="${p.id}" ${p.in_stock ? '' : 'disabled'}>Додати в кошик</button>
                        </div>
                    </div>
                </div>`);
            });
            updateAllProductButtonStates(cartData.items);
        });
    });
}

function showToast(message, type = 'success', actions = '') {
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
    setTimeout(() => {
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }, 3000);
    }, 10);
}

function initAuth() {
    const authModal = document.getElementById('auth-modal');
    if (!authModal) return;
    document.getElementById('open-auth-modal')?.addEventListener('click', () => authModal.classList.add('active'));
    authModal.addEventListener('click', e => {
        if (e.target.classList.contains('close-modal') || e.target.id === 'auth-modal') authModal.classList.remove('active');
    });
    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.auth-tab, .tab-content').forEach(el => el.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(this.dataset.tab).classList.add('active');
        });
    });
    const handleFormSubmit = (formId, url, errorElId) => {
        const form = document.getElementById(formId);
        if(!form) return;
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(this).entries());
            fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
            .then(res => res.json()).then(result => {
                if (result.status === 'success') window.location.reload();
                else {
                    const errorEl = document.getElementById(errorElId);
                    errorEl.textContent = result.message;
                    errorEl.style.display = 'block';
                }
            });
        });
    };
    handleFormSubmit('loginForm', '/login', 'loginError');
    handleFormSubmit('registerForm', '/register', 'registerError');
}

function initHeaderActions() {
    const cartModal = document.getElementById('cart-modal');
    if(!cartModal) return;
    document.getElementById('open-cart-btn')?.addEventListener('click', () => {
        updateCartView();
        cartModal.classList.add('active');
    });
    cartModal.addEventListener('click', e => {
        if (e.target.matches('.close-modal') || e.target.id === 'cart-modal') cartModal.classList.remove('active');
    });
}

function initContactForm() {
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('/send_message', { method: 'POST', body: new FormData(this) }).then(response => response.json()).then(data => {
                showToast(data.message, data.status === 'success' ? 'success' : 'error');
                if (data.status === 'success') this.reset();
            }).catch(() => showToast('Сталася помилка при відправці.', 'error'));
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
    const slider = document.querySelector('.hero-slider');
    if (!slider) return;
    const slides = slider.querySelectorAll('.hero-slide');
    if (slides.length <= 1) return;
    const dotsContainer = slider.querySelector('.slider-dots');
    let currentIndex = 0;
    dotsContainer.innerHTML = '';
    slides.forEach((_, i) => {
        const dot = document.createElement('button');
        dot.classList.add('dot');
        dot.addEventListener('click', () => showSlide(i));
        dotsContainer.appendChild(dot);
    });
    const dots = dotsContainer.querySelectorAll('.dot');
    const showSlide = index => {
        slides[currentIndex].classList.remove('active');
        dots[currentIndex].classList.remove('active');
        currentIndex = (index + slides.length) % slides.length;
        slides[currentIndex].classList.add('active');
        dots[currentIndex].classList.add('active');
    };
    slider.querySelector('.next-btn').addEventListener('click', () => showSlide(currentIndex + 1));
    slider.querySelector('.prev-btn').addEventListener('click', () => showSlide(currentIndex - 1));
    setInterval(() => showSlide(currentIndex + 1), 5000);
    showSlide(0);
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
        scrollAmount = Math.min(scrollAmount + itemWidth * 2, maxScroll); // scroll by 2 items
        track.style.transform = `translateX(-${scrollAmount}px)`;
        updateButtons();
    });
    prevBtn.addEventListener('click', () => {
        scrollAmount = Math.max(scrollAmount - itemWidth * 2, 0); // scroll by 2 items
        track.style.transform = `translateX(-${scrollAmount}px)`;
        updateButtons();
    });
    updateButtons();
}
```

---
### **`checkout.html` (Вирішальний файл)**
*Тут головні зміни: `autocomplete="off"` для поля міста та оновлений JS для обробки вибору.*
```html
{% extends "base.html" %}
{% block title %}Оформлення замовлення{% endblock %}

{% block content %}
<div class="checkout-page-v2">
    <div class="container">
        <h1 class="page-title" style="text-align: left; border: none; padding-bottom: 20px;">Оформлення замовлення</h1>
        <form action="{{ url_for('checkout') }}" method="POST" class="checkout-grid-v2" id="checkout-form">
            <!-- Ліва колонка з даними -->
            <div>
                <section class="checkout-section">
                    <div class="checkout-section-header">
                        <span class="icon">1</span><h4>Контактні дані</h4>
                    </div>
                    <div class="form-group-inline">
                        <div class="form-group">
                            <label for="customer_first_name">Ім'я</label>
                            <input type="text" name="customer_first_name" id="customer_first_name" required value="{% if current_user.is_authenticated %}{{ current_user.first_name }}{% endif %}" placeholder="Іван">
                        </div>
                        <div class="form-group">
                            <label for="customer_last_name">Прізвище</label>
                            <input type="text" name="customer_last_name" id="customer_last_name" required value="{% if current_user.is_authenticated %}{{ current_user.last_name or '' }}{% endif %}" placeholder="Іванов">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="customer_phone">Номер телефону</label>
                        <input type="tel" name="customer_phone" id="customer_phone" required>
                    </div>
                </section>

                <section class="checkout-section">
                    <div class="checkout-section-header">
                        <span class="icon">2</span><h4>Доставка</h4>
                    </div>
                    <div class="radio-group" id="delivery-method-group">
                        <label class="radio-option active">
                            <input type="radio" name="delivery_method" value="Самовивіз з магазину" checked>
                            <div>
                                <strong>Самовивіз з магазину</strong>
                                <p>Безкоштовно за адресою: {{ shop.city }}, {{ shop.address }}</p>
                            </div>
                        </label>
                        <label class="radio-option">
                            <input type="radio" name="delivery_method" value="Нова Пошта">
                             <div>
                                <strong>Нова Пошта</strong>
                                <p>Доставка у відділення або поштомат по Україні.</p>
                            </div>
                        </label>
                    </div>
                    <div id="nova-poshta-details" style="display: none; margin-top: 20px; border-top: 1px solid #eee; padding-top: 20px; position: relative;">
                        <div class="form-group">
                            <label for="delivery_city">Населений пункт</label>
                            <input type="text" name="delivery_city" id="delivery_city" placeholder="Введіть назву міста чи села" autocomplete="off">
                            <div id="city-suggestions" class="suggestions-dropdown"></div>
                        </div>
                        <div class="form-group">
                            <label for="delivery_warehouse">Відділення або поштомат</label>
                            <select name="delivery_warehouse" id="delivery_warehouse" disabled>
                                <option value="">Спочатку виберіть населений пункт</option>
                            </select>
                        </div>
                    </div>
                </section>

                <section class="checkout-section">
                    <div class="checkout-section-header">
                        <span class="icon">3</span><h4>Оплата</h4>
                    </div>
                    <div class="radio-group">
                        <label class="radio-option active">
                            <input type="radio" name="payment_method" value="Післяплата" checked>
                            <div>
                                <strong>Післяплата (при отриманні)</strong>
                                <p>Оплата готівкою або карткою у відділенні "Нової Пошти".</p>
                            </div>
                        </label>
                        <label class="radio-option">
                            <input type="radio" name="payment_method" value="Оплата на рахунок">
                             <div>
                                <strong>Оплата на рахунок</strong>
                                <p>Реквізити для оплати будуть надіслані після підтвердження замовлення.</p>
                            </div>
                        </label>
                    </div>
                </section>
            </div>

            <!-- Права колонка з підсумком замовлення -->
            <aside class="order-summary-v2">
                <section class="checkout-section">
                    <h4>Ваше замовлення</h4>
                    <div id="summary-item-list"></div>
                    <div class="summary-totals">
                        <div class="summary-total-row">
                            <span>Вартість товарів:</span>
                            <span id="summary-subtotal">...</span>
                        </div>
                        <div class="summary-total-row">
                            <span>Доставка:</span>
                            <span>За тарифами</span>
                        </div>
                        <div class="summary-total-row grand-total">
                            <span>Разом до сплати:</span>
                            <span id="summary-grand-total">...</span>
                        </div>
                    </div>
                     <button type="submit" id="submit-checkout-btn" class="btn btn-primary btn-block btn-lg">Підтвердити замовлення</button>
                </section>
            </aside>
        </form>
    </div>
</div>
{% endblock %}

{% block extra_css %}
<style>
    .suggestions-dropdown { display: none; position: absolute; background-color: white; border: 1px solid #ddd; border-top: none; width: 100%; max-height: 200px; overflow-y: auto; z-index: 100; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    .suggestion-item { padding: 10px 12px; cursor: pointer; font-size: 15px; }
    .suggestion-item:hover { background-color: #f0f0f0; }
    .suggestion-item-loading { padding: 10px 12px; color: #888; font-style: italic; }
</style>
{% endblock %}

{% block extra_js %}
<script>
document.addEventListener('DOMContentLoaded', function() {
    setupRadioGroups();
    loadCartSummary();
    setupDeliveryLogic();
    setupEnterKeyNavigation();

    function setupDeliveryLogic() {
        const deliveryGroup = document.getElementById('delivery-method-group');
        const novaPoshtaDetails = document.getElementById('nova-poshta-details');
        const cityInput = document.getElementById('delivery_city');
        const citySuggestions = document.getElementById('city-suggestions');
        const warehouseSelect = document.getElementById('delivery_warehouse');
        const submitBtn = document.getElementById('submit-checkout-btn');
        let searchTimeout;

        deliveryGroup.addEventListener('change', (e) => {
            const radio = e.target.closest('input[type="radio"]');
            if (radio) {
                const isNovaPoshta = radio.value === 'Нова Пошта';
                novaPoshtaDetails.style.display = isNovaPoshta ? 'block' : 'none';
                cityInput.required = isNovaPoshta;
                warehouseSelect.required = isNovaPoshta;
                toggleSubmitButton();
            }
        });

        cityInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();

            if (query.length < 2) {
                citySuggestions.style.display = 'none';
                return;
            }

            citySuggestions.innerHTML = '<div class="suggestion-item-loading">Пошук...</div>';
            citySuggestions.style.display = 'block';

            searchTimeout = setTimeout(() => {
                fetch(`/api/np/cities?q=${encodeURIComponent(query)}`)
                    .then(res => res.json())
                    .then(cities => {
                        citySuggestions.innerHTML = '';
                        if (cities && cities.length > 0) {
                            cities.forEach(city => {
                                const item = document.createElement('div');
                                item.className = 'suggestion-item';
                                item.textContent = city.name;
                                item.dataset.ref = city.ref;
                                item.addEventListener('click', () => selectCity(city));
                                citySuggestions.appendChild(item);
                            });
                        } else {
                            citySuggestions.innerHTML = '<div class="suggestion-item-loading">Нічого не знайдено</div>';
                        }
                    });
            }, 300);
        });

        function selectCity(city) {
            cityInput.value = city.name;
            citySuggestions.style.display = 'none';
            fetchWarehouses(city.ref);
        }

        function fetchWarehouses(cityRef) {
            warehouseSelect.disabled = true;
            warehouseSelect.innerHTML = '<option value="">Завантаження відділень...</option>';
            toggleSubmitButton();

            fetch(`/api/np/warehouses?city_ref=${cityRef}`)
                .then(res => res.json())
                .then(warehouses => {
                    if (warehouses && warehouses.length > 0 && !warehouses.error) {
                        warehouseSelect.innerHTML = '<option value="">-- Оберіть відділення --</option>';
                        warehouses.forEach(wh => {
                            const option = new Option(wh, wh);
                            warehouseSelect.add(option);
                        });
                        warehouseSelect.disabled = false;
                    } else {
                        warehouseSelect.innerHTML = `<option value="">${warehouses.error || 'Відділення не знайдені'}</option>`;
                    }
                    toggleSubmitButton();
                })
                .catch(err => {
                    console.error("Помилка завантаження відділень:", err);
                    warehouseSelect.innerHTML = '<option value="">Помилка завантаження</option>';
                    toggleSubmitButton();
                });
        }

        document.addEventListener('click', (e) => {
            if (!novaPoshtaDetails.contains(e.target)) {
                citySuggestions.style.display = 'none';
            }
        });

        warehouseSelect.addEventListener('change', toggleSubmitButton);
        function toggleSubmitButton() {
            const isNovaPoshta = document.querySelector('input[name="delivery_method"]:checked').value === 'Нова Пошта';
            if (isNovaPoshta) {
                submitBtn.disabled = !warehouseSelect.value;
            } else {
                submitBtn.disabled = false;
            }
        }
    }

    function setupRadioGroups() {
        document.querySelectorAll('.radio-group').forEach(group => {
            group.addEventListener('click', e => {
                const label = e.target.closest('.radio-option');
                if (!label) return;
                group.querySelectorAll('.radio-option').forEach(opt => opt.classList.remove('active'));
                label.classList.add('active');
                const radio = label.querySelector('input');
                if (radio) {
                    radio.checked = true;
                    // Створюємо та відправляємо подію, щоб інші слухачі могли її зловити
                    const event = new Event('change', { bubbles: true });
                    group.dispatchEvent(event);
                }
            });
        });
    }

    function loadCartSummary() {
        fetch('/get_cart').then(res => res.json()).then(data => {
            const listContainer = document.getElementById('summary-item-list');
            const subtotalEl = document.getElementById('summary-subtotal');
            const grandTotalEl = document.getElementById('summary-grand-total');
            listContainer.innerHTML = '';
            if (data.items.length > 0) {
                data.items.forEach(item => {
                    listContainer.insertAdjacentHTML('beforeend', `
                        <div class="summary-item">
                            <img src="${item.image}" alt="${item.name}">
                            <div class="summary-item-details">
                                <div class="name">${item.name}</div>
                                <div class="price">${item.quantity} x ${item.price.toFixed(2)} ₴</div>
                            </div>
                        </div>`);
                });
            } else {
                 window.location.href = "{{ url_for('catalog') }}"; // Якщо кошик порожній, перекидаємо
            }
            subtotalEl.textContent = `${data.total.toFixed(2)} ₴`;
            grandTotalEl.textContent = `${data.total.toFixed(2)} ₴`;
        });
    }

    function setupEnterKeyNavigation() {
        const form = document.getElementById('checkout-form');
        if (!form) return;
        form.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.id !== 'delivery_city') {
                e.preventDefault();
                const inputs = Array.from(form.querySelectorAll('input:not([type="radio"]), select')).filter(el => !el.disabled);
                const currentIndex = inputs.indexOf(e.target);
                const nextInput = inputs[currentIndex + 1];
                if (nextInput) {
                    nextInput.focus();
                } else {
                    form.querySelector('button[type="submit"]').focus();
                }
            }
        });
    }
});
</script>
{% endblock %}