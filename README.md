




<img width="613" height="982" alt="image" src="https://github.com/user-attachments/assets/d30c9981-87a8-4f66-a606-11fc12433f7c" />
# ⚡ Local AI Chat Web UI (RTX 5060)

외부 클라우드 API 없이 로컬 환경(`Ollama`)에서 직접 구동되는 보안형 AI 채팅 웹 인터페이스입니다.

## 🖥️ 하드웨어 및 개발 환경
- **GPU:** NVIDIA GeForce RTX 5060 (8GB VRAM)
- **CPU / RAM:** Intel Core Ultra 5 225F / 16GB DDR5
- **OS / Runtime:** Windows 11 WSL2 (Ubuntu 24.04), Ollama (`qwen2.5-coder:7b`)
- **Tech Stack:** HTML5, CSS3, Vanilla JavaScript (Fetch Stream API)

## ✨ 주요 구현 기능
1. **완전 오프라인 로컬 통신:** `localhost:11434` REST API를 통해 데이터 외부 유출 없이 추론 수행
2. **실시간 스트리밍 출력:** `ReadableStream` 및 `TextDecoder`를 활용해 토큰 생성 즉시 화면에 렌더링
3. **하드웨어 추론 성능 측정기:** Ollama 응답 메타데이터(`eval_count`, `eval_duration`)를 파싱하여 초당 토큰 생성 속도(`tok/s`) 실시간 표시
4. **역할(System Prompt) 전환 & 코드 보안 처리:** 모드별 프롬프트 스위칭 및 HTML 이스케이프(`escapeHtml`) 적용

## 🔧 트러블슈팅 기록
- **브라우저 CORS 차단 문제 해결:** 로컬 HTML 파일에서 Ollama 서버 접근 시 발생하는 CORS 정책 차단을 `OLLAMA_ORIGINS=*` 환경 변수 설정으로 해결

---

# 📄 Phase 2: 보안형 로컬 PDF 문서 분석 비서 (Local RAG)

사내 데이터시트 및 공정 매뉴얼의 외부 유출을 원천 차단하기 위해, 로컬 환경에서 PDF 문서를 벡터화하고 출처(페이지 번호) 기반으로 답변하는 RAG 시스템입니다.

## ✨ 주요 구현 및 성능 최적화
1. **Batch Embedding 병렬화 (`/api/embed`):** 기존 1:1 순차 요청 방식의 HTTP 병목을 개선하여 64개 문단 단위 배치 처리 적용 (대용량 데이터시트 색인 시간 대폭 단축)
2. **코사인 유사도 기반 정밀 검색:** `nomic-embed-text` 임베딩 벡터와 NumPy 행렬 내적(`np.dot`)을 활용해 Top-3 핵심 문단 실시간 추출
3. **할루시네이션 억제 및 근거 검증 UI:** 제공된 문서 내 근거로만 답변하도록 프롬프트를 제어하고, 답변 하단에 인용 페이지 및 원문 유사도 점수(`Expander`) 제공

---

# 📚 Phase 3: ChromaDB 영구 저장 및 다중 PDF 비교 시스템 (Local RAG v3)

매 실행 시 문서를 재학습해야 하는 메모리 휘발성 한계를 극복하고, 여러 개의 반도체 데이터시트(예: STM32 vs ESP32)를 동시에 대조·비교할 수 있도록 고도화한 버전입니다.

## ✨ 주요 고도화 내역
1. **영구 벡터 DB 구축 (`ChromaDB PersistentClient`):** 임베딩 벡터를 로컬 디스크(`./chroma_db`)에 영구 저장하여 재실행 시 재학습 비용 제거 및 문서별 삭제·관리 UI 구현
2. **문서별 균형 검색 (Balanced Multi-Doc Retrieval):** 다중 문서 비교 시 특정 문서로 검색 결과가 쏠리는 현상을 방지하기 위해 선택된 문서마다 Top-K 청크를 균등 추출 후 통합 정렬
3. **비교 분석 프롬프트 및 출처 고도화:** 파일명과 페이지 번호(`[파일명 - Page N]`)를 함께 명시하고, 다중 스펙 대조 시 표(Table) 형식으로 요약 출력
