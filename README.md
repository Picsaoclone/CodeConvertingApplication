# Code Converting Application

Ứng dụng web đơn giản cho phép **đăng ký/đăng nhập**, **chuyển đổi code giữa các ngôn ngữ** bằng OpenAI, và **lưu lịch sử chuyển đổi** vào Oracle Database.

> Ghi chú về cấu trúc thư mục: mã nguồn chính nằm trong `CodeConvertingApplication-main/CodeConvertingApplication/` (bên trong workspace hiện tại).

## Tính năng

- Đăng ký tài khoản: gọi API `POST /register` (lưu vào bảng `Users` trong Oracle)
- Đăng nhập: gọi API `POST /login` và nhận **JWT token** (lưu vào `localStorage` phía trình duyệt)
- Chuyển đổi code: gọi API `POST /convert`:
  - Backend gọi OpenAI Chat Completions để chuyển đổi code
  - Backend gọi Oracle stored procedure `StoreCodeConversion` để kiểm tra hợp lệ/giới hạn và lưu lịch sử
- Xem lịch sử chuyển đổi: `GET /conversion_history/<user_id>`
- Xem chi tiết một lần chuyển đổi: `GET /conversion_detail/<conversion_id>`
- Xem số lượt chuyển đổi còn lại trong ngày: `GET /get_conversion_count?user_id=...` (gọi Oracle function `GetRemainingConversions`)

## Công nghệ

- Backend: Flask
- OpenAI: Python SDK (`openai`)
- Database: Oracle (`cx_Oracle`)
- Frontend: HTML + JavaScript (các file tĩnh trong thư mục `static/`)

## Yêu cầu

- Windows (hoặc OS khác) + Python 3.9+ (khuyến nghị 3.10+)
- Oracle Database đang chạy (mặc định code dùng `localhost:1521`, `service_name="ORCL21"`)
- Oracle Instant Client (để `cx_Oracle` hoạt động)
- OpenAI API key

## Cấu hình

### 1) Oracle

File cấu hình hiện tại: `CodeConvertingApplication-main/CodeConvertingApplication/app/config.py`

- `ORACLE_USER` / `ORACLE_PASSWORD`: tài khoản Oracle
- Code đang hardcode DSN theo dạng:
  - `cx_Oracle.makedsn("localhost", 1521, service_name="ORCL21")`

Ngoài ra DB được kỳ vọng có các object sau (vì backend đang gọi trực tiếp):

- Bảng `Users` (ít nhất các cột: `user_id`, `username`, `email`, `password`, `created_at`)
- Sequence `seq_user_id`
- Bảng `Code_Conversions` (ít nhất các cột: `conversion_id`, `user_id`, `source_code`, `converted_code`, `source_language`, `target_language`, `conversion_time`)
- Stored procedure `StoreCodeConversion(...)`
- Function `GetRemainingConversions(user_id)`

### 2) OpenAI API key

Trong `CodeConvertingApplication-main/CodeConvertingApplication/app/routes.py` có dòng:

- `openai.api_key = Config.OPENAI_API_KEY`

Nhưng trong `config.py` hiện **chưa khai báo** `OPENAI_API_KEY`. Bạn cần bổ sung 1 trong 2 cách:

- Cách A (nhanh): thêm biến `OPENAI_API_KEY = "..."` vào `config.py`
- Cách B (khuyến nghị): đọc từ biến môi trường, ví dụ `OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")`

Model đang được gọi trong code: `gpt-4o-mini-2024-07-18`.

## Cài đặt

Từ thư mục workspace (nơi có file README này):

```bash
cd CodeConvertingApplication-main\CodeConvertingApplication
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Lưu ý: code còn import thêm `flask_cors` và `jwt` nhưng `requirements.txt` hiện chưa liệt kê. Nếu chạy bị lỗi thiếu package, cài thêm:

```bash
pip install flask-cors PyJWT
```

## Chạy ứng dụng

### 1) Chạy backend Flask

```bash
cd CodeConvertingApplication-main\CodeConvertingApplication
python run.py
```

Mặc định Flask chạy ở: `http://localhost:5000`.

### 2) Mở giao diện web

Frontend là file HTML tĩnh (không được backend serve trực tiếp theo cấu hình hiện tại), vì vậy bạn mở trực tiếp trong trình duyệt:

- `CodeConvertingApplication-main/CodeConvertingApplication/static/login.html`

Luồng sử dụng:

1. Sign up ở `sign_up.html`
2. Login ở `login.html` (token sẽ được lưu vào `localStorage`)
3. Sau khi login sẽ chuyển hướng sang `index.html` để convert và xem history

## API

Base URL: `http://localhost:5000`

### `POST /register`

Body JSON:

```json
{ "username": "alice", "email": "alice@example.com", "password": "123" }
```

### `POST /login`

Body JSON:

```json
{ "username": "alice", "password": "123" }
```

Trả về `token` (JWT).

### `POST /convert`

Body JSON:

```json
{
  "user_id": 1,
  "source_code": "print(\"Hello\")",
  "source_language": "Python",
  "target_language": "Java"
}
```

Ghi chú lỗi Oracle được handle đặc biệt:

- `ORA-20002`: vượt quá giới hạn chuyển đổi trong ngày
- `ORA-20001`: code không hợp lệ

### `GET /conversion_history/<user_id>`

Trả về danh sách record (dạng mảng các tuple theo thứ tự cột query).

### `GET /conversion_detail/<conversion_id>`

Trả về `source_code` và `converted_code` (có xử lý trường hợp CLOB).

### `GET /get_conversion_count?user_id=...`

Trả về `remaining_conversions` từ Oracle function `GetRemainingConversions`.

## Workflow

Sơ đồ workflow đã được render sẵn:

- `CodeConvertingApplication-main/CodeConvertingApplication/code_conversion_workflow.png`

Và file DOT nguồn:

- `CodeConvertingApplication-main/CodeConvertingApplication/code_conversion_workflow`

## Lưu ý bảo mật (theo code hiện tại)

- Mật khẩu đang được lưu/so sánh dạng plaintext trong DB.
- JWT secret đang hardcode là `'secret'` trong `routes.py`.
- Thông tin Oracle user/password đang hardcode trong `config.py`.

Nếu dùng cho production, nên thay bằng hash mật khẩu (bcrypt/argon2), secret qua biến môi trường, và không commit credential vào repo.
