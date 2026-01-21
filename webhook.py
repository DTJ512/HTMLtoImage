import os

import uvicorn


def main() -> None:
    """
    Entry point cho server.
    
    - Nếu chạy trên IIS: đọc HTTP_PLATFORM_PORT từ environment variable
    - Nếu chạy local: sử dụng port 8000 mặc định
    """
    # Kiểm tra xem có HTTP_PLATFORM_PORT (IIS) hay không
    port = int(os.environ.get("HTTP_PLATFORM_PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    
    # Nếu không phải IIS, có thể bind toàn bộ interface để test từ máy khác
    if "HTTP_PLATFORM_PORT" not in os.environ:
        host = "0.0.0.0"

    # Chạy FastAPI app trong api.py
    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()