# HTML2Image API

Dự án Python chuyển đổi nội dung HTML thành hình ảnh (PNG/JPEG) hoặc PDF thông qua FastAPI.

## Tính năng

- ✅ Chuyển đổi HTML sang hình ảnh (JPEG/PNG)
- ✅ Chuyển đổi HTML sang PDF
- ✅ Tự động cắt phần nền trắng thừa
- ✅ Tự động resize ảnh về kích thước phù hợp
- ✅ API RESTful với FastAPI
- ✅ Hỗ trợ trả về file hoặc binary trực tiếp
- ✅ Tự động dọn dẹp file cũ

## Yêu cầu

- Python 3.10 trở lên
- pip đã được cài đặt

## Cài đặt

### 1. Clone repository

```bash
git clone <repository-url>
cd HTML2Image
```

### 2. Tạo virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Cài đặt dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Cài đặt Playwright browsers (bắt buộc cho PDF generation)

```bash
playwright install chromium
```

## Sử dụng

### Chạy API server

```bash
python webhook.py
```

Hoặc sử dụng uvicorn trực tiếp:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

API sẽ chạy tại: `http://localhost:8000`

### API Endpoints

#### 1. Render HTML thành ảnh/PDF (trả về URL)

**POST** `/render`

**Request Body:**
```json
{
  "html": "<h1>Hello World</h1>",
  "type": "jpg",  // "jpg" hoặc "pdf"
  "width": 1920,  // optional
  "height": 1080  // optional
}
```

**Response:**
```json
{
  "url": "http://localhost:8000/images/one_a3x9k_20251218.jpeg",
  "file_name": "one_a3x9k_20251218.jpeg"
}
```

#### 2. Render HTML thành ảnh/PDF (trả về binary)

**POST** `/render/binary`

**Request Body:** (giống như `/render`)

**Response:** Binary file trực tiếp

#### 3. Health check

**GET** `/health`

**Response:**
```json
{
  "status": "ok"
}
```

### Sử dụng thư viện trực tiếp

```python
from main import html_to_image, html_to_pdf

# Chuyển HTML sang ảnh
html_content = "<h1>Hello World</h1>"
image_path = html_to_image(
    html_content=html_content,
    output_path="output",
    file_name="example.png",
    max_width=1280
)

# Chuyển HTML sang PDF
pdf_path = html_to_pdf(
    html_content=html_content,
    output_path="output",
    file_name="example.pdf"
)
```

## Cấu trúc dự án

```
HTML2Image/
├── api.py              # FastAPI application
├── main.py             # Core functions (html_to_image, html_to_pdf)
├── webhook.py          # Entry point cho server
├── web.config          # IIS configuration (optional)
├── requirements.txt    # Python dependencies
└── README.md          # Documentation
```

## Deployment

### IIS (Windows)

1. Cấu hình `web.config` với đường dẫn Python và virtual environment của bạn
2. Đảm bảo IIS có quyền truy cập thư mục dự án
3. Cài đặt `httpPlatformHandler` cho IIS

### Docker (sắp tới)

Dockerfile sẽ được thêm trong tương lai.

## Dependencies

- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `html2image`: HTML to image conversion
- `Pillow`: Image processing
- `playwright`: PDF generation

## License

[Thêm license của bạn ở đây]

## Contributing

[Thêm hướng dẫn đóng góp nếu cần]
