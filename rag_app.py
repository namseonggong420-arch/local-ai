import streamlit as st
import requests
import json
import time
import numpy as np
from pypdf import PdfReader

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5-coder:7b"

st.set_page_config(page_title="Local Semiconductor RAG (RTX 5060)", page_icon="📄", layout="wide")
st.title("📄 보안형 로컬 PDF 문서 분석 비서 (Local RAG)")
st.caption(f"Engine: Ollama ({CHAT_MODEL} + {EMBED_MODEL}) | Batch Embedding Accelerated")

def get_embeddings_batch(texts, batch_size=64):
    all_vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        res = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": batch}
        )
        res.raise_for_status()
        vecs = np.array(res.json()["embeddings"], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
        all_vecs.append(vecs / norms)
    return np.vstack(all_vecs)

def chunk_pdf(uploaded_file, chunk_size=500, overlap=100):
    reader = PdfReader(uploaded_file)
    chunks = []
    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = " ".join(text.split())
        for start in range(0, len(text), chunk_size - overlap):
            piece = text[start:start + chunk_size]
            if len(piece) > 30:
                chunks.append({"page": page_idx + 1, "text": piece})
    return chunks

with st.sidebar:
    st.header("1. 문서 업로드 (PDF)")
    uploaded_file = st.file_uploader("데이터시트 / 매뉴얼 PDF 선택", type=["pdf"])
    if uploaded_file and st.button("문서 학습(벡터화) 시작", type="primary"):
        t0 = time.time()
        with st.spinner("PDF 텍스트 추출 및 GPU 배치 벡터화 중..."):
            chunks = chunk_pdf(uploaded_file)
            texts = [c["text"] for c in chunks]
            vectors = get_embeddings_batch(texts, batch_size=64)
            st.session_state["chunks"] = chunks
            st.session_state["vectors"] = vectors
            st.session_state["doc_name"] = uploaded_file.name
        elapsed = time.time() - t0
        st.success(f"완료! 총 {len(chunks)}개 문단 색인됨 ({elapsed:.2f}초 소요)")

    if "doc_name" in st.session_state:
        st.info(f"현재 로드된 문서: **{st.session_state['doc_name']}**")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if query := st.chat_input("업로드한 PDF 내용에 대해 질문하세요..."):
    if "vectors" not in st.session_state:
        st.warning("먼저 왼쪽 사이드바에서 PDF 파일을 업로드하고 '문서 학습 시작'을 눌러주세요.")
        st.stop()

    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    q_vec = get_embeddings_batch([query])[0]
    scores = np.dot(st.session_state["vectors"], q_vec)
    top_indices = np.argsort(scores)[::-1][:3]
    retrieved = [(st.session_state["chunks"][i], float(scores[i])) for i in top_indices]

    context_str = "\n\n".join([f"[Page {c['page']}] {c['text']}" for c, _ in retrieved])
    system_prompt = (
        "당신은 반도체 및 엔지니어링 문서 분석 전문가입니다. "
        "반드시 아래 제공된 [참고 문서]의 내용만을 근거로 한국어로 정확하게 답변하세요. "
        "문서에 없는 내용은 추측하지 말고 '제공된 문서에서 찾을 수 없습니다'라고 답하세요. "
        "답변할 때는 근거가 된 페이지 번호(예: [Page 2])를 반드시 명시하세요."
    )
    user_prompt = f"[참고 문서]\n{context_str}\n\n[질문]\n{query}"

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_reply = ""
        stats_text = ""

        res = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": CHAT_MODEL,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            stream=True,
        )

        for line in res.iter_lines():
            if not line:
                continue
            data = json.loads(line.decode("utf-8"))
            if "message" in data and "content" in data["message"]:
                full_reply += data["message"]["content"]
                placeholder.markdown(full_reply + "▌")
            if data.get("done") and data.get("eval_count") and data.get("eval_duration"):
                sec = data["eval_duration"] / 1e9
                tps = data["eval_count"] / sec
                stats_text = f"\n\n---\n`⚡ RTX 5060 추론 성능: {tps:.1f} tok/s ({sec:.2f}초)`"

        placeholder.markdown(full_reply + stats_text)

        with st.expander("🔍 AI가 참고한 원문 근거 및 유사도 점수 보기"):
            for c, score in retrieved:
                st.markdown(f"**Page {c['page']}** (유사도: `{score:.3f}`)")
                st.caption(c["text"])

    st.session_state["messages"].append({"role": "assistant", "content": full_reply + stats_text})