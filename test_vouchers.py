"""Automatic tests for CHIEUVUI rules and transactional booking capacity."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer
from http.cookiejar import CookieJar
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
import json
import tempfile
import unittest

import server


FRIDAY = date(2026, 10, 16)
SATURDAY = date(2026, 10, 17)
SUNDAY = date(2026, 10, 18)
ONE_SNACK = [{"id": "shrimp-pork-rolls", "quantity": 1}]
TWO_SNACKS = [{"id": "shrimp-pork-rolls", "quantity": 2}]


class ChieuVuiRuleTests(unittest.TestCase):
    def test_1330_is_too_early(self):
        self.assertEqual(
            server.evaluate_chieuvui(FRIDAY, "13:30", TWO_SNACKS),
            ["Mã chỉ áp dụng cho khung giờ 14:00–17:00. Bạn đang chọn 13:30."],
        )

    def test_1400_is_inclusive(self):
        self.assertEqual(server.evaluate_chieuvui(FRIDAY, "14:00", TWO_SNACKS), [])

    def test_1700_is_inclusive(self):
        self.assertEqual(server.evaluate_chieuvui(FRIDAY, "17:00", TWO_SNACKS), [])

    def test_1730_is_too_late(self):
        self.assertEqual(
            server.evaluate_chieuvui(FRIDAY, "17:30", TWO_SNACKS),
            ["Mã chỉ áp dụng cho khung giờ 14:00–17:00. Bạn đang chọn 17:30."],
        )

    def test_friday_is_a_weekday(self):
        self.assertEqual(server.evaluate_chieuvui(FRIDAY, "15:00", TWO_SNACKS), [])

    def test_saturday_is_rejected_with_day_name(self):
        self.assertEqual(
            server.evaluate_chieuvui(SATURDAY, "15:00", TWO_SNACKS),
            ["Mã không áp dụng cuối tuần. Bạn đang chọn Thứ 7."],
        )

    def test_sunday_is_rejected_with_day_name(self):
        self.assertEqual(
            server.evaluate_chieuvui(SUNDAY, "15:00", TWO_SNACKS),
            ["Mã không áp dụng cuối tuần. Bạn đang chọn Chủ nhật."],
        )

    def test_one_snack_reports_exactly_one_missing(self):
        self.assertEqual(
            server.evaluate_chieuvui(FRIDAY, "15:00", ONE_SNACK),
            ["Cần thêm 1 món Ăn vặt (hiện có 1/2)."],
        )

    def test_two_snack_quantities_qualify(self):
        self.assertEqual(server.evaluate_chieuvui(FRIDAY, "15:00", TWO_SNACKS), [])

    def test_all_missing_conditions_are_returned_together(self):
        self.assertEqual(
            server.evaluate_chieuvui(SUNDAY, "19:00", ONE_SNACK),
            [
                "Mã chỉ áp dụng cho khung giờ 14:00–17:00. Bạn đang chọn 19:00.",
                "Mã không áp dụng cuối tuần. Bạn đang chọn Chủ nhật.",
                "Cần thêm 1 món Ăn vặt (hiện có 1/2).",
            ],
        )

    def test_only_snack_category_counts_toward_two_items(self):
        cart = [
            {"id": "honey-chicken-rice", "quantity": 4},
            {"id": "iced-milk-coffee", "quantity": 3},
            {"id": "shrimp-pork-rolls", "quantity": 1},
        ]
        self.assertEqual(
            server.evaluate_chieuvui(FRIDAY, "15:00", cart),
            ["Cần thêm 1 món Ăn vặt (hiện có 1/2)."],
        )

    def test_order_amount_uses_server_catalog_and_applies_twenty_percent(self):
        cart = [
            {"id": "honey-chicken-rice", "quantity": 1, "price": 1, "discount": 999999},
            {"id": "shrimp-pork-rolls", "quantity": 1, "price": 1},
            {"id": "sweet-potato-fries", "quantity": 1, "price": 1},
        ]
        items, subtotal, discount, errors = server.calculate_order(FRIDAY, "15:00", cart, "CHIEUVUI")
        self.assertEqual(errors, [])
        self.assertEqual(len(items), 3)
        self.assertEqual(subtotal, 155000)
        self.assertEqual(discount, 31000)

    def test_invalid_time_and_weekday_and_zero_snacks_all_return(self):
        errors = server.evaluate_chieuvui(SATURDAY, "13:30", [])
        self.assertEqual(len(errors), 3)
        self.assertEqual(errors[-1], "Cần thêm 2 món Ăn vặt (hiện có 0/2).")

    def test_unknown_cart_item_is_rejected(self):
        items, subtotal, discount, errors = server.calculate_order(
            FRIDAY, "15:00", [{"id": "not-in-menu", "quantity": 2}], "CHIEUVUI"
        )
        self.assertIsNone(items)
        self.assertEqual((subtotal, discount), (0, 0))
        self.assertIn("Thực đơn có món không còn tồn tại.", errors[0])


class BookingCapacityApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_dir = server.DATA_DIR
        self.original_db_path = server.DB_PATH
        server.DATA_DIR = Path(self.temp_dir.name)
        server.DB_PATH = server.DATA_DIR / "test-bookings.sqlite3"
        server.initialize_db()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.BookingHandler)
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.visit_date = self.next_weekday()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        server.DATA_DIR = self.original_data_dir
        server.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    @staticmethod
    def next_weekday():
        day = datetime.now(server.LOCAL_TZ).date() + timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        return day.isoformat()

    def post(self, path, payload, headers=None):
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def payload(self, reservation_time="15:00"):
        return {
            "name": "Khách thử",
            "phone": "0912345678",
            "date": self.visit_date,
            "time": reservation_time,
            "partySize": 2,
            "cart": [],
            "voucherCode": "",
        }

    def test_eleventh_booking_is_blocked_and_nearest_tie_prefers_earlier(self):
        for _ in range(10):
            status, _ = self.post("/api/bookings", self.payload())
            self.assertEqual(status, 201)
        status, result = self.post("/api/bookings", self.payload())
        self.assertEqual(status, 409)
        self.assertEqual(result["suggestedTime"], "14:30")

    def test_eleven_simultaneous_requests_never_exceed_ten(self):
        payload = self.payload()
        with ThreadPoolExecutor(max_workers=11) as executor:
            results = list(executor.map(lambda _: self.post("/api/bookings", payload)[0], range(11)))
        self.assertEqual(results.count(201), 10)
        self.assertEqual(results.count(409), 1)

    def test_final_booking_rechecks_voucher_rules_server_side(self):
        payload = self.payload("19:00")
        payload.update({
            "cart": [{"id": "shrimp-pork-rolls", "quantity": 2}],
            "voucherCode": "CHIEUVUI",
            "discountVnd": 0,
        })
        status, result = self.post("/api/bookings", payload)
        self.assertEqual(status, 422)
        self.assertEqual(len(result["voucherErrors"]), 1)
        with closing(server.connect_db()) as db:
            count = db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        self.assertEqual(count, 0)

    def test_blank_required_fields_are_rejected_and_empty_cart_is_allowed(self):
        payload = self.payload()
        payload["name"] = "   "
        status, _ = self.post("/api/bookings", payload)
        self.assertEqual(status, 400)
        payload = self.payload()
        payload["phone"] = ""
        status, _ = self.post("/api/bookings", payload)
        self.assertEqual(status, 400)
        payload = self.payload()
        status, result = self.post("/api/bookings", payload)
        self.assertEqual(status, 201)
        self.assertEqual(result["subtotalVnd"], 0)
        with closing(server.connect_db()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM booking_items").fetchone()[0], 0)

    def test_idempotency_key_replays_booking_without_duplicate_or_capacity_use(self):
        payload = self.payload()
        headers = {"Idempotency-Key": "retry-after-network-drop"}
        first_status, first = self.post("/api/bookings", payload, headers)
        replay_status, replay = self.post("/api/bookings", payload, headers)
        self.assertEqual((first_status, replay_status), (201, 201))
        self.assertEqual(first["bookingCode"], replay["bookingCode"])
        self.assertTrue(replay["replayed"])
        with closing(server.connect_db()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0], 1)

    def test_idempotency_key_cannot_be_reused_for_changed_payload(self):
        headers = {"Idempotency-Key": "same-request-token"}
        self.assertEqual(self.post("/api/bookings", self.payload(), headers)[0], 201)
        changed = self.payload()
        changed["name"] = "Khách khác"
        status, _ = self.post("/api/bookings", changed, headers)
        self.assertEqual(status, 409)

    def test_voucher_api_returns_every_missing_condition(self):
        status, result = self.post("/api/vouchers/validate", {
            "code": "CHIEUVUI",
            "date": SUNDAY.isoformat(),
            "time": "19:00",
            "cart": ONE_SNACK,
        })
        self.assertEqual(status, 422)
        self.assertEqual(len(result["errors"]), 3)
        self.assertEqual(result["errors"][1], "Mã không áp dụng cuối tuần. Bạn đang chọn Chủ nhật.")

    def test_voucher_api_accepts_inclusive_end_and_returns_quote(self):
        status, result = self.post("/api/vouchers/validate", {
            "code": "CHIEUVUI",
            "date": FRIDAY.isoformat(),
            "time": "17:00",
            "cart": TWO_SNACKS,
        })
        self.assertEqual(status, 200)
        self.assertTrue(result["valid"])
        self.assertEqual(result["discountPercent"], 20)
        self.assertEqual(result["discountVnd"], 16800)

    def test_server_recomputes_discount_and_stores_order_lines(self):
        payload = self.payload("15:00")
        payload.update({
            "cart": [
                {"id": "honey-chicken-rice", "quantity": 1, "price": 1},
                {"id": "shrimp-pork-rolls", "quantity": 1, "price": 1},
                {"id": "sweet-potato-fries", "quantity": 1, "price": 1},
            ],
            "voucherCode": "CHIEUVUI",
            "discountVnd": 9999999,
        })
        status, result = self.post("/api/bookings", payload)
        self.assertEqual(status, 201)
        self.assertEqual(result["subtotalVnd"], 155000)
        self.assertEqual(result["discountVnd"], 31000)
        with closing(server.connect_db()) as db:
            row = db.execute("SELECT subtotal_vnd, discount_vnd, voucher_code FROM bookings").fetchone()
            line_count = db.execute("SELECT COUNT(*) FROM booking_items").fetchone()[0]
        self.assertEqual(tuple(row), (155000, 31000, "CHIEUVUI"))
        self.assertEqual(line_count, 3)


class AdminPasswordTests(unittest.TestCase):
    def test_password_is_hashed_and_only_correct_password_verifies(self):
        raw_password = "Correct-Horse-482!"
        stored_hash = server.hash_password(raw_password)
        self.assertNotIn(raw_password, stored_hash)
        self.assertTrue(server.verify_password(raw_password, stored_hash))
        self.assertFalse(server.verify_password("not-the-password", stored_hash))


class AdminSessionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_dir = server.DATA_DIR
        self.original_db_path = server.DB_PATH
        server.DATA_DIR = Path(self.temp_dir.name)
        server.DB_PATH = server.DATA_DIR / "admin-test.sqlite3"
        server.initialize_db()
        server.create_admin("manager@example.com", "Correct-Horse-482!", "Bếp trưởng")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.BookingHandler)
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        server.DATA_DIR = self.original_data_dir
        server.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def request(self, path, payload=None, method=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            try:
                payload = json.loads(body) if body else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}
            return response.status, response.geturl(), payload

    def test_admin_pages_redirect_and_admin_api_requires_session(self):
        status, final_url, _ = self.request("/admin.html")
        self.assertEqual(status, 200)
        self.assertIn("/admin-login.html", final_url)
        status, _, payload = self.request("/api/admin/bookings")
        self.assertEqual(status, 401)
        self.assertIn("Phiên đăng nhập", payload["error"])

    def test_login_dashboard_accept_cancel_and_released_capacity(self):
        status, _, _ = self.request("/api/admin/login", {
            "email": "MANAGER@example.com",
            "password": "Correct-Horse-482!",
        }, "POST")
        self.assertEqual(status, 200)
        self.assertTrue(any(cookie.name == server.SESSION_COOKIE for cookie in self.cookies))

        today = datetime.now(server.LOCAL_TZ).date()
        slot = next((value for value in server.SLOTS if server.slot_is_future(today, value)), None)
        if not slot:
            self.skipTest("No future reservation slot remains today.")
        before = self.request(f"/api/slots?date={today.isoformat()}")[2]
        remaining_before = next(row["remaining"] for row in before["slots"] if row["time"] == slot)
        status, _, booking = self.request("/api/bookings", {
            "name": "Khách hôm nay",
            "phone": "0912345678",
            "date": today.isoformat(),
            "time": slot,
            "partySize": 3,
            "cart": [{"id": "honey-chicken-rice", "quantity": 1}],
            "voucherCode": "",
        }, "POST")
        self.assertEqual(status, 201)

        status, _, dashboard = self.request("/api/admin/bookings?status=pending")
        self.assertEqual(status, 200)
        self.assertEqual(len(dashboard["bookings"]), 1)
        self.assertEqual(dashboard["bookings"][0]["name"], "Khách hôm nay")
        self.assertEqual(dashboard["bookings"][0]["items"][0]["name"], "Cơm gà nướng mật ong")

        status, _, accepted = self.request("/api/admin/bookings/status", {
            "bookingCode": booking["bookingCode"], "status": "confirmed",
        }, "POST")
        self.assertEqual((status, accepted["status"]), (200, "confirmed"))
        status, _, cancelled = self.request("/api/admin/bookings/status", {
            "bookingCode": booking["bookingCode"], "status": "cancelled",
        }, "POST")
        self.assertEqual((status, cancelled["status"]), (200, "cancelled"))

        after = self.request(f"/api/slots?date={today.isoformat()}")[2]
        remaining_after = next(row["remaining"] for row in after["slots"] if row["time"] == slot)
        self.assertEqual(remaining_after, remaining_before)
        status, _, filtered = self.request("/api/admin/bookings?status=cancelled")
        self.assertEqual(status, 200)
        self.assertEqual([row["status"] for row in filtered["bookings"]], ["cancelled"])

        status, _, _ = self.request("/api/admin/logout", {}, "POST")
        self.assertEqual(status, 200)
        status, _, _ = self.request("/api/admin/bookings")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
