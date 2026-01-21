from pathlib import Path
import asyncio

from html2image import Html2Image
from PIL import Image
from playwright.async_api import async_playwright


def estimate_size_from_html(html_content: str) -> tuple[int, int]:
    """
    Ước lượng kích thước ảnh (width, height) dựa trên nội dung HTML.

    Ở đây: 
    - Cố định width = 1920px (tỷ lệ 16:9, phù hợp trình chiếu / báo cáo).
    - Height được ước lượng theo số lượng <tr> (số dòng trong bảng).
    """
    width = 1920

    # Đếm số dòng <tr> để ước lượng chiều cao cần thiết
    row_count = html_content.lower().count("<tr")

    # Các tham số này quyết định khoảng trống trên/dưới
    base_height = 200  # phần header, margin trên/dưới
    row_height = 28    # chiều cao ước lượng mỗi dòng
    height = base_height + row_count * row_height

    # Buffer nhẹ để tránh bị cắt, nhưng không quá dư
    height = int(height * 1.03)

    # Giới hạn cho đẹp, tránh quá dài hoặc quá ngắn
    min_height = 800
    max_height = 2200
    height = max(min_height, min(height, max_height))

    return width, height


def html_to_image(
    html_content: str,
    output_path: str = "output",
    file_name: str = "example.png",
    size: tuple[int, int] | None = None,
    max_width: int | None = 1280,
) -> str:
    """
    Chuyển nội dung HTML sang ảnh (PNG/JPEG tùy theo phần mở rộng của file_name).

    :param html_content: Chuỗi HTML cần render.
    :param output_path: Thư mục lưu ảnh xuất ra.
    :param file_name: Tên file ảnh (ví dụ: "sample.png").
    :param size: Kích thước ảnh (width, height). 
                 Nếu None -> dùng size lớn rồi tự cắt phần nền trắng thừa phía dưới.
    :param max_width: Chiều rộng tối đa sau khi resize (mặc định 1280px).
                      Nếu None -> không resize.
    :return: Đường dẫn file ảnh đã tạo (dạng string).
    """
    # Nếu không truyền size thì dùng size lớn, sau đó sẽ auto-crop phần trắng
    if size is None:
        size = (1920, 2600)

    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / file_name

    hti = Html2Image(output_path=str(output_dir))
    hti.size = size
    hti.screenshot(html_str=html_content, save_as=file_name)

    # Tự động cắt phần nền trắng thừa (dưới + mép phải) để ảnh "ôm" nội dung
    _auto_crop_whitespace(str(output_file))

    # Resize về max_width nếu được chỉ định
    if max_width is not None:
        resize_image_if_needed(str(output_file), max_width=max_width)

    return str(output_file)


def _auto_crop_whitespace(
    image_path: str,
    bg_color: tuple[int, int, int] = (255, 255, 255),
    tolerance: int = 3,
    padding: int = 2,
) -> None:
    """
    Cắt bớt phần nền trắng thừa ở mép dưới ảnh.

    Lưu ý: Hoạt động tốt khi nền là màu trắng (hoặc gần trắng).
    """
    try:
        img = Image.open(image_path)
    except Exception:
        return

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    pixels = img.load()
    width, height = img.size

    def is_bg(pixel) -> bool:
        r, g, b = pixel[:3]
        return (
            abs(r - bg_color[0]) <= tolerance
            and abs(g - bg_color[1]) <= tolerance
            and abs(b - bg_color[2]) <= tolerance
        )

    last_non_bg_y = None
    last_non_bg_x = None

    # Dò từ dưới lên, tìm dòng cuối cùng có pixel khác nền trắng
    for y in range(height - 1, -1, -1):
        row_is_bg = True
        for x in range(width):
            if not is_bg(pixels[x, y]):
                row_is_bg = False
                break
        if not row_is_bg:
            last_non_bg_y = y
            break

    # Dò từ phải sang trái, tìm cột cuối cùng có pixel khác nền trắng
    for x in range(width - 1, -1, -1):
        col_is_bg = True
        for y in range(height):
            if not is_bg(pixels[x, y]):
                col_is_bg = False
                break
        if not col_is_bg:
            last_non_bg_x = x
            break

    if last_non_bg_y is None:
        last_non_bg_y = height - 1
    if last_non_bg_x is None:
        last_non_bg_x = width - 1

    # Cắt đến ngay sau vùng có nội dung, chừa padding px đệm
    crop_bottom = min(height, last_non_bg_y + 1 + padding)
    crop_right = min(width, last_non_bg_x + 1 + padding)

    box = (0, 0, crop_right, crop_bottom)
    img_cropped = img.crop(box)
    img_cropped.save(image_path)


def resize_image_if_needed(
    image_path: str,
    max_width: int = 1280,
    quality: int = 100,
) -> None:
    """
    Resize ảnh nếu chiều rộng lớn hơn max_width, giữ nguyên tỷ lệ khung hình.
    
    :param image_path: Đường dẫn file ảnh cần resize.
    :param max_width: Chiều rộng tối đa (mặc định 1280px cho Telegram).
    :param quality: Chất lượng JPEG khi lưu lại (1-100, mặc định 95).
    """
    try:
        img = Image.open(image_path)
    except Exception:
        return
    
    width, height = img.size
    
    # Nếu chiều rộng <= max_width thì không cần resize
    if width <= max_width:
        return
    
    # Tính chiều cao mới giữ nguyên tỷ lệ
    ratio = max_width / width
    new_height = int(height * ratio)
    
    # Resize ảnh với thuật toán LANCZOS (chất lượng cao)
    img_resized = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
    
    # Lưu lại với chất lượng cao nhất (quality=100, không optimize để giữ chất lượng)
    if image_path.lower().endswith(('.jpg', '.jpeg')):
        img_resized.save(image_path, 'JPEG', quality=quality, optimize=False)
    else:
        img_resized.save(image_path, optimize=True)


def html_to_pdf(
    html_content: str,
    output_path: str = "output",
    file_name: str = "example.pdf",
) -> str:
    """
    Chuyển nội dung HTML sang file PDF sử dụng Playwright.

    :param html_content: Chuỗi HTML cần render.
    :param output_path: Thư mục lưu file PDF xuất ra.
    :param file_name: Tên file PDF (ví dụ: "sample.pdf").
    :return: Đường dẫn file PDF đã tạo (dạng string).
    """
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / file_name

    # Sử dụng Playwright để render HTML sang PDF
    async def _generate_pdf():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            # Load HTML content
            await page.set_content(html_content, wait_until="networkidle")
            
            # Generate PDF
            await page.pdf(
                path=str(output_file),
                format="A4",
                margin={
                    "top": "20mm",
                    "right": "20mm",
                    "bottom": "20mm",
                    "left": "20mm",
                },
                print_background=True,
            )
            
            await browser.close()
    
    # Chạy async function
    try:
        asyncio.run(_generate_pdf())
    except RuntimeError:
        # Nếu đã có event loop đang chạy, dùng get_event_loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Tạo task mới nếu đang trong async context
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _generate_pdf())
                future.result()
        else:
            loop.run_until_complete(_generate_pdf())

    return str(output_file)