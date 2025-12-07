# Jeonbuk-AI

전북특별자치도청 캡스톤 프로젝트로 개발된 AI 협업 플랫폼입니다.

## 프로젝트 개요

Jeonbuk-AI는 Open WebUI를 기반으로 전북특별자치도청의 업무 환경에 최적화된 AI 통합 플랫폼입니다. 다양한 LLM 모델과의 통합, RAG(Retrieval Augmented Generation) 기능, 한국어 특화 문서 처리, 그리고 실시간 회의록 작성 기능을 제공합니다.

## 주요 기능

### 1. 멀티 LLM 지원
- Ollama 기반 로컬 LLM 실행
- OpenAI, Anthropic, Google Gemini 등 외부 API 통합
- 다중 모델 동시 대화 지원
- 커스텀 모델 빌더

### 2. 문서 처리 및 RAG
- 다양한 문서 형식 지원 (PDF, DOCX, PPTX, HWP 등)
- 한글(HWP) 파일 처리 지원
- 9개 벡터 데이터베이스 지원 (ChromaDB, PGVector, Qdrant, Milvus 등)
- 문서 업로드 후 자동 임베딩 및 검색
- 15개 이상의 웹 검색 엔진 통합

### 3. 한국어 특화 기능
- 실시간 음성 녹음 및 회의록 작성
- 한글(HWP) 문서 처리
- RapidOCR 기반 한국어 문서 인식
- Faster Whisper 기반 음성-텍스트 변환 (STT)
- 다중 TTS 엔진 지원 (Azure, ElevenLabs, OpenAI)

### 4. 협업 기능
- 채널 기반 팀 협업
- 실시간 음성/영상 통화
- WebSocket 기반 실시간 메시징
- 문서 공유 및 공동 작업

### 5. 관리자 기능
- 사용자 및 그룹 관리
- 역할 기반 접근 제어 (RBAC)
- 모델 및 도구 관리
- 사용량 모니터링
- SCIM 2.0 기반 자동 프로비저닝

### 6. 이미지 생성 및 처리
- DALL-E, Gemini, ComfyUI 통합
- 이미지 생성 및 편집
- OCR을 통한 이미지 텍스트 추출

## 기술 스택

### 백엔드
- **언어**: Python 3.11+
- **프레임워크**: FastAPI 0.118.0
- **데이터베이스**: PostgreSQL (SQLAlchemy 2.0.38)
- **인증**: PyJWT, Authlib, Argon2
- **WebSocket**: python-socketio 5.15.0
- **스케줄링**: APScheduler 3.10.4

### AI/ML
- **LLM 통합**: OpenAI, Anthropic, Google GenAI, Ollama
- **임베딩**: sentence-transformers 5.1.2, transformers 4.57.3
- **음성 처리**: faster-whisper 1.1.1 (STT), pydub 0.25.1
- **RAG**: langchain 0.3.27, chromadb 1.1.0
- **문서 처리**: pypdf, docx2txt, python-pptx, unstructured
- **한글 지원**: python-hwplib (커스텀)
- **OCR**: rapidocr-onnxruntime

### 프론트엔드
- **프레임워크**: SvelteKit 2.5.27, Svelte 5.0.0
- **스타일링**: Tailwind CSS 4.0.0
- **에디터**: Tiptap 3.0.7, CodeMirror 6
- **차트**: Chart.js 4.4.5, Vega-Lite 6.4.1
- **다국어**: i18next 23.10.0
- **실시간 통신**: Socket.io-client 4.2.0

### 인프라
- **컨테이너**: Docker, Docker Compose
- **웹 서버**: Nginx 1.27-alpine
- **배포**: Kubernetes (Helm, Kustomize)
- **데이터베이스**: PostgreSQL (외부 서버)

## 설치 및 실행

### 사전 요구사항
- Docker 및 Docker Compose
- Node.js 18.13 이상
- Python 3.11 이상 (로컬 개발 시)

### Docker Compose를 이용한 설치

1. 저장소 클론
```bash
git clone https://github.com/mindungil/Jeonbuk-AI.git
cd Jeonbuk-AI
```

2. 환경 변수 설정
```bash
# .env 파일 생성 및 편집
cat > .env << EOF
DATABASE_URL=postgresql://admin:password@host.docker.internal:5432/customui
CORS_ALLOW_ORIGIN=https://ai.jb.go.kr;http://ai.jb.go.kr
EOF
```

3. Docker Compose 실행
```bash
docker-compose up -d
```

4. 서비스 접속
- HTTP: http://localhost:80
- HTTPS: https://localhost:443

### GPU 지원 (CUDA)

GPU를 사용하려면 다음과 같이 실행합니다:

```bash
# Nvidia Container Toolkit 설치 필요
docker-compose -f docker-compose.gpu.yaml up -d
```

### 로컬 개발 환경

#### 백엔드 실행
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn open_webui.main:app --reload
```

#### 프론트엔드 실행
```bash
npm install
npm run dev
```

## 프로젝트 구조

```
Jeonbuk-AI/
├── backend/                    # Python 백엔드
│   ├── open_webui/            # 메인 애플리케이션
│   │   ├── routers/           # API 엔드포인트 (25개)
│   │   ├── models/            # 데이터베이스 모델
│   │   ├── retrieval/         # RAG 기능
│   │   ├── utils/             # 유틸리티
│   │   └── socket/            # WebSocket 통신
│   ├── python-hwplib/         # HWP 파일 처리 라이브러리
│   └── requirements.txt       # Python 의존성
│
├── src/                        # SvelteKit 프론트엔드
│   ├── lib/
│   │   ├── apis/              # API 클라이언트
│   │   ├── components/        # Svelte 컴포넌트
│   │   └── i18n/              # 다국어 지원
│   └── routes/                # SvelteKit 라우트
│
├── nginx/                      # Nginx 설정
│   ├── nginx.conf             # 메인 설정
│   ├── conf.d/                # 사이트 설정
│   └── ssl/                   # SSL 인증서
│
├── kubernetes/                 # Kubernetes 배포
│   ├── helm/                  # Helm 차트
│   └── manifest/              # Kubernetes 매니페스트
│
├── docker-compose.yaml         # Docker Compose 설정
├── Dockerfile                  # Docker 이미지 빌드
├── package.json               # Node.js 의존성
└── README.md                  # 프로젝트 문서
```

## API 엔드포인트

주요 API 엔드포인트:

- `/api/v1/auths/*` - 인증 및 권한 관리
- `/api/v1/chats/*` - 채팅 기능
- `/api/v1/files/*` - 파일 업로드/관리
- `/api/v1/knowledge/*` - 지식 베이스
- `/api/v1/models/*` - 모델 관리
- `/api/v1/audio/*` - 음성 생성/인식
- `/api/v1/retrieval/*` - RAG 검색
- `/api/v1/channels/*` - 채널 관리
- `/ollama/*` - Ollama 프록시
- `/openai/*` - OpenAI 호환 API

## 데이터베이스

### 지원 데이터베이스
- PostgreSQL (권장)
- SQLite (개발용)
- MongoDB

### 벡터 데이터베이스
- ChromaDB (기본)
- PGVector
- Qdrant
- Milvus
- Elasticsearch
- OpenSearch
- Pinecone
- S3Vector
- Oracle 23ai

## 환경 변수

주요 환경 변수:

```bash
# 데이터베이스
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# CORS 설정
CORS_ALLOW_ORIGIN=https://ai.jb.go.kr;http://ai.jb.go.kr

# OpenAI API
OPENAI_API_KEY=sk-...
OPENAI_API_BASE_URL=https://api.openai.com/v1

# Ollama
OLLAMA_BASE_URL=http://ollama:11434

# 음성 처리
WHISPER_MODEL=base
RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# 웹 서버
FORWARDED_ALLOW_IPS=*
```

## 배포

### Docker를 이용한 프로덕션 배포

```bash
# 이미지 빌드
docker build -t jeonbuk-ai:latest .

# 컨테이너 실행
docker run -d \
  -p 80:80 \
  -p 443:443 \
  -e DATABASE_URL=postgresql://... \
  -v open-webui:/app/backend/data \
  --name jeonbuk-ai \
  --restart unless-stopped \
  jeonbuk-ai:latest
```

### Kubernetes 배포

```bash
# Helm을 이용한 배포
cd kubernetes/helm
helm install jeonbuk-ai . -f values.yaml

# 또는 매니페스트 직접 적용
kubectl apply -f kubernetes/manifest/
```

## 커스터마이징

### 브랜딩 변경
- 애플리케이션 이름: 환경 변수 `APP_NAME` 설정
- 로고 및 파비콘: `src/lib/assets/` 디렉토리에서 변경
- 색상 테마: `tailwind.config.js`에서 수정

### 기능 추가
1. 백엔드 라우터: `backend/open_webui/routers/`에 새 파일 추가
2. 프론트엔드 컴포넌트: `src/lib/components/`에 추가
3. API 클라이언트: `src/lib/apis/`에 추가

## 라이선스

이 프로젝트는 Open WebUI를 기반으로 하며, 다음 라이선스를 따릅니다:
- 현재 코드베이스: Open WebUI License
- 이전 기여 코드: 각각의 원본 라이선스

자세한 내용은 [LICENSE](./LICENSE) 및 [LICENSE_HISTORY](./LICENSE_HISTORY) 파일을 참조하세요.

## 기여

### 기반 프로젝트
- Open WebUI: https://github.com/open-webui/open-webui
- 원본 라이선스: Open WebUI License

### 주요 변경사항
- 한국어 특화 기능 추가 (HWP 지원, STT/TTS)
- 실시간 회의록 작성 기능
- 전북특별자치도청 업무 환경 맞춤 설정
- PostgreSQL 기반 외부 데이터베이스 연동
- SSL/Nginx 프록시 설정

## 문제 해결

### 일반적인 문제

**데이터베이스 연결 실패**
```bash
# 연결 문자열 확인
echo $DATABASE_URL

# 데이터베이스 접근 가능 여부 확인
psql $DATABASE_URL
```

**Ollama 연결 실패**
- `OLLAMA_BASE_URL` 환경 변수 확인
- Ollama 서비스 실행 상태 확인
- 네트워크 접근성 확인

**CORS 오류**
- `CORS_ALLOW_ORIGIN` 환경 변수에 도메인 추가
- 프로토콜(http/https) 정확히 지정

자세한 문제 해결은 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)를 참조하세요.

## 지원

프로젝트 관련 문의사항은 이슈를 등록해주세요.

## 개발팀

전북특별자치도청 캡스톤 프로젝트 개발팀

### 연락처
- 길민준: rlfalswns12@gmail.com

## 감사의 글

이 프로젝트는 Open WebUI 커뮤니티의 훌륭한 작업을 기반으로 개발되었습니다. Open WebUI 팀과 기여자들에게 감사드립니다.
