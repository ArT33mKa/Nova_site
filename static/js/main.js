// static/js/main.js (ПОВНІСТЮ ВИПРАВЛЕНА ТА РОБОЧА ВЕРСІЯ)

document.addEventListener('DOMContentLoaded', function() {
    // Ініціалізація всіх основних модулів
    initAuth();
    initHeaderActions();
    initContactForm();
    initCatalogFilters();
    initReviewsPage();
    initHeroSlider();
    initSimilarProductsCarousel();
    initProductDescriptionToggle();
    // Централізована ініціалізація для кошика та обраного
    initCartLogic();
    initFavoritesLogic();

    // Початкове оновлення UI при завантаженні сторінки
    updateCartView();
    updateAllProductButtonStates();
    updateFavoritesUI();
});

function initProductDescriptionToggle() {
    const wrapper = document.getElementById('description-wrapper');
    const btn = document.getElementById('toggle-description-btn');

    // Перевіряємо, чи ми на сторінці товару (чи існують ці елементи)
    if (!wrapper || !btn) {
        return;
    }

    // Перевіряємо, чи текст довший за встановлену висоту.
    // Якщо ні, то кнопка "Читати далі" не потрібна.
    // 125 - це трохи більше за max-height (120px) з CSS, щоб врахувати похибку.
    if (wrapper.scrollHeight > 125) {
        btn.style.display = 'inline-block'; // Показуємо кнопку
    } else {
        // Якщо текст короткий, прибираємо ефект згасання
        wrapper.style.maxHeight = 'none';
        const afterElementStyle = getComputedStyle(wrapper, '::after');
        if (afterElementStyle) {
            wrapper.style.setProperty('--after-opacity', '0'); // приклад, як можна міняти псевдо-елемент
            wrapper.classList.add('is-short'); // кращий варіант
        }
    }
     if (wrapper.scrollHeight <= 125) {
        btn.style.display = 'none';
        wrapper.style.maxHeight = 'none';
        wrapper.classList.add('no-fade'); // Додамо клас, щоб прибрати градієнт
        return;
    }


    btn.addEventListener('click', function() {
        // Перемикаємо клас 'expanded' на контейнері з текстом
        const isExpanded = wrapper.classList.toggle('expanded');

        // Змінюємо текст на кнопці
        if (isExpanded) {
            btn.textContent = 'Приховати';
        } else {
            btn.textContent = 'Читати далі';
        }
    });
}

// ===================================================================
//  ЛОГІКА КОШИКА
// ===================================================================

function initCartLogic() {
    document.body.addEventListener('click', e => {
        const button = e.target.closest('button');
        if (!button) return;

        const productId = button.dataset.id || button.closest('[data-id]')?.dataset.id;

        const actions = {
            '.add-to-cart-btn': () => {
                if (!button.classList.contains('in-cart') && productId) {
                    fetchApi('/add_to_cart', { product_id: productId }).then(() => showToast('Товар додано до кошика'));
                }
            },
            '.buy-now-btn': () => {
                 if (!productId) return;
                 fetch('/buy_now', {
                     method: 'POST',
                     headers: { 'Content-Type': 'application/json' },
                     body: JSON.stringify({ product_id: productId })
                 })
                 .then(res => res.json())
                 .then(data => {
                     if(data.status === 'success') {
                         window.location.href = '/checkout';
                     }
                 });
            },
            '.qty-btn.plus': () => {
                if (!productId) return;
                const newQuantity = parseInt(button.previousElementSibling.textContent) + 1;
                fetchApi(`/update_cart_quantity/${productId}`, { quantity: newQuantity });
            },
            '.qty-btn.minus': () => {
                if (!productId) return;
                const newQuantity = parseInt(button.nextElementSibling.textContent) - 1;
                fetchApi(`/update_cart_quantity/${productId}`, { quantity: newQuantity });
            },
            '.remove-item': () => {
                if (productId) fetchApi(`/remove_from_cart/${productId}`, null, 'POST');
            }
        };

        for (const selector in actions) {
            if (button.matches(selector)) {
                actions[selector]();
                break;
            }
        }
    });
}

function updateCartView() {
    fetch('/get_cart')
        .then(res => res.json())
        .then(data => {
            const totalItems = data.items.reduce((sum, item) => sum + item.quantity, 0);
            document.getElementById('cart-count').textContent = totalItems;

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
                    const itemHtml = `
                    <div class="cart-item" data-id="${item.id}">
                        <a href="${item.url}" class="cart-item-link"><img src="/static/img/products/${item.image}" alt="${item.name}" class="cart-item-img"></a>
                        <div class="cart-item-info">
                            <a href="${item.url}" class="cart-item-link"><h4>${item.name}</h4></a>
                            <p class="cart-item-price">${item.price.toFixed(2)} ₴</p>
                            <p class="cart-item-stock ${stockClass}">${stockText}</p>
                        </div>
                        <div class="cart-item-sidebar-controls">
                            <div class="cart-item-quantity-controls">
                                <button class="qty-btn minus" data-id="${item.id}">-</button>
                                <span class="quantity-display">${item.quantity}</span>
                                <button class="qty-btn plus" data-id="${item.id}">+</button>
                            </div>
                            <button class="remove-item" data-id="${item.id}" title="Видалити">×</button>
                        </div>
                    </div>`;
                    itemsContainer.insertAdjacentHTML('beforeend', itemHtml);
                });
            } else {
                checkoutLink.style.display = 'none';
                itemsContainer.innerHTML = '<div class="empty-cart-message"><i class="fas fa-shopping-cart"></i><p>Ваш кошик порожній</p></div>';
            }
            totalEl.textContent = `${data.total.toFixed(2)} ₴`;
        });
}

function updateAllProductButtonStates() {
    fetch('/get_cart')
        .then(res => res.json())
        .then(data => {
            const cartProductIds = new Set(data.items.map(item => String(item.id)));
            document.querySelectorAll('.add-to-cart-btn').forEach(button => {
                const productId = button.closest('[data-id]')?.dataset.id;
                if (productId) {
                    if (cartProductIds.has(productId)) {
                        button.classList.add('in-cart');
                        button.innerHTML = '<i class="fas fa-check"></i> В кошику';
                    } else {
                        button.classList.remove('in-cart');
                         if (button.innerHTML.includes('fa-shopping-cart')) {
                            button.innerHTML = '<i class="fas fa-shopping-cart"></i> В кошик';
                        } else {
                             button.textContent = 'Додати в кошик';
                        }
                    }
                }
            });
        });
}

// ===================================================================
//  ЛОГІКА ОБРАНОГО
// ===================================================================

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

    fetch('/get_products_by_ids', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: favoriteIds })
    })
    .then(res => res.json())
    .then(products => {
        products.forEach(p => {
            const stockStatus = p.in_stock
                ? `<div class="stock-status in-stock">Є в наявності</div>`
                : `<div class="stock-status out-of-stock">Немає в наявності</div>`;

            // [ОНОВЛЕНО] Генерація адмін-кнопок на основі глобальної змінної
            let adminActionsHtml = '';
            if (window.isAdmin) {
                adminActionsHtml = `
                <div class="admin-product-actions">
                    <a href="/admin/edit_product/${p.id}" class="admin-action-btn edit-btn" title="Редагувати">
                        <i class="fas fa-pencil-alt"></i>
                    </a>
                    <form action="/admin/delete_product/${p.id}" method="POST" onsubmit="return confirm('Ви впевнені, що хочете видалити цей товар?');">
                        <button type="submit" class="admin-action-btn delete-btn" title="Видалити">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </form>
                </div>`;
            }

            const cardHtml = `
            <div class="product-card" data-id="${p.id}">
                <div class="product-image">
                    <a href="${p.url}"><img src="/static/img/products/${p.image}" alt="${p.name}"></a>
                    ${stockStatus}
                    <button class="favorite-btn active" title="Видалити з обраного"><i class="fas fa-star"></i></button>
                    ${adminActionsHtml} <!-- Вставляємо адмін-кнопки сюди -->
                </div>
                <div class="product-info">
                    <h3><a href="${p.url}">${p.name}</a></h3>
                    <p class="product-brand">${p.brand}</p>
                    <div class="product-footer">
                        <span class="price">${p.price.toFixed(2)} ₴</span>
                        <button class="btn btn-sm add-to-cart-btn" data-id="${p.id}" ${p.in_stock ? '' : 'disabled'}>Додати в кошик</button>
                    </div>
                </div>
            </div>`;
            container.insertAdjacentHTML('beforeend', cardHtml);
        });
        updateAllProductButtonStates();
    });
}


// ===================================================================
//  ІНШІ ІНІЦІАЛІЗАТОРИ ТА ДОПОМІЖНІ ФУНКЦІЇ
// ===================================================================

function fetchApi(url, body, method = 'POST') {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    return fetch(url, options)
        .then(res => res.json())
        .then(data => {
            if (data.status !== 'success') showToast(data.message || 'Сталася помилка', 'error');
            updateCartView();
            updateAllProductButtonStates();
        })
        .catch(err => {
            console.error('API Error:', err);
            showToast('Мережева помилка', 'error');
        });
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;
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

function initAuth() {
    const authModal = document.getElementById('auth-modal');
    if (!authModal) return;
    document.getElementById('open-auth-modal')?.addEventListener('click', () => authModal.classList.add('active'));
    authModal.addEventListener('click', e => {
        if (e.target.classList.contains('close-modal') || e.target.id === 'auth-modal') {
            authModal.classList.remove('active');
        }
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
                .then(res => res.json())
                .then(result => {
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
        if (e.target.matches('.close-modal') || e.target.id === 'cart-modal') {
            cartModal.classList.remove('active');
        }
    });
}

function initContactForm() {
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            fetch('/send_message', { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    showToast(data.message, data.status === 'success' ? 'success' : 'error');
                    if (data.status === 'success') this.reset();
                })
                .catch(() => showToast('Сталася помилка при відправці.', 'error'));
        });
    }
}

function initCatalogFilters() {
    const showMoreBtn = document.getElementById('show-more-brands-btn');
    if (showMoreBtn) {
        showMoreBtn.addEventListener('click', function() {
            const list = this.previousElementSibling;
            const hiddenItems = list.querySelectorAll('.brand-item.hidden');
            const isExpanded = this.dataset.expanded === 'true';

            if (isExpanded) {
                // Collapse
                list.querySelectorAll('.brand-item').forEach((item, index) => {
                    if (index >= 5) item.classList.add('hidden');
                });
                this.textContent = 'Показати більше';
                this.dataset.expanded = 'false';
            } else {
                // Expand
                hiddenItems.forEach(item => item.classList.remove('hidden'));
                this.textContent = 'Приховати';
                this.dataset.expanded = 'true';
            }
        });

        // Initial hide
        const list = showMoreBtn.previousElementSibling;
        list.querySelectorAll('.brand-item').forEach((item, index) => {
            if (index >= 5) item.classList.add('hidden');
        });
    }
}


function initReviewsPage() {
    const openModal = modal => modal?.classList.add('active');
    const closeModalOnClick = modal => {
        modal?.addEventListener('click', e => {
            if (e.target.classList.contains('close-modal') || e.target.id === modal.id) {
                 modal.classList.remove('active');
            }
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
    const itemWidth = track.children[0].offsetWidth + 20; // 20 - gap
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