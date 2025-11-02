import os
import streamlit as st
from openai import OpenAI
from src.pdf_utils import read_pdf_text  # ← 既存のPDFテキスト抽出だけ使う

st.title("💬 Chatbot (OpenAI)")
st.caption("アップロードした研修ドキュメントを元に、AIと対話しながらレポートのドラフトを作成します。")

# ===== セッション初期化 =====
ss = st.session_state
if "doc_text" not in ss: ss.doc_text = ""
if "doc_pages" not in ss: ss.doc_pages = 0
if "questions" not in ss: ss.questions = []       # LLMが作る“問い”
if "q_index" not in ss: ss.q_index = 0           # 次に出す問いのindex
if "messages" not in ss:
    ss.messages = [{
        "role": "assistant",
        "content": (
            "💬 研修お疲れさまでした！\n"
            "まずは研修ドキュメント（PDF）をアップロードしてください。\n"
            "アップできたら **ok** とだけ送ってください。"
        ),
    }]

# ===== APIキー（Secrets / Env）=====
api_key    = (st.secrets.get("OPENAI_API_KEY")    or os.getenv("OPENAI_API_KEY")    or "").strip()
project_id = (st.secrets.get("OPENAI_PROJECT_ID") or os.getenv("OPENAI_PROJECT_ID") or "").strip()
if not api_key:
    st.error("OpenAIのAPIキーが設定されていません。Secretsに OPENAI_API_KEY を追加してください。")
    st.stop()

client_args = {"api_key": api_key}
if project_id: client_args["project"] = project_id
client = OpenAI(**client_args)
MODEL = "gpt-4o-mini"

# ===== PDFアップロード =====
uploaded_pdf = st.file_uploader("研修ドキュメント（PDF）をアップロード", type=["pdf"])
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.read()
    text, pages = read_pdf_text(pdf_bytes)
    ss.doc_text, ss.doc_pages = text, pages
    ss.questions, ss.q_index = [], 0
    st.success(f"📄 PDFを読み込みました：{pages}ページ")

# ===== 既存チャット表示 =====
for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ===== “ざっくり読んで問いを作る”関数 =====
def make_questions_from_doc(doc_text: str, n: int = 3) -> list[str]:
    """
    PDFの先頭～中盤をかいつまんでLLMに渡し、対話用の問いを n 個作ってもらう。
    ・研修のふり返り向け（感想→学び→現場適用）を意識
    ・短く、1問ずつ独立、箇条書きで返す
    """
    snippet = (doc_text or "").strip()
    if len(snippet) > 9000:
        # 適当に頭と末尾を繋いでコンテキストを増やす
        snippet = snippet[:6000] + "\n...\n" + doc_text[-2500:]

    sys = (
        "あなたは“研修のふり返り”を促す専門家です。"
        "以下の資料抜粋をざっくり把握し、学習者が答えやすい自然な問いを"
        "日本語で短く3～4文（1文=1問い）作ってください。"
        "・『Q1.』などの番号や記号は付けない\n"
        "・1行1問い、簡潔、具体\n"
        "・最初は感想→次に学び→最後に現場での適用/次の一歩、の順が望ましい"
    )
    user = f"【資料抜粋】\n{snippet}\n\n出力：箇条書き（- で始める）。{n}個。"

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    text = resp.choices[0].message.content.strip()

    # 箇条書きを行ごとに拾う
    qs = []
    for line in text.splitlines():
        line = line.strip(" ・-‐*●\t").strip()
        if not line:
            continue
        # 先頭の番号/括弧などを剥がす
        for pref in ("Q1", "Q2", "Q3", "Q4", "１", "２", "３"):
            line = line.removeprefix(pref).strip(".．:：）) 」").strip()
        qs.append(line)
        if len(qs) >= n:
            break
    return qs

def ask_next_question(prefix: bool = True) -> bool:
    """次の問いを1つ表示。なければFalse。"""
    if ss.q_index < len(ss.questions):
        q = ss.questions[ss.q_index]
        ss.q_index += 1
        msg = (("じゃあ今回の研修を振り返っていきましょう！\n" if prefix and ss.q_index == 1 else "") 
               + f"{q}\n\n自由に書いてください。")
        with st.chat_message("assistant"):
            st.markdown(msg)
        ss.messages.append({"role": "assistant", "content": msg})
        return True
    return False

# ===== 入力受付 =====
if prompt := st.chat_input("研修レポートの作成をはじめましょう（ここに話しかけてください）"):
    ss.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    normalized = prompt.strip().lower()

    # 「ok」合図で：未生成なら問いを作る→1つずつ投げる
    if normalized in {"ok", "ｏｋ", "おk", "了解", "upした", "アップした", "done", "完了"}:
        if not ss.doc_text:
            msg = "まだPDFが読み込まれていないようです。先に研修ドキュメント（PDF）をアップしてください。"
            with st.chat_message("assistant"): st.markdown(msg)
            ss.messages.append({"role": "assistant", "content": msg})
        else:
            if not ss.questions:
                ss.questions = make_questions_from_doc(ss.doc_text, n=3)
                ss.q_index = 0
            if not ask_next_question(prefix=True):
                msg = "資料から問いを作れませんでした。まずは**感想を気軽に書いてください😉**"
                with st.chat_message("assistant"): st.markdown(msg)
                ss.messages.append({"role": "assistant", "content": msg})
        st.stop()

    # すでに問いモードなら、回答のたびに次を出す
    if ss.questions and ss.q_index > 0 and ss.q_index <= len(ss.questions):
        if ask_next_question(prefix=False):
            st.stop()
        else:
            done = "ありがとう！予定していた問いは以上です。続けて深掘りや、レポート下書きの生成もできます。"
            with st.chat_message("assistant"): st.markdown(done)
            ss.messages.append({"role": "assistant", "content": done})

    # 通常応答（必要なら）
    context_snippet = ss.doc_text[:6000] if ss.doc_text else ""
    system_prompt = (
        "あなたは『研修レポート作成を支援する専門家』です。"
        "丁寧で論理的に、文脈に沿って分かりやすく説明してください。"
        + (f"\n\n--- 参考ドキュメント抜粋 ---\n{context_snippet}" if context_snippet else "")
    )
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system_prompt}] + ss.messages,
        stream=True,
    )
    with st.chat_message("assistant"):
        assistant_text = st.write_stream(stream)
    ss.messages.append({"role": "assistant", "content": assistant_text})
