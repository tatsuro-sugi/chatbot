import io
from typing import Tuple, List
from pypdf import PdfReader

def read_pdf_text(file_bytes: bytes) -> Tuple[str, int]:
    """
    PDF全ページからテキストを抽出して返す。
    戻り値: (抽出テキスト, ページ数)
    """
    try:
        pdf = PdfReader(io.BytesIO(file_bytes))
        pages: List[str] = []
        for p in pdf.pages:
            text = p.extract_text() or ""  # None の場合は空文字で補う
            pages.append(text)
        text = "\n".join(pages).strip()
        return text, len(pdf.pages)
    except Exception:
        # 読み取り失敗時は空で返す
        return "", 0
