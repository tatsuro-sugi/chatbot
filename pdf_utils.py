# src/pdf_utils.py
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
            # extract_text() が None のページは空文字で埋める
            pages.append(p.extract_text() or "")
        text = "\n".join(pages).strip()
        return text, len(pdf.pages)
    except Exception:
        # 画像型PDFなどで抽出できない場合は空で返す
        return "", 0
