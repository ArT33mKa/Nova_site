// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // Ініціалізація всіх систем
    initAuth();
    initHeaderActions();
    initFavorites();
    initCart();
    initContactForm();
    initCollapsibleFilters();
    initProductActions(); // Додаємо ініціалізацію для кнопок на сторінці товару
});

// ==============================================
//  СИСТЕМА АВТОРИЗАЦІЇ І МОДАЛЬНИХ ВІКОН
// ==============================================
function initAuth() {
    const authModal = document.getElementById('auth-modal');
    const openAuthBtn = document.getElementById('open-auth-modal');
    if (openAuthBtn) {
        openAuthBtn.addEventListener('click', () => authModal.classList.add('active'));
    }
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.target.closest('.modal, .cart-sidebar').classList.remove('active');
        });
    });
    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.auth-tab, .tab-content').forEach(el => el.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(this.dataset.tab).classList.add('active');
        });
    });
    handleAuthForms();
}

function initCollapsibleFilters() {
    document.querySelectorAll('.filter-toggle-btn').forEach(button => {
        button.addEventListener('click', function() {
            this.classList.toggle('open');
            const content = this.nextElementSibling;
            content.classList.toggle('collapsed');
        });
        const content = button.nextElementSibling;
        if (content) content.classList.add('collapsed');
    });
}

function initContactForm() {
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(contactForm);
            fetch('/send_message', { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                showToast(data.message, data.status);
                if (data.status === 'success') contactForm.reset();
            })
            .catch(error => showToast('Сталася помилка при відправці.', 'error'));
        });
    }
}

function handleAuthForms() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(loginForm).entries());
            fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
            .then(res => res.json())
            .then(result => {
                if (result.status === 'success') window.location.reload();
                else {
                    const errorEl = document.getElementById('loginError');
                    errorEl.textContent = result.message;
                    errorEl.style.display = 'block';
                }
            });
        });
    }
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(registerForm).entries());
            fetch('/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
            .then(res => res.json())
            .then(result => {
                if (result.status === 'success') window.location.reload();
                else {
                    const errorEl = document.getElementById('registerError');
                    errorEl.textContent = result.message;
                    errorEl.style.display = 'block';
                }
            });
        });
    }
}

// ==============================================
//  ДІЇ В ХЕДЕРІ (Кошик, Обране)
// ==============================================
function initHeaderActions() {
    const openCartBtn = document.getElementById('open-cart-btn');
    const cartModal = document.getElementById('cart-modal');
    const openFavoritesBtn = document.getElementById('open-favorites-btn');
    const favoritesModal = document.getElementById('favorites-modal');
    if (openCartBtn && cartModal) {
        openCartBtn.addEventListener('click', () => {
            updateCartView();
            cartModal.classList.add('active');
        });
    }
    if (openFavoritesBtn && favoritesModal) {
        openFavoritesBtn.addEventListener('click', () => {
            renderFavoritesModal();
            favoritesModal.classList.add('active');
        });
    }
}

// ==============================================
//  СИСТЕМА ОБРАНОГО (Favorites)
// ==============================================
function initFavorites() {
    updateFavoritesUI();
    document.addEventListener('click', (e) => {
        const favoriteBtn = e.target.closest('.favorite-btn');
        if (!favoriteBtn) return;
        const productCard = favoriteBtn.closest('[data-id]'); // Універсальний пошук
        if (!productCard) return;
        const productId = productCard.dataset.id;
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
    });
}

function updateFavoritesUI() {
    const favorites = JSON.parse(localStorage.getItem('favorites')) || [];
    const countEl = document.getElementById('favorites-count');
    if(countEl) countEl.textContent = favorites.length;
    document.querySelectorAll('[data-id]').forEach(card => {
        const btn = card.querySelector('.favorite-btn');
        if(btn) btn.classList.toggle('active', favorites.includes(card.dataset.id));
    });
}

function renderFavoritesModal() {
    const favorites = JSON.parse(localStorage.getItem('favorites')) || [];
    const container = document.getElementById('favorites-list-container');
    if (!container) return;
    if (favorites.length === 0) {
        container.innerHTML = '<p class="text-center" style="grid-column: 1 / -1;">Список обраного порожній.</p>';
        return;
    }
    container.innerHTML = '';
    favorites.forEach(id => {
        const productEl = document.querySelector(`.product-card[data-id='${id}']`);
        if (productEl) container.appendChild(productEl.cloneNode(true));
    });
}

// ==============================================
//  СИСТЕМА КОШИКА (Cart)
// ==============================================
function initCart() {
    updateCartView();
    // Видалення з кошика (в бічній панелі)
    document.addEventListener('click', e => {
        if (e.target.closest('.remove-item')) {
            const productId = e.target.closest('.remove-item').dataset.id;
             fetch(`/remove_from_cart/${productId}`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    showToast('Товар видалено з кошика');
                    updateCartView();
                }
            });
        }
    });
}

// ==============================================================
//  ОБРОБКА КНОПОК "В КОШИК" ТА "ОФОРМИТИ ЗАМОВЛЕННЯ"
// ==============================================================
function initProductActions() {
    document.addEventListener('click', e => {
        // Кнопка "В кошик"
        if (e.target.closest('.add-to-cart')) {
            const productElement = e.target.closest('[data-id]');
            if (!productElement) return;
            const productId = productElement.dataset.id;

            fetch('/add_to_cart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId })
            })
            .then(res => res.json())
            .then(data => {
                if(data.status === 'success') {
                    showToast('Товар додано до кошика');
                    updateCartView();
                }
            });
        }

        // Кнопка "Оформити замовлення"
        if (e.target.closest('.buy-now-btn')) {
            const productElement = e.target.closest('[data-id]');
            if (!productElement) return;
            const productId = productElement.dataset.id;

            fetch('/buy_now', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId })
            })
            .then(res => res.json())
            .then(data => {
                if(data.status === 'success') {
                    // Перенаправляємо на сторінку оформлення
                    window.location.href = '/checkout';
                }
            });
        }
    });
}

function updateCartView() {
    fetch('/get_cart')
    .then(res => res.json())
    .then(data => {
        const totalItems = data.items.reduce((sum, item) => sum + item.quantity, 0);
        const cartCount = document.getElementById('cart-count');
        if (cartCount) cartCount.textContent = totalItems;

        const itemsContainer = document.querySelector('.cart-items-container');
        const totalEl = document.getElementById('cart-modal-total');
        if (!itemsContainer || !totalEl) return;

        if (totalItems > 0) {
            itemsContainer.innerHTML = data.items.map(item => `
                <div class="cart-item">
                    <img src="/static/img/products/${item.image}" alt="${item.name}" class="cart-item-img">
                    <div class="cart-item-info">
                        <h4>${item.name}</h4>
                        <p>${item.price.toFixed(2)} грн</p>
                    </div>
                    <div class="cart-item-controls">
                        <span>x ${item.quantity}</span>
                        <button class="remove-item" data-id="${item.id}">×</button>
                    </div>
                </div>
            `).join('');
        } else {
            itemsContainer.innerHTML = '<div class="empty-cart"><i class="fas fa-shopping-cart" style="font-size: 4rem; color: #e0e0e0;"></i><p style="margin-top: 1rem;">Ваш кошик порожній</p></div>';
        }
        totalEl.textContent = `${data.total.toFixed(2)} грн`;
    });
}

// ==============================================
//  ДОПОМІЖНА ФУНКЦІЯ (Сповіщення)
// ==============================================
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    if(type === 'error') toast.style.backgroundColor = 'var(--danger-color)';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }, 3000);
    }, 10);
}