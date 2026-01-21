from pathlib import Path
import datetime
import random
import string
import tempfile
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main import html_to_image, html_to_pdf, resize_image_if_needed


OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class RenderRequest(BaseModel):
    html: str
    type: str = Field(default="jpg", description="Loại file xuất ra: 'jpg' hoặc 'pdf'")
    width: int | None = None
    height: int | None = None


class RenderResponse(BaseModel):
    url: str
    file_name: str


app = FastAPI(title="HTML2Image API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files để serve cả ảnh và PDF
app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")
# Giữ backward compatibility với /images
app.mount("/images", StaticFiles(directory=str(OUTPUT_DIR)), name="images")


@app.post("/render", response_model=RenderResponse)
async def render_html(request: Request, body: RenderRequest) -> RenderResponse:
    """
    Nhận HTML và render ra file (JPEG hoặc PDF) tùy theo type trong body.

    - type: "jpg" (mặc định) hoặc "pdf"
    - Tên file tự động: one_<5 ký tự ngẫu nhiên>_<YYYYMMDD>.<ext>
      Ví dụ: one_a3x9k_20251218.jpeg hoặc one_a3x9k_20251218.pdf
    """
    # Chuẩn hóa type: jpg, jpeg -> jpeg; pdf -> pdf
    output_type = body.type.lower()
    if output_type in ("jpg", "jpeg"):
        ext = "jpeg"
        is_pdf = False
    elif output_type == "pdf":
        ext = "pdf"
        is_pdf = True
    else:
        raise ValueError(f"Type không hợp lệ: {body.type}. Chỉ hỗ trợ 'jpg' hoặc 'pdf'")

    # Tạo tên file tự động
    file_name = _generate_file_name(ext)

    # Bọc HTML người dùng gửi để đảm bảo nền trắng & cấu trúc HTML đầy đủ
    if is_pdf:
        # CSS cho PDF - thêm hỗ trợ bảng lớn
        wrapped_html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8" />
            <style>
                @page {{
                    margin: 20mm;
                    size: A4;
                }}
                html, body {{
                    margin: 0;
                    padding: 0;
                    background-color: #ffffff;
                    font-family: Arial, sans-serif;
                }}
                /* Hỗ trợ bảng lớn - cho phép ngắt trang */
                table {{
                    page-break-inside: auto;
                    border-collapse: collapse;
                }}
                tr {{
                    page-break-inside: avoid;
                }}
            </style>
        </head>
        <body>
        {body.html}
        </body>
        </html>
        """
    else:
        # CSS cho ảnh (cải thiện chất lượng rendering text)
        wrapped_html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8" />
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    background-color: #ffffff;
                    /* Cải thiện chất lượng rendering text */
                    text-rendering: optimizeLegibility;
                    -webkit-font-smoothing: antialiased;
                    -moz-osx-font-smoothing: grayscale;
                    image-rendering: -webkit-optimize-contrast;
                    image-rendering: crisp-edges;
                }}
                * {{
                    /* Đảm bảo text được render sắc nét */
                    text-rendering: optimizeLegibility;
                    -webkit-font-smoothing: antialiased;
                }}
            </style>
        </head>
        <body>
        {body.html}
        </body>
        </html>
        """

    # Render theo type
    if is_pdf:
        html_to_pdf(
            html_content=wrapped_html,
            output_path=str(OUTPUT_DIR),
            file_name=file_name,
        )
        base_url = str(request.base_url).rstrip("/")
        url = f"{base_url}/files/{file_name}"
    else:
        size = None
        if body.width is not None and body.height is not None:
            size = (body.width, body.height)

        html_to_image(
            html_content=wrapped_html,
            output_path=str(OUTPUT_DIR),
            file_name=file_name,
            size=size,
            max_width=1280,  # Tự động resize về 1280px để tránh Telegram bóp lại làm mờ
        )
        base_url = str(request.base_url).rstrip("/")
        url = f"{base_url}/images/{file_name}"

    # Xóa file cũ nhất nếu số lượng >= 11 (giữ tối đa 10 file)
    _cleanup_old_files(max_files=10)

    return RenderResponse(url=url, file_name=file_name)


def _generate_file_name(ext: str) -> str:
    """Sinh tên file: one_<5 ký tự ngẫu nhiên>_<YYYYMMDD>.<ext>"""
    charset = string.ascii_lowercase + string.digits
    rand = "".join(random.choices(charset, k=5))
    today = datetime.date.today().strftime("%Y%m%d")
    return f"one_{rand}_{today}.{ext}"




@app.post("/render/binary")
async def render_html_binary(body: RenderRequest) -> Response:
    """
    Nhận HTML và render ra file (JPEG hoặc PDF) tùy theo type, trả về binary trực tiếp.

    - type: "jpg" (mặc định) hoặc "pdf"
    - Tên file tự động: one_<5 ký tự ngẫu nhiên>_<YYYYMMDD>.<ext>
    - Trả về binary của file trực tiếp trong response body.
    - Không lưu file vào thư mục output, chỉ tạo file tạm thời.
    """
    # Chuẩn hóa type: jpg, jpeg -> jpeg; pdf -> pdf
    output_type = body.type.lower()
    if output_type in ("jpg", "jpeg"):
        ext = "jpeg"
        is_pdf = False
        media_type = "image/jpeg"
    elif output_type == "pdf":
        ext = "pdf"
        is_pdf = True
        media_type = "application/pdf"
    else:
        raise ValueError(f"Type không hợp lệ: {body.type}. Chỉ hỗ trợ 'jpg' hoặc 'pdf'")

    # Tạo tên file tự động
    file_name = _generate_file_name(ext)

    # Bọc HTML người dùng gửi để đảm bảo nền trắng & cấu trúc HTML đầy đủ
    if is_pdf:
        # CSS cho PDF - thêm hỗ trợ bảng lớn
        wrapped_html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8" />
            <style>
                @page {{
                    margin: 20mm;
                    size: A4;
                }}
                html, body {{
                    margin: 0;
                    padding: 0;
                    background-color: #ffffff;
                    font-family: Arial, sans-serif;
                }}
                /* Hỗ trợ bảng lớn - cho phép ngắt trang */
                table {{
                    page-break-inside: auto;
                    border-collapse: collapse;
                }}
                tr {{
                    page-break-inside: avoid;
                }}
            </style>
        </head>
        <body>
        {body.html}
        </body>
        </html>
        """
    else:
        # CSS cho ảnh (cải thiện chất lượng rendering text)
        wrapped_html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8" />
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    background-color: #ffffff;
                    /* Cải thiện chất lượng rendering text */
                    text-rendering: optimizeLegibility;
                    -webkit-font-smoothing: antialiased;
                    -moz-osx-font-smoothing: grayscale;
                    image-rendering: -webkit-optimize-contrast;
                    image-rendering: crisp-edges;
                }}
                * {{
                    /* Đảm bảo text được render sắc nét */
                    text-rendering: optimizeLegibility;
                    -webkit-font-smoothing: antialiased;
                }}
            </style>
        </head>
        <body>
        {body.html}
        </body>
        </html>
        """

    # Tạo file tạm thời thay vì lưu vào output
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        if is_pdf:
            html_to_pdf(
                html_content=wrapped_html,
                output_path=str(temp_path),
                file_name=file_name,
            )
        else:
            size = None
            if body.width is not None and body.height is not None:
                size = (body.width, body.height)

            html_to_image(
                html_content=wrapped_html,
                output_path=str(temp_path),
                file_name=file_name,
                size=size,
                max_width=None,  # Không resize, giữ nguyên kích thước gốc cho binary
            )

        # Đọc file vào memory
        file_path = temp_path / file_name
        with open(file_path, "rb") as f:
            file_data = f.read()

    # Trả về binary của file
    # File tạm sẽ tự động bị xóa khi ra khỏi context manager
    return Response(
        content=file_data,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )


@app.post("/render/pdf", response_model=RenderResponse)
async def render_html_to_pdf(request: Request, body: RenderRequest) -> RenderResponse:
    """
    [DEPRECATED] Sử dụng POST /render với type="pdf" thay thế.
    
    Nhận HTML (và optional width/height), render ra file PDF và trả về URL PDF.

    - Luôn xuất PDF.
    - Tên file tự động: one_<5 ký tự ngẫu nhiên>_<YYYYMMDD>.pdf
      Ví dụ: one_a3x9k_20251218.pdf
    """
    ext = "pdf"

    # Tạo tên file tự động: one_<5 ký tự ngẫu nhiên>_<YYYYMMDD>.pdf
    file_name = _generate_file_name(ext)

    # Bọc HTML người dùng gửi để đảm bảo nền trắng & cấu trúc HTML đầy đủ
    # Thêm CSS để cải thiện chất lượng rendering
    wrapped_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8" />
        <style>
            @page {{
                margin: 20mm;
                size: A4;
            }}
            html, body {{
                margin: 0;
                padding: 0;
                background-color: #ffffff;
                font-family: Arial, sans-serif;
            }}
            * {{
                box-sizing: border-box;
            }}
        </style>
    </head>
    <body>
    {body.html}
    </body>
    </html>
    """

    html_to_pdf(
        html_content=wrapped_html,
        output_path=str(OUTPUT_DIR),
        file_name=file_name,
    )

    pdf_path = OUTPUT_DIR / file_name

    # Xóa file cũ nhất nếu số lượng >= 11 (giữ tối đa 10 file)
    _cleanup_old_files(max_files=10)

    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}/files/{file_name}"

    return RenderResponse(url=url, file_name=file_name)


@app.post("/render/pdf/binary")
async def render_html_to_pdf_binary(body: RenderRequest) -> Response:
    """
    [DEPRECATED] Sử dụng POST /render/binary với type="pdf" thay thế.
    
    Nhận HTML, render ra file PDF và trả về binary của PDF.

    - Luôn xuất PDF.
    - Tên file tự động: one_<5 ký tự ngẫu nhiên>_<YYYYMMDD>.pdf
    - Trả về binary của PDF trực tiếp trong response body.
    - Không lưu file vào thư mục output, chỉ tạo file tạm thời.
    """
    ext = "pdf"

    # Tạo tên file tự động: one_<5 ký tự ngẫu nhiên>_<YYYYMMDD>.pdf
    file_name = _generate_file_name(ext)

    # Bọc HTML người dùng gửi để đảm bảo nền trắng & cấu trúc HTML đầy đủ
    wrapped_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8" />
        <style>
            @page {{
                margin: 20mm;
                size: A4;
            }}
            html, body {{
                margin: 0;
                padding: 0;
                background-color: #ffffff;
                font-family: Arial, sans-serif;
            }}
            * {{
                box-sizing: border-box;
            }}
        </style>
    </head>
    <body>
    {body.html}
    </body>
    </html>
    """

    # Tạo file tạm thời thay vì lưu vào output
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        html_to_pdf(
            html_content=wrapped_html,
            output_path=str(temp_path),
            file_name=file_name,
        )

        # Đọc file PDF vào memory
        pdf_path = temp_path / file_name
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

    # Trả về binary của PDF
    # File tạm sẽ tự động bị xóa khi ra khỏi context manager
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )


def _cleanup_old_files(max_files: int = 10) -> None:
    """
    Xóa file cũ nhất nếu số lượng file trong output >= max_files + 1.
    Ưu tiên giữ lại file mới nhất.
    Hỗ trợ cả ảnh và PDF.
    
    :param max_files: Số lượng file tối đa được phép (mặc định 10).
    """
    # Lấy tất cả file ảnh và PDF trong output
    file_extensions = {'.jpeg', '.jpg', '.png', '.gif', '.webp', '.pdf'}
    files = [
        f for f in OUTPUT_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in file_extensions
    ]
    
    # Nếu số lượng < max_files + 1 thì không cần xóa
    if len(files) < max_files + 1:
        return
    
    # Sắp xếp theo thời gian modified (cũ nhất trước)
    files.sort(key=lambda f: f.stat().st_mtime)
    
    # Xóa các file cũ nhất cho đến khi còn lại max_files
    files_to_delete = files[:len(files) - max_files]
    for file_path in files_to_delete:
        try:
            file_path.unlink()
        except Exception:
            # Bỏ qua nếu không xóa được (file đang được sử dụng, v.v.)
            pass


@app.get("/health")
async def health():
    return {"status": "ok"}