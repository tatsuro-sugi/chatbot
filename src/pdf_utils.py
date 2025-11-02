# src/pdf_utils.py
import io
import re
from typing import Tuple, List
from pypdf import PdfReader

def read_pdf_text(file_bytes: bytes) -> Tuple[str, int]:
    """PDF全体のテキストとページ数を返す"""
    try:
        pdf = PdfReader(io.BytesIO(file_bytes))
        pages: List[str] = []
        for p in pdf.pages:
            txt = p.extract_text() or ""
            pages.append(txt)
        text = "\n".join(pages).strip()
        return text, len(pdf.pages)
    except Exception:
        return "", 0

def extract_questions(doc_text: str, max_q: int = 10) -> List[str]:
    """
    資料内の“問い”を抽出して返す。
      Q: xxx / Q1: xxx / Ｑ２：xxx / 問1 xxx / 【問3】xxx / 問題：xxx
    等の表記に対応（全角半角）。
    """
    lines = [l.strip() for l in doc_text.splitlines()]
    qs: List[str] = []

    patterns = [
        r'^\s*[QＱ]\s*[:：]\s*(.+)$',
        r'^\s*[QＱ]\s*\d+\s*[:：\.\．\)）-]?\s*(.+)$',
        r'^\s*問\s*\d+\s*[:：\.\．\)）-]?\s*(.+)$',
        r'^\s*【?問\d+】?\s*(.+)$',
        r'^\s*問題\s*[:：]\s*(.+)$',
    ]
    regexes = [re.compile(p) for p in patterns]

    for ln in lines:
        for rx in regexes:
            m = rx.match(ln)
            if m:
                q = m.group(1).strip()
                q = re.sub(r'[　\s]+$', '', q)
                if q and q not in qs:
                    qs.append(q)
                break
        if len(qs) >= max_q:
            break

    return qs
