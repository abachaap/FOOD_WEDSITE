# Website nhà hàng Bếp Nhà

## Chạy dự án

Máy chủ cần Python 3.9 trở lên; không cần cài thư viện bên ngoài. Từ thư mục dự án, chạy:

```sh
python server.py
```

Mở `http://127.0.0.1:8000` để xem trang. Không mở `index.html` trực tiếp vì biểu mẫu cần API đặt bàn. Máy chủ tạo `data/bookings.sqlite3` tự động khi khởi động; dữ liệu đặt bàn được giữ lại giữa các lần chạy. Ảnh món ăn lấy từ Unsplash cần có mạng; giao diện dùng font hệ thống để hiển thị nhanh và vẫn hoạt động khi ngoại tuyến.

## Chức năng hiện có

- Trang chủ có banner, giới thiệu, món nổi bật và nút đặt bàn cố định trên màn hình điện thoại.
- Thực đơn có ba danh mục: Món chính, Ăn vặt, Nước uống.
- Tìm kiếm lọc ngay khi gõ, không phân biệt dấu tiếng Việt.
- Giỏ hàng có nút thêm, tăng/giảm số lượng, xóa món và tính tổng; giỏ được lưu trên thiết bị và đồng bộ món/giá khi mở lại.
- Đặt bàn dùng giờ mở/đóng và sức chứa cấu hình trong `config.py`; khung giờ cách nhau 30 phút.
- API kiểm tra sức chứa ở máy chủ trong transaction SQLite, chặn đơn thứ 11 cùng khung giờ và trả về giờ trống gần nhất.
- Voucher `CHIEUVUI` yêu cầu giờ đến từ 14:00 đến 17:00 (cả hai mốc đều tính), ngày trong tuần và ít nhất 2 phần Ăn vặt; đủ điều kiện sẽ giảm 20%.
- Máy chủ trả tất cả điều kiện chưa đạt, tự kiểm tra lại khi gửi đơn, tính giá từ catalog máy chủ và lưu mã giảm, số tiền cùng các dòng món.
- Trang quản trị tại `/admin` dùng đăng nhập email/mật khẩu, mật khẩu PBKDF2 đã băm và cookie phiên HttpOnly; dashboard hiển thị đơn hôm nay, cho lọc trạng thái, nhận hoặc hủy.
- Tab hỗ trợ bàn phím, ảnh tải lười và giao diện có điều chỉnh cho màn hình nhỏ.

## Tạo tài khoản quản trị

Chạy lệnh sau một lần; mật khẩu được nhập ẩn, cần tối thiểu 12 ký tự và chỉ lưu dưới dạng hash:

```sh
python server.py --create-admin quanly@example.com
```

Sau đó chạy `python server.py`, mở `http://127.0.0.1:8000/admin` và đăng nhập. Phiên hết hạn sau 8 giờ; đăng xuất sẽ thu hồi phiên hiện tại.

## Tài liệu

- [Bảng thiết kế và hướng dẫn giao diện](docs/design-system.md)
- [Sơ đồ dữ liệu và quy ước](docs/data-model.md)
- [SQL khởi tạo cơ sở dữ liệu PostgreSQL](database/schema.sql)

Thực đơn hiện dùng dữ liệu mẫu ở phía trình duyệt. `database/schema.sql` là sơ đồ PostgreSQL cho triển khai cơ sở dữ liệu tương lai; máy chủ đặt bàn hiện lưu bookings trong SQLite để chạy ngay mà không cần cài gói bổ sung.

## Kiểm thử

Chạy toàn bộ ca voucher, sức chứa đồng thời và phiên quản trị:

```sh
python -m unittest -v test_vouchers.py
```

## Chuẩn bị triển khai

Ứng dụng có thể chạy bằng Docker. Hosting cần hỗ trợ container Python, HTTPS, biến môi trường và một ổ đĩa lưu trữ bền vững được gắn tại `/data`; nếu không, dữ liệu đặt bàn và tài khoản quản trị có thể mất khi khởi động lại. Cấu hình sẵn dùng `PORT` do nền tảng cấp, lưu SQLite tại `BEP_NHA_DATA_DIR` và bật cờ `Secure` cho cookie quản trị.

Sau khi tạo dịch vụ từ Dockerfile, gắn ổ đĩa vào `/data`, kiểm tra `COOKIE_SECURE=1`, rồi chạy lệnh tạo quản trị trong console của dịch vụ:

```sh
python server.py --create-admin quanly@example.com
```

Tên miền cần được đăng ký riêng và trỏ DNS đến dịch vụ hosting; bật chứng chỉ HTTPS trước khi dùng trang quản trị. Chưa có nhà cung cấp hosting, tên miền hoặc quyền truy cập tài khoản nào được cấu hình trong môi trường làm việc này, vì vậy dự án hiện đã sẵn cấu hình nhưng chưa được xuất bản công khai.
