import os
import streamlit as st
from openai import OpenAI

st.title("💬 Chatbot (debug)")
st.caption("UI入力が空なら Secrets を使用します。")

# === キー取得：UIが空ならSecrets、その次に環境変数 ===
ui_key = st.text_input("OpenAI API Key (空ならSecretsを使う)", type="password")
key = (ui_key or st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()

# どこから拾ったかを表示（安全のため先頭6文字だけ）
source = "UI" if ui_key else ("Secrets" if "OPENAI_API_KEY" in st.secrets else "Env/未設定")
shown = (key[:6] + "…") if key else "(none)"
st.write(f"🔎 Using key from **{source}**: `{shown}`")

if not key:
    st.error("APIキーが見つかりません。UIに入れるか、Settings→Secrets に `OPENAI_API_KEY` を保存してください。")
    st.stop()

# 必要なら project を指定（プロジェクト制限付き環境なら有効化）
PROJECT_ID = st.secrets.get("OPENAI_PROJECT_ID", "")  # 使う場合は Secrets に入れる
client = OpenAI(api_key=key, **({"project": PROJECT_ID} if PROJECT_ID else {}))

# --- まず認証だけテスト（ここで落ちるならキー問題が確定） ---
try:
    _ = client.models.list()  # 軽いAPIで認証確認
    st.success("✅ Auth OK")
except Exception as e:
    st.error("❌ 認証に失敗しました。下のエラーをログでも確認してください（Manage app → Logs）。")
    st.exception(e)
    st.stop()

# ===== ここからチャット本体 =====
if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    def stream_gen():
        stream = client.chat.completions.create(
            model="gpt-4o-mini",               # 現行モデル
            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
            stream=True,
        )
        for ev in stream:
            delta = getattr(ev.choices[0].delta, "content", None)
            if delta: yield delta

    with st.chat_message("assistant"):
        out = st.write_stream(stream_gen())
    st.session_state.messages.append({"role": "assistant", "content": out})
