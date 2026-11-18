



<img width="613" height="982" alt="스크린샷 2026-11-18 161704" src="https://github.com/user-attachments/assets/14a73884-b9b8-49ff-9dd3-1f6d57133f16" />
<img width="613" height="982" alt="image" src="https://github.com/user-attachments/assets/7003c7b2-4698-4151-b125-d28097f84ba3" />
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
