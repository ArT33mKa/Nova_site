document.addEventListener('DOMContentLoaded', function() {
    const pageOverlay = document.getElementById('page-overlay');

    function closeAllSidebars() {
        document.querySelector('.cart-sidebar.active')?.classList.remove('active');
        document.querySelector('.cabinet-sidebar.active')?.classList.remove('active');
        if (pageOverlay) {
            pageOverlay.classList.remove('active', 'dark');
        }
    }

    // Ініціалізація всіх модулів
    initAuth();
    initHeaderActions(pageOverlay, closeAllSidebars);
    initContactForm();
    initCatalogPage();
    initReviewsPage();
    initHeroSlider();
    initSimilarProductsCarousel();
    initProductDescriptionToggle();
    initCartLogic();
    initFavoritesLogic();
    initCabinetModal(pageOverlay, closeAllSidebars);

    // Ініціалізація масок для телефонів
    setupPhoneMaskAdvanced('#customer_phone');
    setupPhoneMaskAdvanced('#register_phone');
    setupPhoneMaskAdvanced('#profile_phone'); // Додано для сторінки налаштувань

    // Початкове оновлення UI
    updateCartView();
    updateFavoritesUI();

    if (pageOverlay) {
        pageOverlay.addEventListener('click', closeAllSidebars);
    }
});


// ===================================================================
//  1. AUTH & USER CABINET
// ===================================================================
function initAuth() {
    const authModal = document.getElementById('auth-modal');
    if (!authModal) return;

    function openAuthModal(tab) {
        switchAuthTab(tab);
        authModal.classList.add('active');
    }

    document.getElementById('open-auth-modal-login')?.addEventListener('click', () => openAuthModal('login'));
    document.getElementById('open-auth-modal-register')?.addEventListener('click', () => openAuthModal('register'));

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
        if (!form) return;
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(this).entries());
            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(result => {
                if (result.status === 'success') {
                    window.location.reload();
                } else {
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

function initCabinetModal(pageOverlay, closeAllSidebars) {
    const cabinetModal = document.getElementById('cabinet-modal');
    if (!cabinetModal) return;

    document.getElementById('open-cabinet-modal')?.addEventListener('click', () => {
        cabinetModal.classList.add('active');
        if (pageOverlay) {
            pageOverlay.classList.add('active', 'dark');
        }
    });

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

// ===================================================================
//  2. CART & FAVORITES
// ===================================================================
function initCartLogic() {
    document.body.addEventListener('click', e => {
        const button = e.target.closest('button');
        if (!button) return;

        const productId = button.dataset.id || button.closest('[data-id]')?.dataset.id;
        if (!productId) return;

        if (button.matches('.add-to-cart-btn') && !button.disabled) {
            fetch('/add_to_cart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId })
            }).then(() => {
                updateCartView();
                showToast('Товар додано до кошика', 'success');
            });
        }

        if (button.matches('.buy-now-btn')) {
            fetch('/buy_now', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId })
            })
            .then(res => res.json())
            .then(data => { if(data.status === 'success') window.location.href = '/checkout'; });
        }

        if (button.matches('.qty-btn')) {
            const cartItemRow = button.closest('.cart-item');
            if (cartItemRow) {
                const quantityDisplay = cartItemRow.querySelector('.quantity-display');
                const currentQuantity = parseInt(quantityDisplay.textContent);
                const newQuantity = button.classList.contains('plus') ? currentQuantity + 1 : currentQuantity - 1;
                if (newQuantity >= 1) {
                    updateCartQuantity(productId, newQuantity);
                }
            }
        }

        if (button.matches('.remove-item')) {
            const cartItemRow = button.closest('.cart-item');
            if (cartItemRow) {
                cartItemRow.style.opacity = '0';
                setTimeout(() => {
                    fetch(`/remove_from_cart/${productId}`, { method: 'POST' }).then(() => updateCartView());
                }, 300);
            }
        }
    });
}

function updateCartQuantity(productId, quantity) {
    fetch(`/update_cart_quantity/${productId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ quantity: quantity })
    }).then(() => updateCartView());
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
            checkoutLink.style.display = 'flex';
            data.items.forEach(item => {
                itemsContainer.insertAdjacentHTML('beforeend', `
                <div class="cart-item" data-id="${item.id}" style="opacity:1; transition: opacity 0.3s;">
                    <a href="${item.url}" class="cart-item-link"><img src="${item.image}" alt="${item.name}" class="cart-item-img"></a>
                    <div class="cart-item-info">
                        <a href="${item.url}" class="cart-item-link"><h4>${item.name}</h4></a>
                        <p class="cart-item-price">${item.price.toFixed(2)} ₴</p>
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
                button.innerHTML = isLargeButton ? '<i class="fas fa-check"></i> Вже в кошику' : '<i class="fas fa-check"></i>';
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

    fetch('/get_products_by_ids', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: favoriteIds })
    })
    .then(res => res.json())
    .then(products => {
        products.forEach(p => {
            const productCardHtml = `
            <div class="product-card" data-id="${p.id}">
                <div class="product-image">
                    <a href="${p.url}">
                        <img src="${p.image}" alt="${p.name}">
                    </a>
                    ${p.in_stock ? '<div class="stock-status in-stock">Є в наявності</div>' : '<div class="stock-status out-of-stock">Немає в наявності</div>'}
                    <button class="favorite-btn active" title="Видалити з обраного"><i class="fas fa-star"></i></button>
                </div>
                <div class="product-info">
                    <h3><a href="${p.url}">${p.name}</a></h3>
                    <div class="product-footer">
                        <span class="price">${p.price.toFixed(2)} ₴</span>
                        <button class="btn btn-sm add-to-cart-btn" data-id="${p.id}" ${!p.in_stock ? 'disabled' : ''}>
                            Додати в кошик
                        </button>
                    </div>
                </div>
            </div>`;
            container.insertAdjacentHTML('beforeend', productCardHtml);
        });
        updateCartView(); // To update button states
    });
}

// ===================================================================
//  3. PAGE-SPECIFIC LOGIC & UI
// ===================================================================
function initHeaderActions(pageOverlay, closeAllSidebars) {
    const cartModal = document.getElementById('cart-modal');
    if (!cartModal) return;

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

function initContactForm() {
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const submitBtn = this.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            fetch('/send_message', { method: 'POST', body: new FormData(this) })
            .then(response => response.json())
            .then(data => {
                showToast(data.message, data.status === 'success' ? 'success' : 'error');
                if (data.status === 'success') this.reset();
            })
            .catch(() => showToast('Сталася помилка при відправці.', 'error'))
            .finally(() => { submitBtn.disabled = false; });
        });
    }
}

function initCatalogPage() {
    // Logic for filters can be added here if needed
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
    const slider = document.querySelector('.card-slider');
    if (!slider) return;

    const slides = Array.from(slider.querySelectorAll('.hero-slide'));
    const prevBtn = document.querySelector('.card-slider-wrapper .prev-btn');
    const nextBtn = document.querySelector('.card-slider-wrapper .next-btn');
    const dotsContainer = document.querySelector('.card-slider-wrapper .slider-dots');
    const totalSlides = slides.length;

    if (totalSlides <= 1) {
        if (prevBtn) prevBtn.style.display = 'none';
        if (nextBtn) nextBtn.style.display = 'none';
        if (dotsContainer) dotsContainer.style.display = 'none';
        return;
    }

    let currentIndex = 0;
    let autoPlayInterval;

    dotsContainer.innerHTML = slides.map((_, i) => `<button class="dot ${i === 0 ? 'active' : ''}"></button>`).join('');
    const dots = dotsContainer.querySelectorAll('.dot');
    dots.forEach((dot, i) => dot.addEventListener('click', () => goToSlide(i)));

    function updateSliderPositions() {
        slides.forEach((slide, i) => {
            let className = 'hero-slide';
            if (i === currentIndex) {
                className += ' slide-center';
            } else if (i === (currentIndex - 1 + totalSlides) % totalSlides) {
                className += ' slide-left';
            } else if (i === (currentIndex + 1) % totalSlides) {
                className += ' slide-right';
            }
            slide.className = className;
        });
        dots.forEach((d, i) => d.classList.toggle('active', i === currentIndex));
    }

    function goToSlide(index) {
        clearInterval(autoPlayInterval);
        currentIndex = index;
        updateSliderPositions();
        startAutoPlay();
    }

    function nextSlide() {
        goToSlide((currentIndex + 1) % totalSlides);
    }

    function prevSlide() {
        goToSlide((currentIndex - 1 + totalSlides) % totalSlides);
    }

    function startAutoPlay() {
        autoPlayInterval = setInterval(nextSlide, 5000);
    }

    nextBtn.addEventListener('click', nextSlide);
    prevBtn.addEventListener('click', prevSlide);

    updateSliderPositions();
    startAutoPlay();
}

function initSimilarProductsCarousel() {
    const container = document.querySelector('.similar-products-section');
    if (!container) return;
    const track = container.querySelector('.products-grid-carousel');
    const prevBtn = container.querySelector('.carousel-prev-btn');
    const nextBtn = container.querySelector('.carousel-next-btn');

    if (!track || !prevBtn || !nextBtn || track.children.length <= 4) {
       if (prevBtn) prevBtn.style.display = 'none';
       if (nextBtn) nextBtn.style.display = 'none';
       return;
    }

    let scrollAmount = 0;
    const itemWidth = track.children[0].offsetWidth + 20;
    const maxScroll = track.scrollWidth - track.clientWidth;

    const updateButtons = () => {
        prevBtn.disabled = scrollAmount < 10;
        nextBtn.disabled = scrollAmount > maxScroll - 10;
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

function initProductDescriptionToggle() {
    const wrapper = document.getElementById('description-wrapper');
    const btn = document.getElementById('toggle-description-btn');
    if (!wrapper || !btn) return;

    // Check if content is scrollable
    if (wrapper.scrollHeight > wrapper.clientHeight) {
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

// ===================================================================
//  4. HELPERS & UTILITIES
// ===================================================================
function setupPhoneMaskAdvanced(selector) {
    const phoneInput = document.querySelector(selector);
    if (!phoneInput) return;

    const matrix = "+380 (__) ___-__-__";
    const prefixNumber = "380";

    const setCursorPosition = (pos, elem) => {
        elem.focus();
        elem.setSelectionRange(pos, pos);
    };

    const applyMask = (event) => {
        let input = event.target;
        let value = input.value.replace(/\D/g, "");
        let i = 0;

        if (!value.startsWith(prefixNumber)) {
            value = prefixNumber + value.substring(prefixNumber.length);
        }

        let formattedValue = matrix.replace(/[_\d]/g, (char) => (i < value.length) ? value.charAt(i++) : char);

        // Find first underscore to place cursor
        let cursorPos = formattedValue.indexOf('_');
        if (cursorPos === -1) {
            cursorPos = formattedValue.length;
        }

        input.value = formattedValue;
        if (event.type !== 'blur') {
             setCursorPosition(cursorPos, input);
        }
    };

    phoneInput.addEventListener('input', applyMask, false);
    phoneInput.addEventListener('focus', applyMask, false);
    phoneInput.addEventListener('blur', (e) => {
        if (e.target.value.replace(/\D/g, "") === prefixNumber) {
            e.target.value = '';
        }
    }, false);
}

function showToast(message, type = 'success', actions = '') {
    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }, 3000);
    }, 10);
}