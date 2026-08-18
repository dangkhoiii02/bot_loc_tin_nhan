# Kế hoạch triển khai bot lọc tin nhắn tự động

## 1. Mục tiêu

Xây dựng một ứng dụng Python chạy trên máy tính cá nhân, có giao diện web local để:

- Dán nhiều dòng tin nhắn vào một lần.
- Loại bỏ thời gian và tên người gửi.
- Chuẩn hóa khoảng trắng.
- Lọc các nội dung trùng lặp nhưng vẫn giữ thứ tự xuất hiện đầu tiên.
- Hiển thị kết quả, số dòng đầu vào, số dòng đầu ra và số dòng trùng đã loại.
- Kết nối với bot thông qua giao diện cấu hình.
- Mở riêng webhook bot ra Internet bằng ngrok.

Ví dụ:

```text
Input:
[17/08/2026 18:16] Mike: cuu cái b
[17/08/2026 18:18] Boy Bad: sao b
[17/08/2026 18:18] Mike: tui chạy r b
[17/08/2026 18:16] Mike: cuu cái b

Output:
cuu cái b
sao b
tui chạy r b
```

## 2. Kiến trúc

Ứng dụng gồm các thành phần chính:

```text
Trình duyệt
    │
    ▼
Local Web UI - Flask :5000
    │
    ├── Filter Engine
    │       ├── Parser
    │       ├── Normalizer
    │       └── Deduplicator
    │
    └── Bot Manager
            │
            ▼
        Webhook Server :5001
            │
            ▼
        Ngrok HTTPS Tunnel
            │
            ▼
        Bot API
```

Định hướng an toàn:

- Cổng `5000` chỉ phục vụ giao diện quản trị trên `127.0.0.1`.
- Chỉ cổng `5001` dành cho webhook được đưa qua ngrok.
- Filter Engine là module dùng chung cho thao tác lọc thủ công và xử lý tin nhắn từ bot.
- Giai đoạn đầu có thể triển khai Telegram trước; kiến trúc Bot Adapter cho phép bổ sung Discord hoặc nền tảng khác sau này.

## 3. Chức năng lọc tin nhắn

### 3.1. Luồng xử lý

```text
Đọc từng dòng
    ↓
Phân tích timestamp, username và message
    ↓
Chỉ lấy phần message
    ↓
Chuẩn hóa khoảng trắng
    ↓
Kiểm tra nội dung đã xuất hiện chưa
    ↓
Giữ dòng đầu tiên, loại các dòng sau bị trùng
```

### 3.2. Định dạng hỗ trợ ban đầu

```text
[17/08/2026 18:16] Mike: cuu cái b
```

Regex đề xuất:

```python
r'^\[(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\]\s+([^:]+):\s*(.*)$'
```

Regex tách được:

```text
Ngày      = 17/08/2026
Thời gian = 18:16
Người gửi = Mike
Nội dung  = cuu cái b
```

### 3.3. Quy tắc lọc trùng

- Dùng một tập `seen` để ghi nhận nội dung đã xuất hiện.
- Giữ nguyên thứ tự xuất hiện của dòng đầu tiên.
- Chuẩn hóa khoảng trắng bằng `" ".join(message.split())` trước khi so sánh.
- Mặc định phân biệt chữ hoa và chữ thường: `Hello` và `hello` là hai nội dung khác nhau.
- Bản MVP có thể bỏ qua dòng trống và giữ nguyên các dòng sai định dạng hoặc báo chúng trong thống kê.

Các tùy chọn có thể bổ sung trên UI:

- Bỏ timestamp.
- Bỏ tên người gửi.
- Lọc trùng.
- Chuẩn hóa khoảng trắng.
- Không phân biệt chữ hoa/thường.
- Sắp xếp theo thời gian.

## 4. Giao diện local

Giao diện HTML/CSS/JavaScript đơn giản, được Flask phục vụ tại:

```text
http://127.0.0.1:5000
```

### 4.1. Khu vực lọc tin nhắn

- Ô `Input` để dán nội dung gốc.
- Ô `Output` chỉ đọc để hiển thị kết quả.
- Nút `Lọc tin nhắn`.
- Nút `Copy` để sao chép kết quả.
- Nút `Xóa` để xóa input/output.
- Thống kê: số dòng input, số dòng output và số dòng trùng.

### 4.2. Khu vực cấu hình bot

Các trường đề xuất:

| Trường | Mục đích |
|---|---|
| Bot Platform | Nền tảng bot, bắt đầu với Telegram |
| Bot Token | Token gọi Bot API |
| Chat/Channel ID | Nơi bot nhận hoặc gửi tin |
| Webhook Secret | Xác thực request gửi đến webhook |
| Ngrok Authtoken | Xác thực phiên ngrok |
| Webhook Port | Mặc định `5001` |

Trạng thái cần hiển thị:

```text
Local Server  ● Online
Bot           ● Connected
Ngrok         ● Online

Public Webhook:
https://xxxx.ngrok.app/webhook/xxxx
```

Giao diện quản trị không được mở qua ngrok.

## 5. Cấu hình bot

Nên thiết kế lớp trừu tượng chung:

```python
class BotAdapter:
    def connect(self): ...
    def disconnect(self): ...
    def send_message(self, text): ...
    def set_webhook(self, url): ...
```

Adapter đầu tiên có thể là:

```python
class TelegramBot(BotAdapter):
    ...
```

Bot Manager chịu trách nhiệm:

- Kiểm tra token và các trường bắt buộc.
- Khởi động hoặc dừng webhook server.
- Đăng ký hoặc xóa webhook với Bot API.
- Gọi Filter Engine khi có tin nhắn mới.
- Gửi kết quả đã lọc về đúng chat/channel.
- Cập nhật trạng thái kết nối và thông báo lỗi cho UI.

## 6. Luồng connect/disconnect

### 6.1. Khi bấm Connect

```text
Bấm CONNECT
    ↓
Kiểm tra cấu hình và Bot Token
    ↓
Khởi động Webhook Server :5001
    ↓
Khởi động ngrok
    ↓
Nhận public HTTPS URL
    ↓
Tạo URL /webhook/<secret>
    ↓
Đăng ký webhook với Bot API
    ↓
Gửi request kiểm tra kết nối
    ↓
Cập nhật trạng thái CONNECTED
```

### 6.2. Khi bấm Disconnect

```text
Bấm DISCONNECT
    ↓
Xóa webhook trên Bot API
    ↓
Dừng bot/webhook server
    ↓
Đóng ngrok tunnel
    ↓
Xóa public URL khỏi trạng thái hiện tại
```

### 6.3. Khi bot nhận tin nhắn

```text
Bot API
    ↓
Webhook
    ↓
Xác thực secret
    ↓
Trích xuất nội dung tin nhắn
    ↓
Filter Engine
    ↓
Gửi kết quả đã lọc về bot
```

## 7. Cấu trúc source

```text
message-filter-bot/
├── app.py
├── config.py
├── requirements.txt
├── .env
├── .gitignore
│
├── core/
│   ├── __init__.py
│   ├── parser.py
│   ├── filter.py
│   └── normalizer.py
│
├── bot/
│   ├── __init__.py
│   ├── manager.py
│   ├── telegram.py
│   └── webhook.py
│
├── tunnel/
│   ├── __init__.py
│   └── ngrok_manager.py
│
├── templates/
│   └── index.html
│
├── static/
│   ├── app.js
│   └── style.css
│
└── tests/
    ├── test_parser.py
    └── test_filter.py
```

Vai trò chính:

- `app.py`: khởi động Flask, render UI và khai báo route.
- `config.py`: đọc cấu hình từ biến môi trường hoặc cấu hình phiên chạy.
- `parser.py`: phân tích định dạng timestamp, username và message.
- `normalizer.py`: xử lý khoảng trắng và các quy tắc chuẩn hóa.
- `filter.py`: lọc trùng và trả về kết quả cùng thống kê.
- `manager.py`: điều phối connect/disconnect.
- `telegram.py`: triển khai Telegram Bot API.
- `webhook.py`: nhận và xác thực request webhook.
- `ngrok_manager.py`: khởi động, lấy URL và dừng tunnel ngrok.

## 8. API

### `GET /`

Hiển thị giao diện local.

### `POST /api/filter`

Request:

```json
{
  "text": "[17/08/2026 18:16] Mike: cuu cái b"
}
```

Response:

```json
{
  "result": "cuu cái b",
  "input_count": 1,
  "output_count": 1,
  "duplicate_count": 0,
  "invalid_count": 0
}
```

### `POST /api/bot/connect`

Nhận cấu hình phiên hiện tại, kiểm tra token, khởi động webhook/ngrok và đăng ký webhook.

### `POST /api/bot/disconnect`

Xóa webhook, dừng bot và đóng tunnel ngrok.

### `GET /api/bot/status`

Trả về trạng thái local server, bot, ngrok và public webhook URL.

### `POST /webhook/<secret>`

Endpoint dành riêng cho Bot API. Request phải được kiểm tra secret trước khi xử lý.

## 9. Năm giai đoạn triển khai

### Giai đoạn 1 — Filter Engine

Hoàn thiện parser, normalizer và deduplicator độc lập với giao diện.

Kiểm thử tối thiểu:

- Dòng trùng hoàn toàn.
- Dòng trùng nhưng khác timestamp hoặc username.
- Nội dung tiếng Việt có dấu.
- Nội dung có ký tự `:`.
- Khoảng trắng thừa.
- Dòng rỗng.
- Dòng sai định dạng.
- Nhiều dòng liên tiếp và giữ đúng thứ tự.

### Giai đoạn 2 — Local Web UI

Chạy ứng dụng tại `127.0.0.1:5000` và hoàn thiện:

- Paste input.
- Lọc tin nhắn.
- Copy output.
- Clear form.
- Hiển thị thống kê.

### Giai đoạn 3 — Bot Adapter

Tạo `BotAdapter`, triển khai adapter Telegram đầu tiên và kiểm tra gửi/nhận tin nhắn mà chưa cần ngrok tự động hóa hoàn toàn.

### Giai đoạn 4 — Webhook và ngrok

Khi Connect được bấm:

```text
Khởi động webhook → khởi động ngrok → lấy URL → đăng ký webhook
```

Khi Disconnect được bấm, thực hiện chuỗi ngược lại và dọn dẹp tài nguyên.

### Giai đoạn 5 — Ổn định và mở rộng

Bổ sung:

- Logging rõ ràng.
- Xử lý lỗi và tự kết nối lại.
- Kiểm tra trạng thái bot/ngrok.
- Lịch sử xử lý hoặc xuất TXT.
- Cấu hình nhiều format tin nhắn.
- Adapter cho nền tảng khác.
- Server phù hợp hơn nếu chạy thường xuyên thay cho development server mặc định.

## 10. Bảo mật token

- Không hard-code Bot Token hoặc Ngrok Authtoken trong source.
- Dùng `.env` cho môi trường local và thêm `.env` vào `.gitignore`.
- Nếu nhập token trên UI, ưu tiên chỉ giữ trong RAM trong phiên hiện tại ở bản MVP.
- Không ghi token vào log hoặc thông báo lỗi.
- Che token trong các ô nhập liệu bằng `type="password"`.
- Dùng webhook secret khó đoán và kiểm tra secret trước khi xử lý request.
- Không expose port `5000` qua ngrok.
- Chỉ gửi dữ liệu cần thiết đến Bot API.
- Khi Disconnect, xóa webhook và đóng tunnel để giảm bề mặt truy cập.

Ví dụ `.env`:

```text
BOT_TOKEN=...
NGROK_AUTHTOKEN=...
WEBHOOK_PORT=5001
WEBHOOK_SECRET=...
```

## 11. MVP cuối cùng

MVP cần đạt các khả năng sau:

1. Chạy một lệnh để mở server local.
2. Truy cập UI tại `http://127.0.0.1:5000`.
3. Dán tin nhắn có timestamp và username.
4. Bấm `FILTER` để nhận danh sách message đã làm sạch và loại trùng.
5. Copy hoặc xóa kết quả.
6. Nhập thông tin bot và ngrok trong khu vực cấu hình.
7. Bấm `CONNECT` để khởi động webhook, ngrok và đăng ký Bot API.
8. Nhận tin nhắn qua webhook, dùng cùng Filter Engine và gửi kết quả về bot.
9. Bấm `DISCONNECT` để dừng an toàn.

## 12. Thứ tự triển khai đề xuất

```text
1. Filter Engine
       ↓
2. Unit tests cho parser và filter
       ↓
3. Local Flask UI
       ↓
4. Bot Adapter
       ↓
5. Webhook Server
       ↓
6. Ngrok Manager
       ↓
7. Connect / Disconnect
       ↓
8. Bảo mật và xử lý lỗi
       ↓
9. Kiểm thử end-to-end
```

Ưu tiên hoàn thành và kiểm thử Filter Engine trước. Đây là phần cốt lõi, được cả giao diện local và bot sử dụng; khi phần này ổn định, các phần kết nối còn lại sẽ dễ phát triển và kiểm tra hơn.
