# utils/text_cleanup.py
def cleanup_text(line: str) -> str:
    return (
        line.replace("\u200b", "")
            .replace("\ufeff", "")
            .strip()
    )
