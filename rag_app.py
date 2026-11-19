import streamlit as st
import requests
import json
import time
import numpy as np
import chromadb
from pypdf import PdfReader

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5-coder:7b"
DB_PATH = "./chroma_db"

st.set_page_config(page_title="Local Semiconductor RAG v3 (ChromaDB)", page_icon="📚", layout="wide")
st.title("📚 보안형 다중 PDF 문서 분석 & 비교 비서 (Local RAG v3)")
st.caption(f"Engine: Ollama ({CHAT_MODEL} + {EMBED_MODEL}) | Persistent ChromaDB & Multi-Doc Comparison")

@st.cache_resource
def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(
        name="semiconductor_docs",
        metadata={"hnsw:space": "cosine"}
    )

collection = get_collection()

def get_indexed_docs():
    data = collection.get(include=["metadatas"])
    if not data["metadatas"]:
        return []
    return sorted(list({m["source"] for m in data["metadatas"]}))

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

# --- 사이드바: 다중 업로드 & DB 관리 ---
with st.sidebar:
    st.header("1. 다중 PDF 업로드 & 영구 저장")
    uploaded_files = st.file_uploader(
        "데이터시트 / 매뉴얼 PDF 선택 (여러 개 가능)",
        type=["pdf"],
        accept_multiple_files=True
    )

    if uploaded_files and st.button("선택한 문서 DB에 영구 저장", type="primary"):
        existing_docs = set(get_indexed_docs())
        for uf in uploaded_files:
            if uf.name in existing_docs:
                st.info(f"'{uf.name}'은(는) 이미 DB에 저장되어 있어 건너뜁니다.")
                continue

            t0 = time.time()
            with st.spinner(f"'{uf.name}' 텍스트 추출 및 GPU 배치 벡터화 중..."):
                chunks = chunk_pdf(uf)
                if not chunks:
                    st.warning(f"'{uf.name}'에서 텍스트를 추출하지 못했습니다.")
                    continue
                texts = [c["text"] for c in chunks]
                vectors = get_embeddings_batch(texts, batch_size=64).tolist()
                ids = [f"{uf.name}_p{c['page']}_c{idx}" for idx, c in enumerate(chunks)]
                metadatas = [{"source": uf.name, "page": c["page"]} for c in chunks]

                for start in range(0, len(ids), 500):
                    collection.add(
                        ids=ids[start:start + 500],
                        documents=texts[start:start + 500],
                        embeddings=vectors[start:start + 500],
                        metadatas=metadatas[start:start + 500]
                    )
            st.success(f"'{uf.name}' 저장 완료! ({len(chunks)}개 문단, {time.time() - t0:.2f}초)")

    st.divider()
    st.header("2. 검색 대상 문서 선택")
    indexed_docs = get_indexed_docs()

    if indexed_docs:
        selected_docs = st.multiselect(
            "질문 및 비교에 사용할 문서를 고르세요",
            options=indexed_docs,
            default=indexed_docs
        )

        with st.expander("🗑️ 저장된 문서 삭제 관리"):
            doc_to_del = st.selectbox("삭제할 문서", indexed_docs)
            if st.button("선택 문서 DB에서 삭제"):
                collection.delete(where={"source": doc_to_del})
                st.success(f"'{doc_to_del}' 삭제 완료!")
                st.rerun()
    else:
        selected_docs = []
        st.caption("아직 DB에 저장된 문서가 없습니다. 위에서 PDF를 추가해 주세요.")

# --- 메인 채팅 화면 ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if query := st.chat_input("저장된 PDF 문서들에 대해 질문하거나 비교해 보세요..."):
    if not selected_docs:
        st.warning("왼쪽 사이드바에서 최소 1개 이상의 문서를 저장 및 선택해 주세요.")
        st.stop()

    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    q_vec = get_embeddings_batch([query])[0].tolist()

    # 단일 문서는 Top-4, 다중 문서 비교 시에는 문서별 Top-2씩 균등 추출
    k_per_doc = 4 if len(selected_docs) == 1 else 2
    retrieved = []

    for doc_name in selected_docs:
        results = collection.query(
            query_embeddings=[q_vec],
            n_results=k_per_doc,
            where={"source": doc_name},
            include=["documents", "metadatas", "distances"]
        )
        if results["documents"] and results["documents"][0]:
            for doc_text, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                retrieved.append({
                    "source": meta["source"],
                    "page": meta["page"],
                    "text": doc_text,
                    "score": 1.0 - float(dist)
                })

    retrieved.sort(key=lambda x: x["score"], reverse=True)

    context_str = "\n\n".join(
        [f"[{r['source']} - Page {r['page']}] {r['text']}" for r in retrieved]
    )
    system_prompt = (
        "당신은 반도체 및 엔지니어링 문서 분석 전문가입니다. "
        "반드시 아래 제공된 [참고 문서]의 내용만을 근거로 한국어로 정확하게 답변하세요. "
        "여러 문서를 비교하는 질문이라면 표(Table)나 항목별로 명확히 대조해서 설명하세요. "
        "문서에 없는 내용은 추측하지 말고 '제공된 문서에서 찾을 수 없습니다'라고 답하세요. "
        "답변할 때는 근거가 된 파일명과 페이지 번호(예: [파일명 - Page 2])를 반드시 명시하세요."
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
                stats_text = f"\n\n---\n`⚡ RTX 5060 추론 성능: {tps:.1f} tok/s ({sec:.2f}초) | 검색 문서: {len(selected_docs)}개`"

        placeholder.markdown(full_reply + stats_text)

        with st.expander("🔍 AI가 참고한 원문 근거 및 유사도 점수 보기"):
            for r in retrieved:
                st.markdown(f"**{r['source']} - Page {r['page']}** (유사도: `{r['score']:.3f}`)")
                st.caption(r["text"])

    st.session_state["messages"].append({"role": "assistant", "content": full_reply + stats_text})