import os
import streamlit as st
from openai import OpenAI

st.title("💬 Chatbot")
st.write(
    "This is a simple chatbot that uses OpenAI models. "
    "Enter your OpenAI API key below or store it in Secrets."
)

# 1) UI入力 > 2) Secrets > 3) 環境変数 の優先順でキー取得
ui_key = st.text_input("OpenAI API Key", type="password")
api_key = (ui_key or st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()

if not api_key:
    st.info("Please add your OpenAI API key to continue (input box or Settings→Secrets).", icon="🗝️")
    st.stop()

# OpenAIクライアントに明示的に渡す（ここが重要）
client = OpenAI(api_key=api_key)

# セッション状態
if "messages" not in st.session_state:
    st.session_state.messages = []

# 既存メッセージ表示
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# 入力
if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ※ 旧 gpt-3.5-turbo は終了。現行の軽量モデルを使用
    def stream_gen():
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
            stream=True,
        )
        for ev in stream:
            delta = getattr(ev.choices[0].delta, "content", None)
            if delta:
                yield delta

    with st.chat_message("assistant"):
        assistant_text = st.write_stream(stream_gen())

    st.session_state.messages.append({"role": "assistant", "content": assistant_text})
