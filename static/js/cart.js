document.addEventListener('DOMContentLoaded', () => {
  const cartIcon = document.getElementById('cart-icon');
  const cartCountBadge = document.getElementById('cart-count');
  const cartModal = document.getElementById('cart-modal');
  const cartItemsUl = document.getElementById('cart-modal-items');
  const cartTotalEl = document.getElementById('cart-total');
  const cartCheckoutBtn = document.getElementById('cart-checkout');
  const closeCartModal = document.getElementById('close-cart-modal');
  const toast = document.getElementById('toast');

  let cart = JSON.parse(localStorage.getItem('cart')) || [];

  if (cartIcon) {
    cartIcon.addEventListener('click', () => {
      renderCartModal();
      cartModal.classList.remove('hidden');
    });
  }

  if (closeCartModal) {
    closeCartModal.addEventListener('click', () => {
      cartModal.classList.add('hidden');
    });
  }

  if (cartCheckoutBtn) {
    cartCheckoutBtn.addEventListener('click', () => {
      if (!cart.length) return alert('Кошик порожній');
      showToast('✅ Товари готові до оформлення');
    });
  }

  function renderCartModal() {
    if (!cartItemsUl || !cartTotalEl) return;
    cartItemsUl.innerHTML = '';
    if (!cart.length) {
      cartItemsUl.innerHTML = '<li class="empty">Кошик порожній</li>';
      cartTotalEl.innerHTML = '<strong>Разом:</strong> 0&nbsp;грн';
      return;
    }

    cart.forEach((item, idx) => {
      const li = document.createElement('li');
      li.className = 'cart-item';
      li.innerHTML = `
        <img src="/static/img/${item.image}" alt="${item.name}">
        <div class="item-info">
          <h4>${item.name}</h4>
          <p>${item.price}&nbsp;грн · <span style="color:#4caf50">в&nbsp;наявності</span></p>
        </div>
        <div class="qty-controls">
          <button class="qty-btn minus" data-idx="${idx}">−</button>
          <span class="qty">${item.qty}</span>
          <button class="qty-btn plus" data-idx="${idx}">+</button>
        </div>
        <button class="remove-item" data-idx="${idx}">🗑️</button>
      `;
      cartItemsUl.appendChild(li);
    });

    updateTotal();
  }

  if (cartItemsUl) {
    cartItemsUl.addEventListener('click', e => {
      const idx = +e.target.dataset.idx;
      if (isNaN(idx)) return;

      if (e.target.classList.contains('plus')) cart[idx].qty++;
      else if (e.target.classList.contains('minus')) cart[idx].qty > 1 ? cart[idx].qty-- : cart.splice(idx, 1);
      else if (e.target.classList.contains('remove-item')) cart.splice(idx, 1);

      persistCart();
    });
  }

  function persistCart() {
    localStorage.setItem('cart', JSON.stringify(cart));
    updateBadge();
    if (!cartModal.classList.contains('hidden')) renderCartModal();
  }

  function updateTotal() {
    const total = cart.reduce((sum, i) => sum + i.price * i.qty, 0);
    cartTotalEl.innerHTML = `<strong>Разом:</strong> ${total}&nbsp;грн`;
  }

  function updateBadge() {
    const count = cart.reduce((sum, i) => sum + i.qty, 0);
    if (cartCountBadge) cartCountBadge.textContent = count;
  }

  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.remove('hidden');
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
  }

  updateBadge();
});
