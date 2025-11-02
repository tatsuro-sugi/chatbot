import os
import re
import streamlit as st
from openai import OpenAI
from src.pdf_utils import read_pdf_text, extract_questions

st.title("💬 Chatbot (OpenAI)")
st.caption("アップロードした研修ドキュメントを元に、AIと対話しながらレポートのドラフトを作成します。")

# ===== PDFアップロード =====
uploaded_pdf = st.file_uploader("研修ドキュメント（PDF）をアップロード", type=["pdf"])

# セッション初期化
ss = st.session_state
if "doc_text" not in ss: ss.doc_text = ""
if "doc_pages" not in ss: ss.doc_pages = 0
if "questions" not in ss: ss.questions = []       # 抽出した“問い”の配列
if "q_index" not in ss: ss.q_index = 0           # 次に投げる問いのインデックス
if "messages" not in ss:
    ss.messages = [{
        "role": "assistant",
        "content": (
            "💬 研修お疲れさまでした！\n"
            "まずは研修ドキュメント（PDF）をアップロードしてください。\n"
            "アップできたら **ok** とだけ送ってください。"
        ),
    }]

# PDF読み込み
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.read()
    text, pages = read_pdf_text(pdf_bytes)
    ss.doc_text, ss.doc_pages = text, pages
    ss.questions = extract_questions(text, max_q=10)  # ← ここで問いを抽出
    ss.q_index = 0
    st.success(f"📄 PDFを読み込みました：{pages}ページ")
else:
    st.info("PDFをアップロードすると内容を解析できます。")

# ===== APIキー（Secrets / 環境変数から自動取得）=====
api_key    = (st.secrets.get("OPENAI_API_KEY")    or os.getenv("OPENAI_API_KEY")    or "").strip()
project_id = (st.secrets.get("OPENAI_PROJECT_ID") or os.getenv("OPENAI_PROJECT_ID") or "").strip()
if not api_key:
    st.error("OpenAIのAPIキーが設定されていません。Secretsに OPENAI_API_KEY を追加してください。")
    st.stop()

client_args = {"api_key": api_key}
if project_id: client_args["project"] = project_id
client = OpenAI(**client_args)

# 既存チャット表示
for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

MODEL = "gpt-4o-mini"

# システムプロンプト（PDFの要点を渡したい場合）
context_snippet = ss.doc_text[:6000] if ss.doc_text else ""
system_prompt = (
    "あなたは『研修レポート作成を支援する専門家』です。"
    "丁寧で論理的に、文脈に沿って分かりやすく説明してください。"
    + (f"\n\n--- 参考ドキュメント抜粋 ---\n{context_snippet}" if context_snippet else "")
)

# ===== ここが 1) の置き換え：自然な会話形式で1問ずつ出す =====
def ask_next_question() -> bool:
    """抽出済みの問いを1つだけ自然文で投げる。投げたら True、もう無ければ False。"""
    if ss.q_index < len(ss.questions):
        q = ss.questions[ss.q_index].strip()
        ss.q_index += 1

        with st.chat_message("assistant"):
            # 最初の1問目だけ、導入のひと言を添える
            if ss.q_index == 1:
                st.markdown("じゃあ今回の研修を振り返っていきましょう！")
            st.markdown(q)  # 見出しや番号は付けず、質問文そのまま

        # ログにも保存（1問目は導入文を含めて保存）
        ss.messages.append({
            "role": "assistant",
            "content": ("じゃあ今回の研修を振り返っていきましょう！\n" + q) if ss.q_index == 1 else q
        })
        return True
    return False

# ===== 入力受付 =====
if prompt := st.chat_input("研修レポートの作成をはじめましょう（ここに話しかけてください）"):
    ss.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    normalized = prompt.strip().lower()

    # 1) 最初の合図「ok」で、抽出済みの“問い”を投げ始める
    if normalized in {"ok", "ｏｋ", "おk", "了解", "upした", "アップした", "done", "完了"}:
        if not ss.doc_text:
            msg = "まだPDFが読み込まれていないようです。先に研修ドキュメント（PDF）をアップしてください。"
            with st.chat_message("assistant"): st.markdown(msg)
            ss.messages.append({"role": "assistant", "content": msg})
        else:
            # 問いが見つかったら順番に出す。無ければ感想を促す
            if ss.questions:
                ask_next_question()
            else:
                msg = "資料内で“Q”が見つかりませんでした。まずは研修の感想から教えてください。"
                with st.chat_message("assistant"): st.markdown(msg)
                ss.messages.append({"role": "assistant", "content": msg})
        st.stop()

    # 2) Qモード中：ユーザーの回答を受けたら“次の問い”を1つだけ投げる
    if ss.q_index > 0 and ss.q_index <= len(ss.questions):
        if ask_next_question():
            st.stop()
        else:
            done_msg = "ありがとう！予定していた問いは以上です。続けて深掘りしてもいいですし、ここまでの内容でレポート案を作ることもできます。"
            with st.chat_message("assistant"): st.markdown(done_msg)
            ss.messages.append({"role": "assistant", "content": done_msg})
            # 以降は通常の生成にフォールバック

    # 3) 通常の応答（モデル呼び出し）
    messages_for_api = [{"role": "system", "content": system_prompt}] + ss.messages
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages_for_api,
        stream=True,
    )
    with st.chat_message("assistant"):
        assistant_text = st.write_stream(stream)
    ss.messages.append({"role": "assistant", "content": assistant_text})

def _clean_question(q: str) -> str:
    # 例: "Q1. あな", "Q２：〇〇", "Q 3) ..." → "あな" / "〇〇" に
    return re.sub(r'^\s*[QＱ]\s*[\d０-９]*\s*[:：\.\)）\-–]*\s*', '', q.strip(), flags=re.IGNORECASE)

def ask_next_question() -> bool:
    if ss.q_index < len(ss.questions):
        raw_q = ss.questions[ss.q_index].strip()
        q = _clean_question(raw_q)          # ← ここで番号などを除去
        ss.q_index += 1

        with st.chat_message("assistant"):
            if ss.q_index == 1:
                st.markdown("じゃあ今回の研修を振り返っていきましょう！")
            st.markdown(q)                  # 番号なしで自然文だけを表示

        ss.messages.append({
            "role": "assistant",
            "content": ("じゃあ今回の研修を振り返っていきましょう！\n" + q) if ss.q_index == 1 else q
        })
        return True
    return False
