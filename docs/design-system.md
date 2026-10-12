# Bảng thiết kế

## Hướng nghệ thuật

Nhà hàng mang cảm giác ấm áp, mộc mạc và chỉn chu. Nền kem như giấy, chữ than dễ đọc, xanh ô liu gợi nguyên liệu tự nhiên và vàng đồng dành cho điểm nhấn. Ảnh món ăn dùng khung hình lớn, ánh sáng tự nhiên; tránh các dải thẻ đồng nhất và giữ khoảng thở rộng.

| Thành phần | Quyết định | Mã màu / kiểu chữ |
| --- | --- | --- |
| Nền chính | Kem ấm | `#F6F1E8` |
| Bề mặt | Trắng giấy | `#FFFDF8` |
| Chữ chính | Than đen dịu | `#292820` |
| Chữ phụ | Xám ấm | `#777367` |
| Màu thương hiệu | Xanh ô liu | `#596348` |
| Điểm nhấn | Vàng đồng | `#B38A4B` |
| Tiêu đề | Serif có sẵn của hệ thống | Georgia, Times New Roman |
| Nội dung | Sans-serif có sẵn của hệ thống | Segoe UI, Arial |

Các biến màu và phông được khai báo trong `style.css` để trang và các thành phần về sau dùng chung.

## Bố cục mobile-first

- Bắt đầu từ màn hình rộng 320 px; lề nội dung điện thoại 20 px.
- Xếp nội dung theo một cột trên điện thoại, rồi mở rộng thành bố cục lệch nhịp ở màn hình lớn (điểm mở rộng ban đầu 768 px, lề 48 px).
- Dành ưu tiên thị giác cho ảnh món ăn lớn; xen kẽ ảnh và nội dung thay vì lặp lại một lưới thẻ đều nhau.
- Giữ khoảng trắng thoáng, phân cấp tiêu đề rõ, nút đặt bàn nổi bật.
- Khi bổ sung hiệu ứng cuộn, dùng chuyển động ngắn, nhẹ; tôn trọng `prefers-reduced-motion`.

## Khung hiện tại

`index.html` là trang HTML hợp lệ, responsive viewport đã khai báo, chưa có nội dung hiển thị. CSS chỉ đặt nền, màu, phông, lề responsive và hỗ trợ giảm chuyển động — sẵn sàng để xây giao diện mà không làm trang khởi đầu mất trạng thái trống.
