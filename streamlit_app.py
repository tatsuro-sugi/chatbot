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

if st.session_state.doc_text:
    st.success(f"📄 PDFを読み込みました：{st.session_state.doc_pages}ページ")
    with st.expander("🔎 テキストプレビュー（先頭2,000文字）", expanded=False):
        st.text(st.session_state.doc_text[:2000] or "テキストを抽出できませんでした。")
else:
    st.info("PDFをアップロードすると、ここにプレビューが表示されます。")

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
    st.session_state.messages = []

# 既存メッセージ表示
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ===== 入力と応答 =====
MODEL = "gpt-4o-mini"

# PDFテキストをシステムプロンプトに入れる（長過ぎるときは先頭を一部だけ）
context_snippet = st.session_state.doc_text[:6000] if st.session_state.doc_text else ""
system_prompt = (
    "あなたは『研修レポート作成を支援する専門家』です。"
    "丁寧に、具体例を交えながら簡潔に返答してください。"
    + (f"\n\n--- 参考ドキュメント抜粋 ---\n{context_snippet}" if context_snippet else "")
)

if prompt := st.chat_input("研修レポートの作成をはじめましょう（ここに話しかけてください）"):
    # 画面表示
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # モデルに渡すメッセージ（systemを先頭に付加）
    messages_for_api = [{"role": "system", "content": system_prompt}]
    messages_for_api += st.session_state.messages

    # ストリーミング応答
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages_for_api,
        stream=True,
    )

    with st.chat_message("assistant"):
        assistant_text = st.write_stream(stream)

    st.session_state.messages.append({"role": "assistant", "content": assistant_text})
