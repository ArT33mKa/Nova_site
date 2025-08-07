// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // [НОВЕ] Отримуємо елемент затемнення один раз при завантаженні
    const pageOverlay = document.getElementById('page-overlay');

    // [НОВЕ] Універсальна функція для закриття всіх бічних панелей та затемнення
    function closeAllSidebars() {
        document.querySelector('.cart-sidebar.active')?.classList.remove('active');
        document.querySelector('.cabinet-sidebar.active')?.classList.remove('active');
        if (pageOverlay) {
            pageOverlay.classList.remove('active');
            pageOverlay.classList.remove('dark'); // Скидаємо модифікатор темного фону
        }
    }

    // Ініціалізація всіх основних модулів
    initAuth();
    initHeaderActions(pageOverlay, closeAllSidebars); // [ЗМІНЕНО] Передаємо залежності
    initContactForm();
    initCatalogFilters();
    initReviewsPage();
    initHeroSlider();
    initSimilarProductsCarousel();
    initProductDescriptionToggle();
    initOptimizedCartLogic();
    initFavoritesLogic();
    initCabinetModal(pageOverlay, closeAllSidebars); // [ЗМІНЕНО] Передаємо залежності

    setupPhoneMaskAdvanced('#customer_phone');
    setupPhoneMaskAdvanced('#register_phone');
    initLoadMore();
    initShowMoreFilters();
    updateCartView();
    updateFavoritesUI();

    // [НОВЕ] Обробник кліку на саме затемнення для закриття панелей
    if (pageOverlay) {
        pageOverlay.addEventListener('click', closeAllSidebars);
    }
});


// ===================================================================
//  ЛОГІКА КАБІНЕТУ ТА АВТОРИЗАЦІЇ
// ===================================================================

function initAuth() {
    const authModal = document.getElementById('auth-modal');
    if (!authModal) return;

    document.getElementById('open-auth-modal-login')?.addEventListener('click', () => {
        switchAuthTab('login');
        authModal.classList.add('active');
    });

    document.getElementById('open-auth-modal-register')?.addEventListener('click', () => {
        switchAuthTab('register');
        authModal.classList.add('active');
    });

    authModal.addEventListener('click', e => {
        if (e.target.classList.contains('close-modal') || e.target.id === 'auth-modal') {
            authModal.classList.remove('active');
        }
    });

    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', () => switchAuthTab(tab.dataset.tab));
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

function switchAuthTab(tabId) {
    document.querySelectorAll('.auth-tab, .tab-content').forEach(el => el.classList.remove('active'));
    document.querySelector(`.auth-tab[data-tab="${tabId}"]`)?.classList.add('active');
    document.getElementById(tabId)?.classList.add('active');
}

// [ЗМІНЕНО] Функція тепер приймає залежності
function initCabinetModal(pageOverlay, closeAllSidebars) {
    const cabinetModal = document.getElementById('cabinet-modal');
    if (!cabinetModal) return;

    document.getElementById('open-cabinet-modal')?.addEventListener('click', () => {
        cabinetModal.classList.add('active');
        if (pageOverlay) {
            pageOverlay.classList.add('active');
            pageOverlay.classList.add('dark'); // Темне затемнення для кабінету
        }
    });

    // [ЗМІНЕНО] Використовуємо універсальну функцію закриття
    cabinetModal.addEventListener('click', e => {
        if (e.target.classList.contains('cabinet-close') || e.target.id === 'cabinet-modal') {
            closeAllSidebars();
        }
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

// [ЗМІНЕНО] Функція тепер приймає залежності
function initHeaderActions(pageOverlay, closeAllSidebars) {
    const cartModal = document.getElementById('cart-modal');
    if(!cartModal) return;

    document.getElementById('open-cart-btn')?.addEventListener('click', () => {
        updateCartView();
        cartModal.classList.add('active');
        if (pageOverlay) {
            pageOverlay.classList.add('active'); // Сіре затемнення (за замовчуванням)
        }
    });

    // [ЗМІНЕНО] Використовуємо універсальну функцію закриття
    cartModal.addEventListener('click', e => {
        if (e.target.matches('.close-modal') || e.target.id === 'cart-modal') {
            closeAllSidebars();
        }
    });
}

// ===================================================================
//  ІНША ЛОГІКА (без змін, просто залишаємо як є)
// ===================================================================
function initOptimizedCartLogic() {
    document.body.addEventListener('click', e => {
        const button = e.target.closest('button');
        if (!button) return;

        const productId = button.dataset.id || button.closest('[data-id]')?.dataset.id;
        if (!productId) return;

        if (button.matches('.add-to-cart-btn') && !button.classList.contains('in-cart')) {
            setButtonAsInCart(button, true);
            updateCartCounter(1);
            showToast('Товар додано до кошика', 'success', `<a href="/checkout" class="btn btn-sm btn-primary">Оформити</a>`);
            fetch('/add_to_cart', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: productId })})
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

        if (button.matches('.buy-now-btn')) {
             fetch('/buy_now', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: productId })})
             .then(res => res.json()).then(data => { if(data.status === 'success') window.location.href = '/checkout'; });
        }

        if (button.matches('.qty-btn')) {
             const cartItemRow = button.closest('.cart-item');
             if (!cartItemRow) return;
             const quantityDisplay = cartItemRow.querySelector('.quantity-display');
             const currentQuantity = parseInt(quantityDisplay.textContent);
             const newQuantity = button.classList.contains('plus') ? currentQuantity + 1 : currentQuantity - 1;

             if (newQuantity >= 1) {
                updateCartView(); // Optimistic update
                fetch(`/update_cart_quantity/${productId}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({quantity: newQuantity}) });
             }
        }

        if (button.matches('.remove-item')) {
            const cartItemRow = button.closest('.cart-item');
            if (cartItemRow) {
                cartItemRow.style.transition = 'opacity 0.3s, transform 0.3s';
                cartItemRow.style.opacity = '0';
                cartItemRow.style.transform = 'translateX(50px)';
                setTimeout(() => updateCartView(), 300);
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
    if (isInCart) {
        button.classList.add('in-cart');
        button.innerHTML = '<i class="fas fa-check"></i> В кошику';
    } else {
        button.classList.remove('in-cart');
        button.innerHTML = 'Додати в кошик';
    }
}

function setupPhoneMaskAdvanced(selector) {
    const phoneInput = document.querySelector(selector);
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
    const slider = document.querySelector('.card-slider');
    if (!slider) return;

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

    dotsContainer.innerHTML = '';
    slides.forEach((_, i) => {
        const dot = document.createElement('button');
        dot.classList.add('dot');
        dot.addEventListener('click', () => {});
        dotsContainer.appendChild(dot);
    });
    const dots = dotsContainer.querySelectorAll('.dot');

    function updateSlider(direction = 'next') {
        clearInterval(autoPlayInterval);
        const prevIndex = (currentIndex - 1 + totalSlides) % totalSlides;
        const nextIndexFromCurrent = (currentIndex + 1) % totalSlides;
        const currentCenterSlide = slides[currentIndex];
        const currentLeftSlide = slides[prevIndex];
        const currentRightSlide = slides[nextIndexFromCurrent];
        slides.forEach(s => s.className = 'hero-slide');

        if (direction === 'next') {
            currentIndex = (currentIndex + 1) % totalSlides;
            const newRightIndex = (currentIndex + 1) % totalSlides;
            currentLeftSlide.classList.add('slide-exit');
            currentCenterSlide.classList.add('slide-left');
            currentRightSlide.classList.add('slide-center');
            if (totalSlides > 3) {
                slides[newRightIndex].classList.add('slide-new');
                setTimeout(() => { slides[newRightIndex].classList.remove('slide-new'); slides[newRightIndex].classList.add('slide-right'); }, 50);
            } else {
                 slides[newRightIndex].classList.add('slide-right');
            }
        } else {
            currentIndex = (currentIndex - 1 + totalSlides) % totalSlides;
            const newLeftIndex = (currentIndex - 1 + totalSlides) % totalSlides;
            currentRightSlide.classList.add('slide-exit');
            currentCenterSlide.classList.add('slide-right');
            currentLeftSlide.classList.add('slide-center');
            if (totalSlides > 3) {
                 slides[newLeftIndex].classList.add('slide-new');
                 setTimeout(() => { slides[newLeftIndex].classList.remove('slide-new'); slides[newLeftIndex].classList.add('slide-left'); }, 50);
            } else {
                 slides[newLeftIndex].classList.add('slide-left');
            }
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
        dots.forEach((dot, i) => dot.classList.toggle('active', i === currentIndex));
    }

    function startAutoPlay() {
        autoPlayInterval = setInterval(() => updateSlider('next'), 5000);
    }

    nextBtn.addEventListener('click', () => updateSlider('next'));
    prevBtn.addEventListener('click', () => updateSlider('prev'));

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

function initLoadMore() {
    const loadMoreBtn = document.getElementById('load-more-btn');
    const productsGrid = document.querySelector('.products-grid');
    const loadingSpinner = document.getElementById('loading-spinner');

    if (!loadMoreBtn || !productsGrid) {
        return;
    }

    let currentPage = 1;

    loadMoreBtn.addEventListener('click', () => {
        currentPage++;
        loadMoreBtn.style.display = 'none';
        if (loadingSpinner) loadingSpinner.style.display = 'block';

        const params = new URLSearchParams(window.location.search);
        params.set('page', currentPage);

        fetch(`/api/catalog/load_more?${params.toString()}`)
            .then(response => {
                const moreAvailable = response.headers.get('X-More-Available') === 'true';
                return response.text().then(html => ({ html, moreAvailable }));
            })
            .then(({ html, moreAvailable }) => {
                if (html.trim() !== "") {
                    productsGrid.insertAdjacentHTML('beforeend', html);
                }

                if (moreAvailable) {
                    loadMoreBtn.style.display = 'inline-block';
                } else {
                    loadMoreBtn.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error loading more products:', error);
                loadMoreBtn.style.display = 'inline-block';
            })
            .finally(() => {
                if (loadingSpinner) loadingSpinner.style.display = 'none';
            });
    });
}

function initShowMoreFilters() {
    document.querySelectorAll('.filter-options-list[data-show-limit]').forEach(list => {
        const limit = parseInt(list.dataset.showLimit, 10);
        const items = Array.from(list.children);

        if (items.length > limit) {
            // Ховаємо всі елементи, що перевищують ліміт
            for (let i = limit; i < items.length; i++) {
                items[i].style.display = 'none';
            }

            // Створюємо та додаємо кнопку
            const remainingCount = items.length - limit;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'show-more-filters-btn';
            button.textContent = `Ще ${remainingCount}`;
            list.insertAdjacentElement('afterend', button);

            // Додаємо обробник події для кнопки
            button.addEventListener('click', () => {
                for (let i = limit; i < items.length; i++) {
                    items[i].style.display = ''; // Повертаємо стандартне відображення
                }
                button.remove(); // Видаляємо кнопку після використання
            });
        }
    });
}

function initShowMoreFilters() {
    document.querySelectorAll('.filter-options-list[data-show-limit]').forEach(list => {
        const limit = parseInt(list.dataset.showLimit, 10);
        const items = Array.from(list.children);

        if (items.length > limit) {
            // Ховаємо всі елементи, що перевищують ліміт
            for (let i = limit; i < items.length; i++) {
                items[i].style.display = 'none';
            }

            // Створюємо та додаємо кнопку
            const remainingCount = items.length - limit;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'show-more-filters-btn';
            button.textContent = `Показати ще ${remainingCount}`;
            list.insertAdjacentElement('afterend', button);

            // Додаємо обробник події для кнопки
            button.addEventListener('click', () => {
                for (let i = limit; i < items.length; i++) {
                    items[i].style.display = ''; // Повертаємо стандартне відображення
                }
                button.remove(); // Видаляємо кнопку після використання
            });
        }
    });
}