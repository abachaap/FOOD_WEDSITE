"""Small standard-library web server and transactional booking API."""

from datetime import date, datetime, time, timedelta, timezone
from contextlib import closing
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import argparse
import hashlib
import hmac
import json
import os
import posixpath
import re
import secrets
import sqlite3
import time as system_time

import config
from menu_catalog import MENU_CATALOG


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("BEP_NHA_DATA_DIR", ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "bookings.sqlite3"
# Vietnam uses UTC+07:00 year-round; a fixed offset also runs on Windows
# without requiring an external IANA timezone database package.
LOCAL_TZ = timezone(timedelta(hours=7), config.TIME_ZONE)
ACTIVE_STATUSES = ("pending", "confirmed")
SESSION_COOKIE = "bepnha_admin"
SESSION_LIFETIME_SECONDS = 8 * 60 * 60
PASSWORD_HASH_ITERATIONS = 310_000
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0").strip().lower() in {"1", "true", "yes"}


def session_cookie_attributes():
    secure = "; Secure" if COOKIE_SECURE else ""
    return f"Path=/; Max-Age={SESSION_LIFETIME_SECONDS}; HttpOnly; SameSite=Strict{secure}"


def slot_times():
    start = datetime.strptime(config.OPENING_TIME, "%H:%M")
    end = datetime.strptime(config.CLOSING_TIME, "%H:%M")
    slots = []
    current = start
    while current < end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=config.SLOT_INTERVAL_MINUTES)
    return slots


SLOTS = slot_times()


def connect_db():
    DATA_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def initialize_db():
    with closing(connect_db()) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_code TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                reservation_date TEXT NOT NULL,
                reservation_time TEXT NOT NULL,
                party_size INTEGER NOT NULL CHECK (party_size > 0),
                subtotal_vnd INTEGER NOT NULL DEFAULT 0 CHECK (subtotal_vnd >= 0),
                discount_vnd INTEGER NOT NULL DEFAULT 0 CHECK (discount_vnd >= 0),
                voucher_code TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled', 'no_show')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(bookings)")}
        for column, declaration in (
            ("subtotal_vnd", "INTEGER NOT NULL DEFAULT 0 CHECK (subtotal_vnd >= 0)"),
            ("discount_vnd", "INTEGER NOT NULL DEFAULT 0 CHECK (discount_vnd >= 0)"),
            ("voucher_code", "TEXT"),
            ("request_key", "TEXT"),
            ("request_fingerprint", "TEXT"),
        ):
            if column not in columns:
                db.execute(f"ALTER TABLE bookings ADD COLUMN {column} {declaration}")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS bookings_request_key_idx ON bookings (request_key)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS booking_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
                menu_item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price_vnd INTEGER NOT NULL CHECK (unit_price_vnd >= 0),
                UNIQUE (booking_id, menu_item_id)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token_hash TEXT PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS admin_sessions_expiry_idx ON admin_sessions (expires_at)")
        db.execute("""
            CREATE INDEX IF NOT EXISTS bookings_slot_status_idx
            ON bookings (reservation_date, reservation_time, status)
        """)


def parse_cart(cart):
    if not isinstance(cart, list):
        raise ValueError("Giỏ hàng không hợp lệ.")
    quantities = {}
    for line in cart:
        if not isinstance(line, dict):
            raise ValueError("Giỏ hàng có món không hợp lệ.")
        item_id = line.get("id")
        quantity = line.get("quantity")
        if not isinstance(item_id, str) or item_id not in MENU_CATALOG:
            raise ValueError("Thực đơn có món không còn tồn tại. Hãy tải lại trang.")
        if type(quantity) is not int or not 1 <= quantity <= 99:
            raise ValueError("Số lượng món không hợp lệ.")
        quantities[item_id] = quantities.get(item_id, 0) + quantity
        if quantities[item_id] > 99:
            raise ValueError("Mỗi món được đặt tối đa 99 phần.")
    return [{"id": item_id, "quantity": quantity} for item_id, quantity in quantities.items()]


def evaluate_chieuvui(reservation_date, reservation_time, cart):
    """Return every unmet CHIEUVUI rule for visit date/time and normalized cart."""
    errors = []
    try:
        day = reservation_date if isinstance(reservation_date, date) else date.fromisoformat(reservation_date)
    except (TypeError, ValueError):
        return ["Ngày đến không hợp lệ."]
    try:
        selected_time = time.fromisoformat(reservation_time)
    except (TypeError, ValueError):
        selected_time = None

    if selected_time is None or not time(14, 0) <= selected_time <= time(17, 0):
        errors.append(
            f"Mã chỉ áp dụng cho khung giờ 14:00–17:00. Bạn đang chọn {reservation_time}."
        )

    weekdays_vi = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")
    if day.weekday() >= 5:
        errors.append(f"Mã không áp dụng cuối tuần. Bạn đang chọn {weekdays_vi[day.weekday()] }.")

    snack_count = sum(
        line["quantity"]
        for line in cart
        if MENU_CATALOG[line["id"]]["category"] == "snacks"
    )
    if snack_count < 2:
        errors.append(f"Cần thêm {2 - snack_count} món Ăn vặt (hiện có {snack_count}/2).")
    return errors


def calculate_order(reservation_date, reservation_time, raw_cart, voucher_code=""):
    try:
        items = parse_cart(raw_cart)
    except ValueError as error:
        return None, 0, 0, [str(error)]
    subtotal = sum(MENU_CATALOG[line["id"]]["price_vnd"] * line["quantity"] for line in items)
    normalized_code = voucher_code.strip().upper() if isinstance(voucher_code, str) else ""
    if not normalized_code:
        return items, subtotal, 0, []
    if normalized_code != "CHIEUVUI":
        return items, subtotal, 0, ["Mã giảm giá không hợp lệ."]
    errors = evaluate_chieuvui(reservation_date, reservation_time, items)
    discount = subtotal * 20 // 100 if not errors else 0
    return items, subtotal, discount, errors


def hash_password(password, salt=None):
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, PASSWORD_HASH_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    try:
        algorithm, iterations_text, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations)
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (AttributeError, ValueError, TypeError):
        return False


def create_admin(email, password, display_name=None):
    normalized_email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_email):
        raise ValueError("Địa chỉ email không hợp lệ.")
    if len(password) < 12:
        raise ValueError("Mật khẩu quản trị cần dài ít nhất 12 ký tự.")
    name = (display_name or normalized_email.split("@", 1)[0]).strip()[:160]
    with closing(connect_db()) as db:
        db.execute(
            "INSERT INTO admins (email, password_hash, display_name) VALUES (?, ?, ?)",
            (normalized_email, hash_password(password), name),
        )


def session_token_from_request(handler):
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
        return cookie[SESSION_COOKIE].value if SESSION_COOKIE in cookie else None
    except Exception:
        return None


def admin_for_session(token):
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(system_time.time())
    with closing(connect_db()) as db:
        row = db.execute("""
            SELECT admins.id, admins.email, admins.display_name
            FROM admin_sessions
            JOIN admins ON admins.id = admin_sessions.admin_id
            WHERE admin_sessions.token_hash = ? AND admin_sessions.expires_at > ? AND admins.is_active = 1
        """, (token_hash, now)).fetchone()
    return dict(row) if row else None


def insert_admin_session(admin_id):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(system_time.time())
    with closing(connect_db()) as db:
        db.execute("DELETE FROM admin_sessions WHERE expires_at <= ?", (now,))
        db.execute(
            "INSERT INTO admin_sessions (token_hash, admin_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, admin_id, now + SESSION_LIFETIME_SECONDS),
        )
    return token


def revoke_admin_session(token):
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with closing(connect_db()) as db:
        db.execute("DELETE FROM admin_sessions WHERE token_hash = ?", (token_hash,))


def slot_is_future(day, slot):
    local_slot = datetime.combine(day, time.fromisoformat(slot), tzinfo=LOCAL_TZ)
    return local_slot > datetime.now(LOCAL_TZ)


def get_slot_rows(day):
    with closing(connect_db()) as db:
        rows = db.execute("""
            SELECT reservation_time, COUNT(*) AS booked
            FROM bookings
            WHERE reservation_date = ? AND status IN (?, ?)
            GROUP BY reservation_time
        """, (day.isoformat(), *ACTIVE_STATUSES)).fetchall()
    counts = {row["reservation_time"]: row["booked"] for row in rows}
    return [
        {
            "time": slot,
            "booked": counts.get(slot, 0),
            "remaining": max(0, config.TABLES_PER_SLOT - counts.get(slot, 0)),
            "available": counts.get(slot, 0) < config.TABLES_PER_SLOT and slot_is_future(day, slot),
        }
        for slot in SLOTS
    ]


def nearest_available(day, requested):
    available = [row["time"] for row in get_slot_rows(day) if row["available"]]
    if not available:
        return None
    requested_minutes = int(requested[:2]) * 60 + int(requested[3:])
    # Earlier time wins when before and after are equally close.
    return min(
        available,
        key=lambda slot: (
            abs(int(slot[:2]) * 60 + int(slot[3:]) - requested_minutes),
            int(slot[:2]) * 60 + int(slot[3:]),
        ),
    )


class BookingHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format_string, *args):
        print("[%s] %s" % (self.log_date_time_string(), format_string % args))

    def normalized_path(self):
        return posixpath.normpath(unquote(urlparse(self.path).path))

    def is_admin_page(self):
        return self.normalized_path() in {"/admin", "/admin/", "/admin.html"}

    def is_admin_api(self):
        return self.normalized_path().startswith("/api/admin/")

    def current_admin(self):
        return admin_for_session(session_token_from_request(self))

    def require_admin(self):
        admin = self.current_admin()
        if not admin:
            self.send_json(401, {"error": "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."})
            return None
        return admin

    def redirect_to_login(self):
        self.send_response(302)
        self.send_header("Location", "/admin-login.html?next=%2Fadmin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def same_origin_request(self):
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc.casefold() != self.headers.get("Host", "").casefold():
            self.send_json(403, {"error": "Yêu cầu không cùng nguồn."})
            return False
        if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            self.send_json(403, {"error": "Yêu cầu không cùng nguồn."})
            return False
        return True

    def serve_admin_bookings(self, query):
        params = parse_qs(query)
        status_filter = params.get("status", ["all"])[0]
        allowed = {"all", "pending", "confirmed", "cancelled"}
        if status_filter not in allowed:
            return self.send_json(400, {"error": "Bộ lọc trạng thái không hợp lệ."})
        today = datetime.now(LOCAL_TZ).date().isoformat()
        with closing(connect_db()) as db:
            if status_filter == "all":
                rows = db.execute("""
                    SELECT booking_code, customer_name, customer_phone, party_size,
                           reservation_time, status, subtotal_vnd, discount_vnd, voucher_code
                    FROM bookings WHERE reservation_date = ?
                    ORDER BY reservation_time ASC, id ASC
                """, (today,)).fetchall()
            else:
                rows = db.execute("""
                    SELECT booking_code, customer_name, customer_phone, party_size,
                           reservation_time, status, subtotal_vnd, discount_vnd, voucher_code
                    FROM bookings WHERE reservation_date = ? AND status = ?
                    ORDER BY reservation_time ASC, id ASC
                """, (today, status_filter)).fetchall()
            result = []
            for row in rows:
                items = db.execute("""
                    SELECT menu_item_id, quantity, unit_price_vnd
                    FROM booking_items WHERE booking_id = (
                        SELECT id FROM bookings WHERE booking_code = ?
                    ) ORDER BY id ASC
                """, (row["booking_code"],)).fetchall()
                result.append({
                    "bookingCode": row["booking_code"],
                    "name": row["customer_name"],
                    "phone": row["customer_phone"],
                    "partySize": row["party_size"],
                    "time": row["reservation_time"],
                    "status": row["status"],
                    "subtotalVnd": row["subtotal_vnd"],
                    "discountVnd": row["discount_vnd"],
                    "voucherCode": row["voucher_code"],
                    "items": [
                        {
                            "id": item["menu_item_id"],
                            "name": MENU_CATALOG.get(item["menu_item_id"], {}).get("name", item["menu_item_id"]),
                            "quantity": item["quantity"],
                            "unitPriceVnd": item["unit_price_vnd"],
                        }
                        for item in items
                    ],
                })
        return self.send_json(200, {
            "date": today,
            "statusFilter": status_filter,
            "bookings": result,
        })

    def translate_path(self, path):
        normalized = self.normalized_path()
        if normalized in {"/admin", "/admin/"}:
            return str(ROOT / "admin.html")
        resolved = Path(super().translate_path(path)).resolve()
        if resolved == DATA_DIR or DATA_DIR in resolved.parents:
            return str(ROOT / "__not_found__")
        return str(resolved)

    def end_headers(self):
        if self.is_admin_page() or self.is_admin_api():
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def update_booking_status(self, payload):
        booking_code = payload.get("bookingCode")
        new_status = payload.get("status")
        if not isinstance(booking_code, str) or new_status not in ("confirmed", "cancelled"):
            return self.send_json(400, {"error": "Trạng thái đơn không hợp lệ."})
        today = datetime.now(LOCAL_TZ).date().isoformat()
        db = connect_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""
                SELECT status FROM bookings
                WHERE booking_code = ? AND reservation_date = ?
            """, (booking_code, today)).fetchone()
            if not row:
                db.execute("ROLLBACK")
                return self.send_json(404, {"error": "Không tìm thấy đơn đặt bàn hôm nay."})
            allowed_sources = ("pending", "confirmed")
            if row["status"] not in allowed_sources or (new_status == "confirmed" and row["status"] != "pending"):
                db.execute("ROLLBACK")
                return self.send_json(409, {"error": "Đơn đã được xử lý trước đó."})
            db.execute(
                "UPDATE bookings SET status = ? WHERE booking_code = ?",
                (new_status, booking_code),
            )
            db.execute("COMMIT")
        except sqlite3.Error:
            if db.in_transaction:
                db.execute("ROLLBACK")
            return self.send_json(503, {"error": "Chưa thể cập nhật đơn. Vui lòng thử lại."})
        finally:
            db.close()
        return self.send_json(200, {"bookingCode": booking_code, "status": new_status})

    def read_json(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if size < 1 or size > 10_000:
            return None
        try:
            return json.loads(self.rfile.read(size))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def do_GET(self):
        parsed = urlparse(self.path)
        if self.is_admin_page() and not self.current_admin():
            return self.redirect_to_login()
        if self.is_admin_api():
            if not self.require_admin():
                return
            if self.normalized_path() == "/api/admin/me":
                admin = self.current_admin()
                return self.send_json(200, {
                    "admin": {"email": admin["email"], "displayName": admin["display_name"]},
                })
            if self.normalized_path() == "/api/admin/bookings":
                return self.serve_admin_bookings(parsed.query)
            return self.send_json(404, {"error": "Không tìm thấy địa chỉ này."})
        if parsed.path.startswith("/data/"):
            return self.send_json(404, {"error": "Không tìm thấy địa chỉ này."})
        if parsed.path == "/api/config":
            return self.send_json(200, {
                "openingTime": config.OPENING_TIME,
                "closingTime": config.CLOSING_TIME,
                "slotIntervalMinutes": config.SLOT_INTERVAL_MINUTES,
                "tablesPerSlot": config.TABLES_PER_SLOT,
                "timeZone": config.TIME_ZONE,
            })
        if parsed.path == "/api/slots":
            params = parse_qs(parsed.query)
            try:
                day = date.fromisoformat(params.get("date", [""])[0])
            except ValueError:
                return self.send_json(400, {"error": "Ngày không hợp lệ."})
            return self.send_json(200, {"date": day.isoformat(), "slots": get_slot_rows(day)})
        return super().do_GET()

    def do_HEAD(self):
        if self.is_admin_page() and not self.current_admin():
            return self.redirect_to_login()
        if self.is_admin_api() and not self.require_admin():
            return
        return super().do_HEAD()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/admin/login":
            payload = self.read_json()
            if not isinstance(payload, dict):
                return self.send_json(400, {"error": "Dữ liệu đăng nhập không hợp lệ."})
            email = payload.get("email", "")
            password = payload.get("password", "")
            if not isinstance(email, str) or not isinstance(password, str) or not email.strip():
                return self.send_json(400, {"error": "Nhập email và mật khẩu."})
            with closing(connect_db()) as db:
                admin = db.execute(
                    "SELECT id, email, display_name, password_hash FROM admins WHERE email = ? AND is_active = 1",
                    (email.strip().lower(),),
                ).fetchone()
            if not admin or not verify_password(password, admin["password_hash"]):
                return self.send_json(401, {"error": "Email hoặc mật khẩu chưa đúng."})
            token = insert_admin_session(admin["id"])
            return self.send_json(200, {
                "admin": {"email": admin["email"], "displayName": admin["display_name"]},
            }, extra_headers={
                "Set-Cookie": f"{SESSION_COOKIE}={token}; {session_cookie_attributes()}",
            })

        if path.startswith("/api/admin/"):
            admin = self.require_admin()
            if not admin:
                return
            if path in ("/api/admin/logout", "/api/admin/bookings/status") and not self.same_origin_request():
                return
            payload = self.read_json()
            if not isinstance(payload, dict):
                return self.send_json(400, {"error": "Dữ liệu gửi lên không hợp lệ."})
            token = session_token_from_request(self)
            if path == "/api/admin/logout":
                revoke_admin_session(token)
                self.send_response(200)
                secure = "; Secure" if COOKIE_SECURE else ""
                self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict{secure}")
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", "2")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b"{}")
                return
            if path == "/api/admin/bookings/status":
                return self.update_booking_status(payload)
            return self.send_json(404, {"error": "Không tìm thấy địa chỉ này."})

        if path not in ("/api/bookings", "/api/vouchers/validate"):
            return self.send_json(404, {"error": "Không tìm thấy địa chỉ này."})

        payload = self.read_json()
        if not isinstance(payload, dict):
            return self.send_json(400, {"error": "Dữ liệu gửi lên không hợp lệ."})

        if path == "/api/vouchers/validate":
            code = payload.get("code", "")
            if not isinstance(code, str) or code.strip().upper() != "CHIEUVUI":
                return self.send_json(422, {"valid": False, "errors": ["Mã giảm giá không hợp lệ."]})
            items, subtotal, discount, errors = calculate_order(
                payload.get("date"), payload.get("time"), payload.get("cart"), code
            )
            if errors:
                return self.send_json(422, {"valid": False, "errors": errors, "subtotalVnd": subtotal})
            return self.send_json(200, {
                "valid": True,
                "code": "CHIEUVUI",
                "discountPercent": 20,
                "subtotalVnd": subtotal,
                "discountVnd": discount,
                "totalVnd": subtotal - discount,
            })

        name = payload.get("name", "")
        phone = payload.get("phone", "")
        date_text = payload.get("date", "")
        requested_time = payload.get("time", "")
        party_size = payload.get("partySize")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            return self.send_json(400, {"error": "Vui lòng nhập tên từ 1 đến 120 ký tự."})
        if not isinstance(phone, str) or not re.fullmatch(r"[+\d\s().-]{8,24}", phone):
            return self.send_json(400, {"error": "Vui lòng nhập số điện thoại hợp lệ."})
        if len(re.sub(r"\D", "", phone)) < 8:
            return self.send_json(400, {"error": "Số điện thoại cần có ít nhất 8 chữ số."})
        if type(party_size) is not int or not 1 <= party_size <= 30:
            return self.send_json(400, {"error": "Số người phải từ 1 đến 30."})
        try:
            day = date.fromisoformat(date_text)
        except (TypeError, ValueError):
            return self.send_json(400, {"error": "Ngày đặt bàn không hợp lệ."})
        if requested_time not in SLOTS:
            return self.send_json(400, {"error": "Khung giờ này không nằm trong giờ phục vụ."})
        if not slot_is_future(day, requested_time):
            return self.send_json(400, {"error": "Vui lòng chọn một ngày giờ trong tương lai."})

        items, subtotal, discount, voucher_errors = calculate_order(
            day.isoformat(), requested_time, payload.get("cart", []), payload.get("voucherCode", "")
        )
        if voucher_errors:
            return self.send_json(422, {
                "error": "Không thể áp mã CHIEUVUI cho đơn này.",
                "voucherErrors": voucher_errors,
            })
        voucher_code = "CHIEUVUI" if discount else None

        request_key = self.headers.get("Idempotency-Key", "").strip()
        if request_key and (len(request_key) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", request_key)):
            return self.send_json(400, {"error": "Mã gửi lại yêu cầu không hợp lệ."})
        fingerprint_payload = {
            "name": name.strip(), "phone": phone.strip(), "date": day.isoformat(),
            "time": requested_time, "partySize": party_size, "cart": items,
            "voucherCode": voucher_code,
        }
        request_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        db = connect_db()
        try:
            # Reserve SQLite's single writer before counting, so concurrent requests
            # serialize the capacity check and insert as one atomic operation.
            db.execute("BEGIN IMMEDIATE")
            if request_key:
                prior = db.execute(
                    "SELECT booking_code, reservation_date, reservation_time, subtotal_vnd, discount_vnd, voucher_code, request_fingerprint FROM bookings WHERE request_key = ?",
                    (request_key,),
                ).fetchone()
                if prior:
                    if prior["request_fingerprint"] != request_fingerprint:
                        db.execute("ROLLBACK")
                        return self.send_json(409, {"error": "Mã yêu cầu đã được dùng cho nội dung khác. Hãy tải lại trang trước khi gửi lại."})
                    db.execute("COMMIT")
                    return self.send_json(201, {
                        "bookingCode": prior["booking_code"],
                        "message": "Đã nhận yêu cầu đặt bàn của bạn.",
                        "date": prior["reservation_date"], "time": prior["reservation_time"],
                        "subtotalVnd": prior["subtotal_vnd"], "discountVnd": prior["discount_vnd"],
                        "totalVnd": prior["subtotal_vnd"] - prior["discount_vnd"],
                        "voucherCode": prior["voucher_code"], "replayed": True,
                    })
            booked = db.execute("""
                SELECT COUNT(*) AS booked FROM bookings
                WHERE reservation_date = ? AND reservation_time = ? AND status IN (?, ?)
            """, (day.isoformat(), requested_time, *ACTIVE_STATUSES)).fetchone()["booked"]
            if booked >= config.TABLES_PER_SLOT:
                db.execute("ROLLBACK")
                suggestion = nearest_available(day, requested_time)
                return self.send_json(409, {
                    "error": "Khung giờ này đã đủ 10 bàn.",
                    "suggestedTime": suggestion,
                    "date": day.isoformat(),
                    "time": requested_time,
                })

            booking_code = "BN-" + secrets.token_hex(4).upper()
            db.execute("""
                INSERT INTO bookings
                    (booking_code, customer_name, customer_phone, reservation_date,
                     reservation_time, party_size, subtotal_vnd, discount_vnd, voucher_code, status,
                     request_key, request_fingerprint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """, (
                booking_code, name.strip(), phone.strip(), day.isoformat(), requested_time,
                party_size, subtotal, discount, voucher_code, request_key or None,
                request_fingerprint if request_key else None,
            ))
            db.executemany("""
                INSERT INTO booking_items (booking_id, menu_item_id, quantity, unit_price_vnd)
                VALUES ((SELECT id FROM bookings WHERE booking_code = ?), ?, ?, ?)
            """, [
                (booking_code, line["id"], line["quantity"], MENU_CATALOG[line["id"]]["price_vnd"])
                for line in items
            ])
            db.execute("COMMIT")
        except sqlite3.Error:
            if db.in_transaction:
                db.execute("ROLLBACK")
            return self.send_json(503, {"error": "Chưa thể lưu đặt bàn. Vui lòng thử lại."})
        finally:
            db.close()

        return self.send_json(201, {
            "bookingCode": booking_code,
            "message": "Đã nhận yêu cầu đặt bàn của bạn.",
            "date": day.isoformat(),
            "time": requested_time,
            "subtotalVnd": subtotal,
            "discountVnd": discount,
            "totalVnd": subtotal - discount,
            "voucherCode": voucher_code,
        })


def main():
    initialize_db()
    parser = argparse.ArgumentParser(description="Bếp Nhà web server")
    parser.add_argument(
        "--create-admin",
        metavar="EMAIL",
        help="Tạo tài khoản quản trị tương tác rồi thoát",
    )
    args = parser.parse_args()
    if args.create_admin:
        import getpass

        password = getpass.getpass("Mật khẩu mới (ít nhất 12 ký tự): ")
        confirmation = getpass.getpass("Nhập lại mật khẩu: ")
        if password != confirmation:
            parser.error("Hai mật khẩu không khớp.")
        try:
            create_admin(args.create_admin, password)
        except (ValueError, sqlite3.IntegrityError) as error:
            parser.error(str(error))
        print(f"Đã tạo tài khoản quản trị {args.create_admin.strip().lower()}.")
        return
    address = (os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8000")))
    print(f"Bếp Nhà đang chạy tại http://{address[0]}:{address[1]}")
    ThreadingHTTPServer(address, BookingHandler).serve_forever()


if __name__ == "__main__":
    main()
