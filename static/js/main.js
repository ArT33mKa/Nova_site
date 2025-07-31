// static/js/main.js (ФІНАЛЬНА ВЕРСІЯ 6.0 З ВИПРАВЛЕНОЮ МАСКОЮ)

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
    initCartLogic();
    initFavoritesLogic();

    // Ініціалізуємо єдину правильну маску для обох полів вводу телефону
    setupPhoneMaskAdvanced('#customer_phone');
    setupPhoneMaskAdvanced('#register_phone');

    updateCartView();
    updateAllProductButtonStates();
    updateFavoritesUI();
});

// ===================================================================
//  [ПОВНІСТЮ ПЕРЕПИСАНА І ВИПРАВЛЕНА ФУНКЦІЯ МАСКИ ТЕЛЕФОНУ]
// ===================================================================
function setupPhoneMaskAdvanced(selector) {
    const phoneInput = document.querySelector(selector);
    if (!phoneInput) return;

    const matrix = "+380 (__) ___-__-__";
    const prefixNumber = "380";

    const setCursorPosition = (pos, elem) => {
        // requestAnimationFrame допомагає уникнути "гонки" подій і стабілізує позиціонування
        requestAnimationFrame(() => {
            elem.focus();
            elem.setSelectionRange(pos, pos);
        });
    };

    const mask = (event) => {
        const { target, type } = event;
        let value = target.value.replace(/\D/g, ""); // Отримуємо тільки цифри
        let i = 0;

        // Гарантуємо, що префікс завжди на місці і не може бути видалений
        if (value.length < prefixNumber.length) {
            value = prefixNumber;
        }

        // Заново форматуємо рядок за матрицею
        let newValue = matrix.replace(/[_\d]/g, (a) => {
            if (i < value.length) {
                return value.charAt(i++);
            }
            return a; // Якщо цифри закінчилися, повертаємо символ матриці ('_' або цифру)
        });

        // Знаходимо наступну позицію для курсора
        i = newValue.indexOf("_");
        if (i === -1) { // якщо символів '_' не залишилось, курсор ставимо в кінець
            i = newValue.length;
        }

        target.value = newValue;

        // При будь-якій взаємодії (введення, клік, фокус) ставимо курсор на правильне місце
        if (type !== 'blur') {
            setCursorPosition(i, target);
        }
    };

    phoneInput.addEventListener("input", mask);
    phoneInput.addEventListener("focus", mask);
    phoneInput.addEventListener("click", mask);

    // Очищуємо поле, якщо користувач пішов з нього, так і не ввівши номер
    phoneInput.addEventListener("blur", (e) => {
        if (e.target.value.replace(/\D/g, "") === prefixNumber) {
            e.target.value = "";
        }
    });

    // Додаткова обробка Backspace для запобігання видалення префіксу
    phoneInput.addEventListener("keydown", (e) => {
        if (e.key === 'Backspace' && e.target.value.replace(/\D/g, "").length <= prefixNumber.length) {
            e.preventDefault();
        }
    });
}

// ===================================================================
//  РЕШТА ФУНКЦІЙ (без змін)
// ===================================================================

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

function initCartLogic() {
    document.body.addEventListener('click', e => {
        const button = e.target.closest('button');
        if (!button) return;
        const productId = button.dataset.id || button.closest('[data-id]')?.dataset.id;
        const actions = {
            '.add-to-cart-btn': () => {
                if (!button.classList.contains('in-cart') && productId) {
                    const checkoutBtn = `<a href="/checkout" class="btn btn-sm btn-primary">Оформити</a>`;
                    fetchApi('/add_to_cart', { product_id: productId })
                        .then(() => showToast('Товар додано до кошика', 'success', checkoutBtn));
                }
            },
            '.buy-now-btn': () => {
                 if (!productId) return;
                 fetch('/buy_now', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: productId })})
                 .then(res => res.json()).then(data => { if(data.status === 'success') window.location.href = '/checkout'; });
            },
            '.qty-btn.plus': () => {
                if (!productId) return;
                const newQuantity = parseInt(button.previousElementSibling.textContent) + 1;
                fetchApi(`/update_cart_quantity/${productId}`, { quantity: newQuantity });
            },
            '.qty-btn.minus': () => {
                if (!productId) return;
                const currentQuantity = parseInt(button.nextElementSibling.textContent);
                if (currentQuantity <= 1) return;
                const newQuantity = currentQuantity - 1;
                fetchApi(`/update_cart_quantity/${productId}`, { quantity: newQuantity });
            },
            '.remove-item': () => {
                if (productId) fetchApi(`/remove_from_cart/${productId}`, null, 'POST');
            }
        };
        for (const selector in actions) {
            if (button.matches(selector)) { actions[selector](); break; }
        }
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
    });
}

function updateAllProductButtonStates() {
    fetch('/get_cart').then(res => res.json()).then(data => {
        const cartProductIds = new Set(data.items.map(item => String(item.id)));
        document.querySelectorAll('.add-to-cart-btn').forEach(button => {
            const productId = button.closest('[data-id]')?.dataset.id;
            if (productId) {
                if (cartProductIds.has(productId)) {
                    button.classList.add('in-cart');
                    button.innerHTML = '<i class="fas fa-check"></i> В кошику';
                } else {
                    button.classList.remove('in-cart');
                    button.innerHTML = button.innerHTML.includes('fa-shopping-cart') ? '<i class="fas fa-shopping-cart"></i> В кошик' : 'Додати в кошик';
                }
            }
        });
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
        updateAllProductButtonStates();
    });
}

function fetchApi(url, body, method = 'POST') {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);
    return fetch(url, options).then(res => res.json()).then(data => {
        if (data.status !== 'success') showToast(data.message || 'Сталася помилка', 'error');
        updateCartView();
        updateAllProductButtonStates();
    }).catch(err => { console.error('API Error:', err); showToast('Мережева помилка', 'error'); });
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

function initCatalogFilters() {
    const showMoreBtn = document.getElementById('show-more-brands-btn');
    if (showMoreBtn) {
        showMoreBtn.addEventListener('click', function() {
            const list = this.previousElementSibling;
            const isExpanded = this.dataset.expanded === 'true';
            if (isExpanded) {
                list.querySelectorAll('.brand-item').forEach((item, index) => { if (index >= 5) item.classList.add('hidden'); });
                this.textContent = 'Показати більше';
                this.dataset.expanded = 'false';
            } else {
                list.querySelectorAll('.brand-item.hidden').forEach(item => item.classList.remove('hidden'));
                this.textContent = 'Приховати';
                this.dataset.expanded = 'true';
            }
        });
        const list = showMoreBtn.previousElementSibling;
        list.querySelectorAll('.brand-item').forEach((item, index) => { if (index >= 5) item.classList.add('hidden'); });
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