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
    改行を含む「Q1.」「Q2.」形式の質問にも対応。
    """
    qs: List[str] = []
    # Q行を中心に、その次の1〜2行も一緒に見る
    lines = [l.strip() for l in doc_text.splitlines()]
    for i, line in enumerate(lines):
        if re.match(r'^(Q\d+|Ｑ\d+|問\d+|Q|Ｑ|問題)\s*[\.．:：]?', line):
            q_line = line
            # 次の行に内容がある場合は結合
            if i + 1 < len(lines) and lines[i + 1]:
                q_line += " " + lines[i + 1].strip()
            if i + 2 < len(lines) and len(lines[i + 1]) < 5 and lines[i + 2]:
                q_line += " " + lines[i + 2].strip()
            qs.append(q_line.strip())
        if len(qs) >= max_q:
            break
    return qs
