const menuItems = [
  { id: 'honey-chicken-rice', name: 'Cơm gà nướng mật ong', category: 'main', description: 'Gà nướng thơm, cơm lá dứa, đồ chua nhà làm.', price: 78000, image: 'photo-1534939561126-855b8675edd7' },
  { id: 'house-bun-bo', name: 'Bún bò nhà nấu', category: 'main', description: 'Nước dùng ninh chậm, rau thơm và chút sa tế.', price: 72000, image: 'photo-1569718212165-3a8278d5f624' },
  { id: 'caramelized-fish', name: 'Cá kho tộ', category: 'main', description: 'Cá kho niêu đất cùng tiêu xanh và nước màu dừa.', price: 89000, image: 'photo-1512621776951-a57141f2eefd' },
  { id: 'vegetable-fried-rice', name: 'Cơm rang rau củ', category: 'main', description: 'Cơm rang tơi với trứng, rau củ theo mùa.', price: 65000, image: 'photo-1512058564366-18510be2db19' },
  { id: 'shrimp-pork-rolls', name: 'Gỏi cuốn tôm thịt', category: 'snacks', description: 'Cuốn tay mỗi ngày, chấm sốt đậu phộng.', price: 42000, image: 'photo-1547592180-85f173990554' },
  { id: 'sweet-potato-fries', name: 'Khoai lang chiên', category: 'snacks', description: 'Khoai lang mật giòn bên ngoài, bùi bên trong.', price: 35000, image: 'photo-1573080496219-bb080dd4f877' },
  { id: 'banana-cake', name: 'Bánh chuối nướng', category: 'snacks', description: 'Bánh chuối thơm cốt dừa, nướng nóng tại bếp.', price: 38000, image: 'photo-1606313564200-e75d5e30476c' },
  { id: 'iced-milk-coffee', name: 'Cà phê sữa đá', category: 'drinks', description: 'Cà phê rang đậm, pha phin chậm rãi.', price: 32000, image: 'photo-1461023058943-07fcbe16d735' },
  { id: 'peach-orange-tea', name: 'Trà đào cam sả', category: 'drinks', description: 'Trà ủ lạnh, đào chín, cam tươi và sả thơm.', price: 39000, image: 'photo-1556679343-c7306c1976bc' },
  { id: 'passionfruit-juice', name: 'Nước chanh dây', category: 'drinks', description: 'Chanh dây tươi, chua ngọt vừa phải.', price: 35000, image: 'photo-1513558161293-cdaf765edfd7' },
];

const tabs = [...document.querySelectorAll('.menu-tab')];
const searchInput = document.querySelector('#menu-search');
const menuGrid = document.querySelector('#menu-grid');
const emptyState = document.querySelector('#empty-state');
const searchHint = document.querySelector('#search-hint');
const cartOpenButton = document.querySelector('#cart-open');
const cartOverlay = document.querySelector('#cart-overlay');
const cartDrawer = document.querySelector('.cart-drawer');
const cartCloseButton = document.querySelector('#cart-close');
const cartBackdrop = document.querySelector('#cart-backdrop');
const cartItemsElement = document.querySelector('#cart-items');
const cartEmptyElement = document.querySelector('#cart-empty');
const cartFooter = document.querySelector('#cart-footer');
const cartCountElement = document.querySelector('#cart-count');
const cartTotalElement = document.querySelector('#cart-total');
const cartSubtotalElement = document.querySelector('#cart-subtotal');
const cartDiscountLine = document.querySelector('#cart-discount-line');
const cartDiscountElement = document.querySelector('#cart-discount');
const cartMessage = document.querySelector('#cart-message');
const cartCheckout = document.querySelector('.cart-checkout');
const CART_STORAGE_KEY = 'bep-nha-cart-v1';
let activeCategory = 'main';
let cart = loadCart();

function normalizeText(value) {
  return value
    .toLocaleLowerCase('vi')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .trim();
}

function formatPrice(price) {
  return `${new Intl.NumberFormat('vi-VN').format(price)}đ`;
}

function menuImageUrl(image, width, quality = 73) {
  return `https://images.unsplash.com/${image}?auto=format&fit=crop&w=${width}&q=${quality}`;
}

function renderMenu() {
  const query = normalizeText(searchInput.value);
  const visibleItems = menuItems.filter((item) => {
    const matchesCategory = item.category === activeCategory;
    const matchesQuery = normalizeText(`${item.name} ${item.description}`).includes(query);
    return matchesCategory && matchesQuery;
  });

  menuGrid.innerHTML = visibleItems.map((item) => `
    <article class="menu-card">
      <div class="menu-card-image">
        <img src="${menuImageUrl(item.image, 480)}" srcset="${menuImageUrl(item.image, 360, 70)} 360w, ${menuImageUrl(item.image, 520, 72)} 520w, ${menuImageUrl(item.image, 760, 74)} 760w" sizes="(max-width: 767px) 46vw, (max-width: 1100px) 30vw, 24vw" width="760" height="520" alt="${item.name}" loading="lazy" decoding="async" />
      </div>
      <div class="menu-card-copy">
        <h3>${item.name}</h3>
        <p>${item.description}</p>
        <div class="menu-card-actions"><span class="menu-card-price">${formatPrice(item.price)}</span><button class="add-to-cart" type="button" data-add-item="${item.id}" aria-label="Thêm ${item.name} vào giỏ">+ Thêm</button></div>
      </div>
    </article>
  `).join('');

  emptyState.hidden = visibleItems.length > 0;
  menuGrid.hidden = visibleItems.length === 0;
  searchHint.hidden = query.length === 0;
}

function selectTab(tab, moveFocus = false) {
  activeCategory = tab.dataset.category;
  tabs.forEach((item) => {
    const isSelected = item === tab;
    item.classList.toggle('is-active', isSelected);
    item.setAttribute('aria-selected', String(isSelected));
    item.tabIndex = isSelected ? 0 : -1;
  });
  menuGrid.setAttribute('aria-labelledby', tab.id);
  if (moveFocus) tab.focus();
  renderMenu();
}

tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTab(tab));
  tab.addEventListener('keydown', (event) => {
    let nextIndex = index;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === 'Home') nextIndex = 0;
    else if (event.key === 'End') nextIndex = tabs.length - 1;
    else return;
    event.preventDefault();
    selectTab(tabs[nextIndex], true);
  });
});

searchInput.addEventListener('input', renderMenu);
function loadCart() {
  try {
    const stored = JSON.parse(localStorage.getItem(CART_STORAGE_KEY) || '[]');
    if (!Array.isArray(stored)) return [];
    return stored
      .filter((line) => line && typeof line.id === 'string' && Number.isInteger(line.quantity) && line.quantity > 0)
      .map((line) => ({ id: line.id, quantity: Math.min(line.quantity, 99), price: line.price }));
  } catch {
    return [];
  }
}

function persistCart() {
  try {
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
  } catch {
    cartMessage.textContent = 'Không lưu được giỏ trên thiết bị này.';
  }
}

function reconcileCart() {
  const currentItems = new Map(menuItems.map((item) => [item.id, item]));
  let removedItems = 0;
  let updatedPrices = 0;
  cart = cart.flatMap((line) => {
    const item = currentItems.get(line.id);
    if (!item) {
      removedItems += 1;
      return [];
    }
    if (line.price !== item.price) updatedPrices += 1;
    return [{ id: item.id, quantity: line.quantity, price: item.price }];
  });
  if (removedItems || updatedPrices) {
    persistCart();
    if (removedItems && updatedPrices) cartMessage.textContent = 'Món không còn đã được bỏ, giá các món khác được cập nhật.';
    else if (removedItems) cartMessage.textContent = 'Món không còn trong thực đơn đã được bỏ khỏi giỏ.';
    else cartMessage.textContent = 'Giá trong giỏ đã được cập nhật theo thực đơn mới.';
  }
}

function renderCart() {
  const quantity = cart.reduce((sum, line) => sum + line.quantity, 0);
  const localSubtotal = cart.reduce((sum, line) => sum + line.price * line.quantity, 0);
  const subtotal = verifiedOrderQuote?.subtotalVnd ?? localSubtotal;
  const discount = appliedVoucher
    ? (verifiedOrderQuote?.discountVnd ?? Math.floor(subtotal * 0.2))
    : 0;
  const total = verifiedOrderQuote?.totalVnd ?? (subtotal - discount);
  cartCountElement.textContent = quantity > 99 ? '99+' : String(quantity);
  cartOpenButton.setAttribute('aria-label', `Mở giỏ hàng, ${quantity} món`);
  cartSubtotalElement.textContent = formatPrice(subtotal);
  cartDiscountLine.hidden = !discount;
  cartDiscountElement.textContent = `−${formatPrice(discount)}`;
  cartTotalElement.textContent = formatPrice(total);
  cartEmptyElement.hidden = cart.length > 0;
  cartFooter.hidden = cart.length === 0;
  cartItemsElement.hidden = cart.length === 0;

  cartItemsElement.innerHTML = cart.map((line) => {
    const item = menuItems.find((menuItem) => menuItem.id === line.id);
    return `
      <article class="cart-line">
        <img src="${menuImageUrl(item.image, 180, 65)}" width="180" height="130" alt="" loading="lazy" decoding="async" />
        <div class="cart-line-info"><h3>${item.name}</h3><p>${formatPrice(item.price)} / món</p><div class="cart-quantity"><button class="quantity-button" type="button" data-quantity-change="-1" data-item-id="${item.id}" aria-label="Bớt một ${item.name}">−</button><span class="quantity-value">${line.quantity}</span><button class="quantity-button" type="button" data-quantity-change="1" data-item-id="${item.id}" aria-label="Thêm một ${item.name}">+</button></div></div>
        <div class="cart-line-end"><span class="cart-line-total">${formatPrice(item.price * line.quantity)}</span><button class="remove-item" type="button" data-remove-item="${item.id}">Xóa</button></div>
      </article>`;
  }).join('');
  renderOrderSummary();
}

function addToCart(id) {
  const item = menuItems.find((menuItem) => menuItem.id === id);
  if (!item) return;
  const line = cart.find((entry) => entry.id === id);
  if (line) line.quantity = Math.min(99, line.quantity + 1);
  else cart.push({ id: item.id, quantity: 1, price: item.price });
  persistCart();
  renderCart();
  cartMessage.textContent = `Đã thêm ${item.name} vào giỏ.`;
  revalidateAppliedVoucher();
}

function changeQuantity(id, delta) {
  const line = cart.find((entry) => entry.id === id);
  if (!line) return;
  line.quantity += delta;
  if (line.quantity <= 0) cart = cart.filter((entry) => entry.id !== id);
  persistCart();
  renderCart();
  revalidateAppliedVoucher();
}

function removeFromCart(id) {
  cart = cart.filter((line) => line.id !== id);
  persistCart();
  renderCart();
  cartMessage.textContent = 'Đã xóa món khỏi giỏ.';
  revalidateAppliedVoucher();
}

function openCart() {
  cartOverlay.hidden = false;
  document.body.classList.add('cart-is-open');
  cartCloseButton.focus();
}

function closeCart() {
  cartOverlay.hidden = true;
  document.body.classList.remove('cart-is-open');
  cartOpenButton.focus();
}

menuGrid.addEventListener('click', (event) => {
  const button = event.target.closest('[data-add-item]');
  if (button) addToCart(button.dataset.addItem);
});

cartItemsElement.addEventListener('click', (event) => {
  const quantityButton = event.target.closest('[data-quantity-change]');
  if (quantityButton) {
    changeQuantity(quantityButton.dataset.itemId, Number(quantityButton.dataset.quantityChange));
    return;
  }
  const removeButton = event.target.closest('[data-remove-item]');
  if (removeButton) removeFromCart(removeButton.dataset.removeItem);
});

cartOpenButton.addEventListener('click', openCart);
cartCloseButton.addEventListener('click', closeCart);
cartBackdrop.addEventListener('click', closeCart);
cartCheckout.addEventListener('click', closeCart);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !cartOverlay.hidden) closeCart();
});

const bookingForm = document.querySelector('#booking-form');
const bookingDate = document.querySelector('#booking-date');
const slotGrid = document.querySelector('#slot-grid');
const slotHelp = document.querySelector('#slot-help');
const slotOpeningNote = document.querySelector('#slot-opening-note');
const bookingResponse = document.querySelector('#booking-response');
const bookingSubmit = document.querySelector('#booking-submit');
const voucherCodeInput = document.querySelector('#voucher-code');
const voucherApplyButton = document.querySelector('#voucher-apply');
const voucherFeedback = document.querySelector('#voucher-feedback');
const voucherErrorsList = document.querySelector('#voucher-errors');
const orderSubtotalElement = document.querySelector('#order-subtotal');
const orderDiscountRow = document.querySelector('#order-discount-row');
const orderDiscountElement = document.querySelector('#order-discount');
const orderTotalElement = document.querySelector('#order-total');
let bookingSlots = [];
let selectedSlot = '';
let slotRequestNumber = 0;
let bookingConfig = null;
let appliedVoucher = '';
let voucherRequestNumber = 0;
let verifiedOrderQuote = null;
const BOOKING_RETRY_KEY = 'bep-nha-booking-retry-v1';

async function bookingRequestKeyFor(payloadText) {
  const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(payloadText));
  const fingerprint = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
  let pending = null;
  try { pending = JSON.parse(localStorage.getItem(BOOKING_RETRY_KEY) || 'null'); } catch { /* ignore invalid saved retry data */ }
  if (!pending || pending.fingerprint !== fingerprint || typeof pending.key !== 'string') {
    pending = {
      fingerprint,
      key: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    };
    try { localStorage.setItem(BOOKING_RETRY_KEY, JSON.stringify(pending)); } catch { /* server can still accept the request */ }
  }
  return pending.key;
}

function clearBookingRequestKey() {
  try { localStorage.removeItem(BOOKING_RETRY_KEY); } catch { /* ignore unavailable storage */ }
}

function renderOrderSummary() {
  const localSubtotal = cart.reduce((sum, line) => sum + line.price * line.quantity, 0);
  const subtotal = verifiedOrderQuote?.subtotalVnd ?? localSubtotal;
  const discount = appliedVoucher
    ? (verifiedOrderQuote?.discountVnd ?? Math.floor(subtotal * 0.2))
    : 0;
  orderSubtotalElement.textContent = formatPrice(subtotal);
  orderDiscountRow.hidden = !discount;
  orderDiscountElement.textContent = `−${formatPrice(discount)}`;
  orderTotalElement.textContent = formatPrice(subtotal - discount);
}

function displayVoucherErrors(errors) {
  voucherErrorsList.replaceChildren(...errors.map((error) => {
    const line = document.createElement('li');
    line.textContent = error;
    return line;
  }));
}

async function validateVoucher(code, mode = 'apply') {
  const requestNumber = ++voucherRequestNumber;
  const requestedCode = typeof code === 'string' ? code.trim().toUpperCase() : '';
  const date = bookingDate.value;
  const time = selectedSlot;
  if (!date || !time) {
    if (mode === 'recheck' && appliedVoucher) {
      const removedCode = appliedVoucher;
      appliedVoucher = '';
      verifiedOrderQuote = null;
      voucherCodeInput.value = '';
      voucherFeedback.textContent = `Mã ${removedCode} đã được gỡ vì chưa có khung giờ hợp lệ.`;
      renderCart();
    } else {
      voucherFeedback.textContent = 'Chọn ngày và giờ đến trước khi áp mã.';
    }
    displayVoucherErrors(['Chọn ngày và giờ đến trước khi áp mã.']);
    return false;
  }
  try {
    const response = await fetch('/api/vouchers/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: requestedCode,
        date,
        time,
        cart: cart.map(({ id, quantity }) => ({ id, quantity })),
      }),
    });
    const result = await response.json();
    if (requestNumber !== voucherRequestNumber) return false;
    if (!response.ok || !result.valid) {
      verifiedOrderQuote = null;
      if (mode === 'recheck' && appliedVoucher) {
        appliedVoucher = '';
        voucherCodeInput.value = '';
        voucherFeedback.textContent = `Mã ${appliedVoucher || requestedCode} đã được gỡ vì đơn không còn thỏa điều kiện:`;
        renderCart();
      } else {
        voucherFeedback.textContent = `Chưa áp dụng được mã ${requestedCode || 'ưu đãi'}:`;
      }
      displayVoucherErrors(result.errors || [result.error || 'Không xác minh được mã ưu đãi.']);
      renderOrderSummary();
      return false;
    }
    appliedVoucher = 'CHIEUVUI';
    verifiedOrderQuote = result;
    voucherCodeInput.value = 'CHIEUVUI';
    voucherFeedback.textContent = 'Đã áp dụng CHIEUVUI · giảm 20% trên giỏ hàng.';
    displayVoucherErrors([]);
    renderCart();
    return true;
  } catch {
    if (requestNumber !== voucherRequestNumber) return false;
    verifiedOrderQuote = null;
    if (mode === 'recheck' && appliedVoucher) {
      appliedVoucher = '';
      voucherCodeInput.value = '';
      voucherFeedback.textContent = 'Mã đã được gỡ vì không thể xác minh với máy chủ. Hãy áp dụng lại khi kết nối ổn định.';
      renderCart();
    } else {
      voucherFeedback.textContent = 'Không kết nối được máy chủ để kiểm tra mã.';
    }
    displayVoucherErrors([]);
    renderOrderSummary();
    return false;
  }
}

function revalidateAppliedVoucher() {
  if (appliedVoucher) {
    verifiedOrderQuote = null;
    renderCart();
    return validateVoucher(appliedVoucher, 'recheck');
  }
}

voucherApplyButton.addEventListener('click', () => {
  validateVoucher(voucherCodeInput.value.trim().toUpperCase());
});
voucherCodeInput.addEventListener('input', () => {
  voucherRequestNumber += 1;
  if (appliedVoucher && voucherCodeInput.value.trim().toUpperCase() !== appliedVoucher) {
    appliedVoucher = '';
    verifiedOrderQuote = null;
    voucherFeedback.textContent = '';
    displayVoucherErrors([]);
    renderCart();
  }
});
voucherCodeInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    validateVoucher(voucherCodeInput.value.trim().toUpperCase());
  }
});

function restaurantDate(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: bookingConfig?.timeZone || 'Asia/Ho_Chi_Minh',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function renderSlots() {
  const chosenIsAvailable = bookingSlots.some((slot) => slot.time === selectedSlot && slot.available);
  if (!chosenIsAvailable) selectedSlot = bookingSlots.find((slot) => slot.available)?.time || '';

  slotGrid.innerHTML = bookingSlots.map((slot) => {
    const selected = slot.time === selectedSlot && slot.available;
    const label = slot.available ? slot.time : `${slot.time} · Đầy`;
    return `<button class="slot-button${selected ? ' is-selected' : ''}" type="button" data-slot="${slot.time}" aria-pressed="${selected}"${slot.available ? '' : ' disabled'}>${label}</button>`;
  }).join('');

  bookingSubmit.disabled = !selectedSlot;
  if (bookingSlots.length && !bookingSlots.some((slot) => slot.available)) {
    slotHelp.textContent = 'Ngày này đã hết chỗ. Vui lòng chọn ngày khác.';
  } else if (selectedSlot) {
    const current = bookingSlots.find((slot) => slot.time === selectedSlot);
    slotHelp.textContent = `${current.remaining} bàn còn trống · Chọn giờ cách nhau 30 phút.`;
  } else {
    slotHelp.textContent = 'Đang tải các khung giờ còn trống…';
  }
}

async function loadBookingSlots(day, preferred = '') {
  const requestNumber = ++slotRequestNumber;
  slotGrid.innerHTML = '';
  slotHelp.textContent = 'Đang kiểm tra chỗ trống…';
  bookingSubmit.disabled = true;
  try {
    const response = await fetch(`/api/slots?date=${encodeURIComponent(day)}`, { cache: 'no-store' });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Không tải được giờ đặt bàn.');
    if (requestNumber !== slotRequestNumber) return;
    bookingSlots = result.slots;
    selectedSlot = preferred && bookingSlots.some((slot) => slot.time === preferred && slot.available)
      ? preferred
      : '';
    renderSlots();
  } catch (error) {
    if (requestNumber !== slotRequestNumber) return;
    bookingSlots = [];
    selectedSlot = '';
    slotHelp.textContent = 'Không kết nối được máy chủ đặt bàn. Hãy chạy python server.py rồi tải lại trang.';
    bookingSubmit.disabled = true;
  }
}

async function initializeBooking() {
  try {
    const response = await fetch('/api/config', { cache: 'no-store' });
    if (!response.ok) throw new Error('Server unavailable');
    bookingConfig = await response.json();
    slotOpeningNote.textContent = `(${bookingConfig.openingTime}–${bookingConfig.closingTime})`;
    document.querySelector('#visit-hours').textContent = `${bookingConfig.openingTime} — ${bookingConfig.closingTime}`;
    const today = restaurantDate();
    bookingDate.min = today;
    bookingDate.value = today;
    await loadBookingSlots(today);
    if (!bookingSlots.some((slot) => slot.available)) {
      const tomorrow = new Date(`${today}T12:00:00`);
      tomorrow.setDate(tomorrow.getDate() + 1);
      const nextDay = restaurantDate(tomorrow);
      bookingDate.value = nextDay;
      await loadBookingSlots(nextDay);
    }
  } catch {
    bookingDate.min = restaurantDate();
    bookingDate.value = bookingDate.min;
    slotHelp.textContent = 'Không kết nối được máy chủ đặt bàn. Hãy chạy python server.py rồi tải lại trang.';
    bookingSubmit.disabled = true;
  }
}

bookingDate.addEventListener('change', async () => {
  selectedSlot = '';
  bookingResponse.replaceChildren();
  await loadBookingSlots(bookingDate.value);
  revalidateAppliedVoucher();
});

slotGrid.addEventListener('click', (event) => {
  const button = event.target.closest('[data-slot]');
  if (!button || button.disabled) return;
  selectedSlot = button.dataset.slot;
  renderSlots();
  revalidateAppliedVoucher();
});

bookingResponse.addEventListener('click', (event) => {
  const suggestion = event.target.closest('[data-suggest-slot]');
  if (!suggestion) return;
  const suggestedTime = suggestion.dataset.suggestSlot;
  selectedSlot = suggestedTime;
  renderSlots();
  bookingResponse.classList.remove('is-success');
  bookingResponse.textContent = `Đã chọn ${suggestedTime}. Gửi lại yêu cầu để xác nhận.`;
  slotGrid.querySelector(`[data-slot="${suggestedTime}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
});

bookingForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!selectedSlot || !bookingForm.reportValidity()) return;
  bookingSubmit.disabled = true;
  bookingResponse.classList.remove('is-success');
  bookingResponse.textContent = 'Đang kiểm tra chỗ và gửi yêu cầu…';
  const formData = new FormData(bookingForm);
  const bookingPayload = {
    name: formData.get('name'),
    phone: formData.get('phone'),
    date: bookingDate.value,
    time: selectedSlot,
    partySize: Number(formData.get('partySize')),
    cart: cart.map(({ id, quantity }) => ({ id, quantity })),
    voucherCode: appliedVoucher,
  };
  let requestKey;
  try {
    requestKey = await bookingRequestKeyFor(JSON.stringify(bookingPayload));
    const response = await fetch('/api/bookings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestKey },
      body: JSON.stringify(bookingPayload),
    });
    const result = await response.json();
    if (response.status === 409) {
      selectedSlot = '';
      await loadBookingSlots(bookingDate.value);
      revalidateAppliedVoucher();
      bookingSubmit.disabled = true;
      bookingResponse.classList.remove('is-success');
      bookingResponse.textContent = result.suggestedTime
        ? `Rất tiếc, ${result.time || 'khung giờ bạn chọn'} vừa kín chỗ. Khung gần nhất còn trống là ${result.suggestedTime}.`
        : 'Khung giờ này đã kín và ngày này không còn giờ trống. Vui lòng chọn ngày khác.';
      if (result.suggestedTime) {
        const suggestionButton = document.createElement('button');
        suggestionButton.className = 'suggested-slot';
        suggestionButton.type = 'button';
        suggestionButton.dataset.suggestSlot = result.suggestedTime;
        suggestionButton.textContent = `Chuyển sang ${result.suggestedTime}`;
        bookingResponse.append(suggestionButton);
      }
      return;
    }
    if (response.status === 422 && result.voucherErrors) {
      appliedVoucher = '';
      voucherCodeInput.value = '';
      voucherFeedback.textContent = 'Máy chủ đã kiểm tra lại và gỡ mã ưu đãi:';
      displayVoucherErrors(result.voucherErrors);
      renderCart();
      throw new Error(result.error || 'Điều kiện mã ưu đãi đã thay đổi.');
    }
    if (!response.ok) throw new Error(result.error || 'Chưa gửi được yêu cầu.');
    clearBookingRequestKey();
    bookingResponse.classList.add('is-success');
    bookingResponse.textContent = `${result.message} Mã đặt bàn: ${result.bookingCode} · ${result.time} · thành tiền ${formatPrice(result.totalVnd)}.`;
    bookingForm.reset();
    bookingDate.value = result.date;
    selectedSlot = '';
    appliedVoucher = '';
    verifiedOrderQuote = null;
    voucherCodeInput.value = '';
    voucherFeedback.textContent = '';
    displayVoucherErrors([]);
    cart = [];
    persistCart();
    renderCart();
    await loadBookingSlots(result.date);
  } catch (error) {
    bookingResponse.classList.remove('is-success');
    bookingResponse.textContent = error instanceof TypeError
      ? 'Mất kết nối trước khi nhận xác nhận. Thông tin vẫn được giữ; hãy thử gửi lại, hệ thống sẽ tránh tạo đơn trùng.'
      : (error.message || 'Chưa gửi được yêu cầu. Vui lòng thử lại.');
  } finally {
    bookingSubmit.disabled = !selectedSlot;
  }
});

renderMenu();
reconcileCart();
renderCart();
initializeBooking();
