import os
import streamlit as st
import anthropic

st.title("💬 Claude Chatbot (Anthropic)")
st.caption("UI入力が空なら Secrets / 環境変数の順でAPIキーを使用します。")

# キー取得：UI > Secrets > 環境変数
ui_key = st.text_input("Anthropic API Key (空ならSecretsを使う)", type="password")
api_key = (ui_key or st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()

src = "UI" if ui_key else ("Secrets" if "ANTHROPIC_API_KEY" in st.secrets else "Env/未設定")
st.write(f"🔑 Using key from **{src}**: `{(api_key[:6] + '…') if api_key else '(none)'}`")

if not api_key:
    st.error("AnthropicのAPIキーが見つかりません。入力欄 or Settings→Secrets に `ANTHROPIC_API_KEY` を設定してください。")
    st.stop()

client = anthropic.Anthropic(api_key=api_key)

# 認証チェック（軽いリクエスト）
try:
    # Claudeはモデル一覧APIがないため、最小呼び出しで検証
    client.messages.create(
        model="claude-3-haiku-20240307",  # ごく短いダミー
        max_tokens=1,
        messages=[{"role": "user", "content": "ping"}],
    )
    st.success("✅ Anthropic Auth OK")
except Exception as e:
    st.error("❌ Anthropic 認証に失敗。キーを確認してください。")
    st.exception(e)
    st.stop()

# チャット状態
if "messages" not in st.session_state:
    st.session_state.messages = []

# 既存表示
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# 入力
if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 推奨モデル：高速なら Haiku、精度なら Sonnet
    MODEL = "claude-3-5-sonnet-latest"  # 迷ったらこれ
    # MODEL = "claude-3-haiku-20240307" # 速さ優先

    # ストリーミングで出力
    def stream_claude():
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
        ) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
        # write_streamの戻り値として全文が欲しいので返す
        return final.content[0].text if final and final.content else ""

    with st.chat_message("assistant"):
        assistant_text = st.write_stream(stream_claude())

    st.session_state.messages.append({"role": "assistant", "content": assistant_text})
