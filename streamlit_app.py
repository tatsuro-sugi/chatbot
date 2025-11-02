import os
import streamlit as st
from openai import OpenAI
from src.pdf_utils import read_pdf_text

st.title("💬 Chatbot (OpenAI)")
st.caption("アップロードした研修ドキュメントを元に、AIと対話しながらレポートのドラフトを作成します。")

# ===== PDFアップロード =====
uploaded_pdf = st.file_uploader("研修ドキュメント（PDF）をアップロード", type=["pdf"])

if "doc_text" not in st.session_state:
    st.session_state.doc_text = ""
if "doc_pages" not in st.session_state:
    st.session_state.doc_pages = 0

if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.read()
    text, pages = read_pdf_text(pdf_bytes)
    st.session_state.doc_text = text
    st.session_state.doc_pages = pages
    st.success(f"📄 PDFを読み込みました：{pages}ページ")
else:
    st.info("PDFをアップロードすると内容を解析できます。")

# ===== APIキー（Secrets / 環境変数から自動取得）=====
api_key = (st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
project_id = (st.secrets.get("OPENAI_PROJECT_ID") or os.getenv("OPENAI_PROJECT_ID") or "").strip()
if not api_key:
    st.error("OpenAIのAPIキーが設定されていません。Secretsに OPENAI_API_KEY を追加してください。")
    st.stop()

client_args = {"api_key": api_key}
if project_id:
    client_args["project"] = project_id
client = OpenAI(**client_args)

# ===== チャット履歴 =====
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "💬 研修お疲れさまでした！\n"
                "まずは研修ドキュメント（PDF）をアップロードしてください。\n"
                "アップできたら **ok** とだけ送ってください。"
            ),
        }
    ]

# ===== 既存メッセージ表示 =====
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ===== 入力と応答 =====
MODEL = "gpt-4o-mini"

context_snippet = st.session_state.doc_text[:6000] if st.session_state.doc_text else ""
system_prompt = (
    "あなたは『研修レポート作成を支援する専門家』です。"
    "丁寧で論理的に、文脈に沿って分かりやすく説明してください。"
    + (f"\n\n--- 参考ドキュメント抜粋 ---\n{context_snippet}" if context_snippet else "")
)

if prompt := st.chat_input("研修レポートの作成をはじめましょう（ここに話しかけてください）"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ===== 「ok」ハンドリング =====
    normalized = prompt.strip().lower()
    if normalized in {"ok", "ｏｋ", "おk", "了解", "アップした", "upした", "done", "完了"}:
        if st.session_state.doc_text:
            next_msg = (
                "研修を受けてどうでしたか？\n"
                "まずは**感想を気軽に書いてください😉**"
            )
        else:
            next_msg = (
                "まだPDFが読み込まれていないようです。\n"
                "先に研修ドキュメント（PDF）をアップロードしてください。"
            )

        with st.chat_message("assistant"):
            st.markdown(next_msg)
        st.session_state.messages.append({"role": "assistant", "content": next_msg})
        st.stop()

    # ===== 通常の応答 =====
    messages_for_api = [{"role": "system", "content": system_prompt}]
    messages_for_api += st.session_state.messages

    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages_for_api,
        stream=True,
    )

    with st.chat_message("assistant"):
        assistant_text = st.write_stream(stream)

    st.session_state.messages.append({"role": "assistant", "content": assistant_text})
