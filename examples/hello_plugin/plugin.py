# examples/hello_plugin/plugin.py
"""
Hello Plugin — Demo plugin cho CogniCraft ecosystem
"""
from datetime import datetime


PLUGIN_INFO = {
    "id": "hello-plugin",
    "version": "1.0.0",
    "commands": [
        {
            "name": "hello",
            "description": "Chào hỏi",
            "usage": "hello [tên]"
        },
        {
            "name": "hello_time",
            "description": "Hiện giờ hiện tại",
            "usage": "hello_time"
        }
    ]
}


def hello(name: str = "bạn") -> str:
    """Chào hỏi"""
    return f"👋 Xin chào {name}! Chào mừng đến CogniCraft."


def hello_time() -> str:
    """Hiện thời gian"""
    now = datetime.now()
    return f"🕐 Bây giờ là {now.strftime('%H:%M:%S - %d/%m/%Y')}"


def run(command: str, args: list = None) -> str:
    """
    Entry point — dispatcher commands

    Args:
        command: tên command (không có prefix)
        args: list arguments

    Returns:
        String response
    """
    args = args or []

    if command == "hello":
        name = args[0] if args else "bạn"
        return hello(name)
    elif command == "hello_time":
        return hello_time()
    else:
        return f"❌ Command không tồn tại: {command}"


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print(hello("Dat"))
    print(hello_time())
    print(run("hello", ["Test"]))
    print(run("hello_time"))