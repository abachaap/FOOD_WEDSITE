const loginForm = document.querySelector('#admin-login-form');
const loginMessage = document.querySelector('#login-message');
const loginSubmit = document.querySelector('#login-submit');
const dashboard = document.querySelector('#admin-dashboard');
const bookingsContainer = document.querySelector('#admin-bookings');
const dashboardMessage = document.querySelector('#dashboard-message');
const statusFilter = document.querySelector('#status-filter');

function formatMoney(value) {
  return `${new Intl.NumberFormat('vi-VN').format(value || 0)}đ`;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options });
  let result = {};
  try { result = await response.json(); } catch { /* no response body */ }
  if (response.status === 401 && url !== '/api/admin/login') {
    location.replace('/admin-login.html');
    throw new Error('Phiên đăng nhập đã hết hạn.');
  }
  if (!response.ok) throw new Error(result.error || 'Có lỗi xảy ra.');
  return result;
}

if (loginForm) {
  fetch('/api/admin/me', { credentials: 'same-origin', cache: 'no-store' })
    .then((response) => { if (response.ok) location.replace('/admin'); })
    .catch(() => {});

  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    loginSubmit.disabled = true;
    loginMessage.textContent = '';
    const data = new FormData(loginForm);
    try {
      await requestJson('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: data.get('email'), password: data.get('password') }),
      });
      location.replace('/admin');
    } catch (error) {
      loginMessage.textContent = error.message || 'Không kết nối được máy chủ.';
      loginSubmit.disabled = false;
    }
  });
}

function statusText(status) {
  return ({ pending: 'Chờ', confirmed: 'Đã nhận', cancelled: 'Đã hủy' })[status] || status;
}

function renderBooking(booking) {
  const card = document.createElement('article');
  card.className = 'admin-booking-card';

  const top = document.createElement('div');
  top.className = 'admin-booking-top';
  const timeAndCode = document.createElement('div');
  timeAndCode.innerHTML = `<span class="admin-booking-time">${booking.time}</span><span class="admin-booking-code"></span>`;
  timeAndCode.querySelector('.admin-booking-code').textContent = booking.bookingCode;
  top.append(timeAndCode);
  const pill = document.createElement('span');
  pill.className = `status-pill ${booking.status}`;
  pill.textContent = statusText(booking.status);
  top.append(pill);

  const person = document.createElement('div');
  person.className = 'admin-booking-person';
  const name = document.createElement('h2');
  name.className = 'admin-booking-name';
  name.textContent = booking.name;
  const contact = document.createElement('p');
  contact.className = 'admin-booking-contact';
  const phone = document.createElement('a');
  phone.href = `tel:${booking.phone.replace(/[^+\d]/g, '')}`;
  phone.textContent = booking.phone;
  contact.append(phone);
  person.append(name, contact);

  const details = document.createElement('div');
  details.className = 'admin-party';
  details.textContent = `${booking.partySize} người`;

  card.append(top, person, details);
  if (booking.items.length) {
    const list = document.createElement('ul');
    list.className = 'admin-items';
    booking.items.forEach((item) => {
      const line = document.createElement('li');
      line.textContent = `${item.name} × ${item.quantity}`;
      list.append(line);
    });
    card.append(list);
    const total = document.createElement('div');
    total.className = 'admin-order-total';
    const label = document.createElement('span');
    label.textContent = booking.discountVnd ? `${booking.voucherCode} · đã giảm ${formatMoney(booking.discountVnd)}` : 'Tổng món';
    const amount = document.createElement('strong');
    amount.textContent = formatMoney(booking.subtotalVnd - booking.discountVnd);
    total.append(label, amount);
    card.append(total);
  }

  if (booking.status !== 'cancelled') {
    const actions = document.createElement('div');
    actions.className = 'admin-actions';
    if (booking.status === 'pending') {
      const accept = document.createElement('button');
      accept.className = 'admin-action';
      accept.type = 'button';
      accept.textContent = 'Chấp nhận';
      accept.dataset.bookingCode = booking.bookingCode;
      accept.dataset.nextStatus = 'confirmed';
      actions.append(accept);
    }
    const cancel = document.createElement('button');
    cancel.className = 'admin-action cancel';
    cancel.type = 'button';
    cancel.textContent = 'Hủy';
    cancel.dataset.bookingCode = booking.bookingCode;
    cancel.dataset.nextStatus = 'cancelled';
    actions.append(cancel);
    card.append(actions);
  }
  return card;
}

async function loadDashboard() {
  dashboardMessage.textContent = '';
  bookingsContainer.replaceChildren();
  try {
    const result = await requestJson(`/api/admin/bookings?status=${encodeURIComponent(statusFilter.value)}`);
    document.querySelector('#admin-identity').textContent = result.admin?.displayName || document.querySelector('#admin-identity').textContent;
    document.querySelector('#booking-count').textContent = result.bookings.length;
    document.querySelector('#dashboard-date').textContent = new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'full', timeZone: 'Asia/Ho_Chi_Minh',
    }).format(new Date(`${result.date}T12:00:00+07:00`));
    if (!result.bookings.length) {
      const empty = document.createElement('div');
      empty.className = 'admin-empty';
      empty.textContent = 'Không có đơn đặt bàn ở trạng thái này hôm nay.';
      bookingsContainer.append(empty);
    } else {
      bookingsContainer.append(...result.bookings.map(renderBooking));
    }
  } catch (error) {
    dashboardMessage.textContent = error.message;
  }
}

if (dashboard) {
  requestJson('/api/admin/me').then(({ admin }) => {
    document.querySelector('#admin-identity').textContent = admin.displayName;
    dashboard.hidden = false;
    loadDashboard();
  }).catch(() => {});

  statusFilter.addEventListener('change', loadDashboard);
  document.querySelector('#refresh-bookings').addEventListener('click', loadDashboard);
  document.querySelector('#admin-logout').addEventListener('click', async () => {
    try { await requestJson('/api/admin/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); }
    finally { location.replace('/admin-login.html'); }
  });
  bookingsContainer.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-next-status]');
    if (!button) return;
    button.disabled = true;
    dashboardMessage.textContent = '';
    try {
      await requestJson('/api/admin/bookings/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bookingCode: button.dataset.bookingCode, status: button.dataset.nextStatus }),
      });
      await loadDashboard();
    } catch (error) {
      dashboardMessage.textContent = error.message;
      button.disabled = false;
    }
  });
}
