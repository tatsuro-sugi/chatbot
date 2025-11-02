import os
import json
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from src.pdf_utils import read_pdf_text  # PDFテキスト抽出

st.title("💬 Chatbot (OpenAI)")
st.caption("アップロードした研修ドキュメントを元に、AIと対話しながらレポートのドラフトを作成します。")

# ===== セッション初期化 =====
ss = st.session_state
if "doc_text" not in ss: ss.doc_text = ""
if "doc_pages" not in ss: ss.doc_pages = 0
if "questions" not in ss: ss.questions = []       # LLMが作る“問い”
if "q_index" not in ss: ss.q_index = 0           # 次に出す問いのindex
if "doc_title" not in ss: ss.doc_title = "研修レポート"  # ← タイトル保持
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
    # ファイル名→タイトル（拡張子除去）
    try:
        fname = uploaded_pdf.name
        ss.doc_title = os.path.splitext(fname)[0] or ss.doc_title
    except Exception:
        pass
    ss.questions, ss.q_index = [], 0
    st.success(f"📄 PDFを読み込みました：{pages}ページ（タイトル：{ss.doc_title}）")

# ===== 既存チャット表示 =====
for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ===== “ざっくり読んで問いを作る”関数 =====
def make_questions_from_doc(doc_text: str, n: int = 3) -> list[str]:
    snippet = (doc_text or "").strip()
    if len(snippet) > 9000:
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

    qs = []
    for line in text.splitlines():
        line = line.strip(" ・-‐*●\t").strip()
        if not line:
            continue
        for pref in ("Q1", "Q2", "Q3", "Q4", "１", "２", "３"):
            if line.startswith(pref):
                line = line[len(pref):].lstrip(".．:：）) 」　 ")
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

# ===== レポート生成（盛りすぎない＆所定フォーマット） =====
def generate_report_draft() -> str:
    """ユーザー回答とPDF抜粋から、控えめ・事実ベースのレポートを所定フォーマットで作成。"""
    user_answers = "\n".join(m["content"] for m in ss.messages if m["role"] == "user").strip()
    context_snippet = ss.doc_text[:3500].strip() if ss.doc_text else ""
    title = ss.doc_title or "研修レポート"

    system = (
        "あなたは日本語で、簡潔で誇張のない文体の編集者です。"
        "事実に基づき、断定しすぎず、丁寧に書きます。"
    )
    user = f"""
次の情報（PDF抜粋と受講生の回答）だけを根拠に、短い感想文を作ってください。
- 出力フォーマットは厳守：最初の行に【{title}】、空行1つ、次の行から本文のみ。
- 本文は300〜450文字程度。比喩や煽りは使わず、断定しすぎない表現（〜と感じた／〜に気づいた等）を用いる。
- 事実にない内容は書かない。推測・決めつけ・一般化のしすぎを避ける。
- 箇条書きにしない。小見出し（はじめに 等）は付けない。
- 「です・ます」調で統一。末尾に注記や指示文を入れない。

[PDF抜粋]
{context_snippet}

[受講生の回答]
{user_answers}
""".strip()

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,  # 控えめトーン
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    body = resp.choices[0].message.content.strip()

    # すでにタイトル行を含んでいればそのまま、無ければ包む
    first_line = body.splitlines()[0] if body else ""
    if first_line.startswith("【") and "】" in first_line:
        return body
    return f"【{title}】\n\n{body}"

# ===== 入力受付 =====
if prompt := st.chat_input("研修レポートの作成をはじめましょう（ここに話しかけてください）"):
    ss.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    normalized = prompt.strip().lower()

    # 「できた」で即レポート生成 & Copyボタン表示
    if normalized in {"できた", "done", "完了", "完成", "終わった"}:
        if not ss.doc_text and not any(m["role"] == "user" for m in ss.messages):
            msg = "まずはPDFのアップロードと、いくつかの質問への回答をお願いします。"
            with st.chat_message("assistant"): st.markdown(msg)
            ss.messages.append({"role": "assistant", "content": msg})
            st.stop()

        with st.chat_message("assistant"):
            st.markdown("📝 レポートを作成中…")
        draft = generate_report_draft()
        ss.report_draft = draft  # セッション保持

        st.success("✅ レポートドラフトを作成しました！下のテキストをコピーしてお使いください。")
        st.text_area("レポート（コピーして使えます）", draft, height=320, key="draft_textarea_inline")

        # Copy ボタン
        safe = json.dumps(draft)
        components.html(f"""
            <button onclick='navigator.clipboard.writeText({safe}).then(() => {{
                const n = window.parent.document.createElement("div");
                n.textContent = "レポートをコピーしました！";
                n.style.cssText = "position:fixed;right:16px;bottom:16px;background:#4caf50;color:#fff;padding:8px 12px;border-radius:8px;font-size:14px;z-index:9999;";
                window.parent.document.body.appendChild(n);
                setTimeout(()=>n.remove(), 1600);
            }})' style="
                background:#4CAF50;color:#fff;border:none;padding:8px 16px;
                border-radius:6px;cursor:pointer;margin-top:6px;
            ">📋 Copy</button>
        """, height=60)
        st.stop()

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
            done = "ありがとう！予定していた問いは以上です。必要なら「できた」と送るとドラフトを作成します。"
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

# ===== 下部に常時ドラフト表示（Copyボタン版） =====
if "report_draft" in ss:
    st.markdown("---")
    st.subheader("📝 レポートドラフト")
    st.text_area("レポート（コピーして使えます）", ss.report_draft, height=320, key="draft_textarea_panel")

    safe = json.dumps(ss.report_draft)
    components.html(f"""
        <button onclick='navigator.clipboard.writeText({safe}).then(() => {{
            const n = window.parent.document.createElement("div");
            n.textContent = "レポートをコピーしました！";
            n.style.cssText = "position:fixed;right:16px;bottom:16px;background:#4caf50;color:#fff;padding:8px 12px;border-radius:8px;font-size:14px;z-index:9999;";
            window.parent.document.body.appendChild(n);
            setTimeout(()=>n.remove(), 1600);
        }})' style="
            background:#4CAF50;color:#fff;border:none;padding:8px 16px;
            border-radius:6px;cursor:pointer;margin-top:6px;
        ">📋 Copy</button>
    """, height=60)

# ===== レポート生成ボタン（クリック派向け。Copyに統一） =====
if ss.q_index >= len(ss.questions) and ss.questions:
    st.markdown("---")
    st.subheader("📝 レポートドラフトの作成")
    if st.button("レポートを生成する"):
        with st.spinner("レポートを作成中..."):
            draft = generate_report_draft()
            ss.report_draft = draft
            st.success("✅ レポートドラフトを作成しました！")
            st.text_area("レポート（コピーして使えます）", draft, height=300, key="draft_textarea_button")

            safe2 = json.dumps(draft)
            components.html(f"""
                <button onclick='navigator.clipboard.writeText({safe2}).then(() => {{
                    const n = window.parent.document.createElement("div");
                    n.textContent = "レポートをコピーしました！";
                    n.style.cssText = "position:fixed;right:16px;bottom:16px;background:#4caf50;color:#fff;padding:8px 12px;border-radius:8px;font-size:14px;z-index:9999;";
                    window.parent.document.body.appendChild(n);
                    setTimeout(()=>n.remove(), 1600);
                }})' style="
                    background:#4CAF50;color:#fff;border:none;padding:8px 16px;
                    border-radius:6px;cursor:pointer;margin-top:6px;
                ">📋 Copy</button>
            """, height=60)
