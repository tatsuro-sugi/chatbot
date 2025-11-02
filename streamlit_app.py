import os
import streamlit as st
from openai import OpenAI
from src.pdf_utils import read_pdf_text

st.title("💬 Chatbot (OpenAI)")
st.caption("UI入力が空なら Secrets / 環境変数の順でAPIキーを使用します。")


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

# --- キー取得：UI > Secrets > 環境変数 ---
ui_key = st.text_input("OpenAI API Key (空ならSecretsを使う)", type="password")
api_key = (ui_key or st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
project_id = (st.secrets.get("OPENAI_PROJECT_ID") or os.getenv("OPENAI_PROJECT_ID") or "").strip()

src = "UI" if ui_key else ("Secrets" if "OPENAI_API_KEY" in st.secrets else "Env/未設定")
st.write(f"🔑 Using key from **{src}**: `{(api_key[:6] + '…') if api_key else '(none)'}`")
if api_key.startswith("sk-proj-") and not project_id:
    st.warning("このキーはプロジェクト制限付きです。Secrets に OPENAI_PROJECT_ID を設定してください。")

if not api_key:
    st.error("OpenAIのAPIキーが見つかりません。入力欄 or Settings→Secrets に設定してください。")
    st.stop()

# --- OpenAIクライアント初期化 ---
client_args = {"api_key": api_key}
if project_id:
    client_args["project"] = project_id
client = OpenAI(**client_args)

# --- 認証チェック（軽い呼び出し） ---
try:
    client.models.list()
    st.success("✅ OpenAI Auth OK")
except Exception as e:
    st.error("❌ 認証に失敗しました。APIキーまたはProject IDを確認してください。")
    st.exception(e)
    st.stop()

# --- チャット履歴の初期化 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# 既存メッセージ表示
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- 入力と応答 ---
MODEL = "gpt-4o-mini"  # 速くて安価。重めなら "gpt-4.1" 等に変更

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ストリーミング応答
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
        stream=True,
    )

    with st.chat_message("assistant"):
        assistant_text = st.write_stream(stream)

    st.session_state.messages.append({"role": "assistant", "content": assistant_text})
