# CHAMP V3 — Packages & Dependencies

> Every package installed, what it does, and why CHAMP needs it.

---

## Quick Summary

- **188+ Python packages** installed in `champ_v3/venv`
- **2 system dependencies** needed (ffmpeg, libcairo)
- Packages fall into two categories:
  - **Packages** — Python libraries you `pip install` and `import` in code
  - **Dependencies** — System-level tools that packages need to function (not Python)

---

## System Dependencies

These are NOT Python packages. They're system tools that must be installed separately.

| Dependency | Required By | What It Does | Install (Windows) |
|---|---|---|---|
| **ffmpeg** | `pydub`, `moviepy` | Encodes/decodes audio and video files (MP3, WAV, MP4, etc.) | `choco install ffmpeg` or download from ffmpeg.org |
| **libcairo** | `cairosvg` | Renders SVG vector graphics to PNG/PDF | `choco install cairo` or install GTK3 runtime |

---

## Core CHAMP Packages

These are the packages that make CHAMP run. Without these, the system doesn't start.

### Brain (Intelligence Kernel)

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `fastapi` | Python web framework for building APIs | Brain's HTTP server — all endpoints run on this |
| `uvicorn` | ASGI server that runs FastAPI | Actually serves the Brain on port 8100 |
| `pydantic` | Data validation and settings management | Validates every request/response flowing through Brain |
| `pydantic-settings` | Environment variable loading | Loads `.env` config into typed settings |
| `python-dotenv` | Reads `.env` files | Loads API keys and config at startup |
| `httpx` | Async HTTP client | Brain calls LiteLLM and external services |
| `sse-starlette` | Server-Sent Events for FastAPI | Streams chat responses back to clients |
| `starlette` | ASGI framework (FastAPI is built on it) | Middleware, CORS, request handling |

### LiteLLM (Model Router)

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `litellm` | Universal LLM API proxy | Routes requests to Claude, GPT, Gemini through one API |
| `litellm-enterprise` | Enterprise features for LiteLLM | Extended routing and fallback capabilities |
| `litellm-proxy-extras` | Additional proxy functionality | Config loading, model management |
| `openai` | OpenAI Python SDK | OpenAI-compatible API format used by all models |
| `tiktoken` | Token counter for OpenAI models | Counts tokens to stay within model limits |

### Supabase (Memory)

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `supabase` | Supabase Python client | Connects Brain to Supabase for memory storage |
| `postgrest` | PostgREST client for Supabase | Direct database queries (profiles, lessons, sessions) |
| `realtime` | Supabase realtime subscriptions | Live updates from database changes |
| `storage3` | Supabase storage client | File storage capabilities |
| `supabase-auth` | Supabase auth client | Authentication layer |
| `supabase-functions` | Supabase edge functions client | Serverless function calls |

### Voice Agent (LiveKit)

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `livekit` | LiveKit Python SDK | WebRTC connection for real-time voice |
| `livekit-agents` | LiveKit agent framework | Builds the voice agent that listens and responds |
| `livekit-api` | LiveKit server API | Creates rooms, generates tokens, dispatches agents |
| `livekit-plugins-noise-cancellation` | Noise cancellation plugin | Cleans up mic audio before processing |
| `livekit-blingfire` | Text tokenization for LiveKit | Processes text for voice synthesis |
| `sounddevice` | Audio I/O library | Captures microphone input for Ears |
| `soundfile` | Read/write audio files | Audio file format support |

### Ears (Wake Word)

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `openwakeword` | Wake word detection engine | Listens for "Hey Jarvis" on local mic |
| `onnxruntime` | ML inference engine | Runs the wake word model locally |
| `keyboard` | Keyboard event detection | NumLock key as manual wake trigger |

### AI / ML Support

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `numpy` | Numerical computing | Audio frame processing, ML data handling |
| `scipy` | Scientific computing | Signal processing for audio |
| `scikit-learn` | Machine learning toolkit | Classification, clustering for mode detection |
| `huggingface_hub` | Hugging Face model hub | Downloads wake word models |
| `tokenizers` | Fast text tokenization | Tokenizes text for LLM processing |
| `sympy` | Symbolic mathematics | Mathematical computation support |

### LangChain (Orchestration)

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `langchain-classic` | LLM orchestration framework | Chain-of-thought and tool orchestration |
| `langchain-core` | Core LangChain abstractions | Base classes for prompts, outputs, memory |
| `langchain-community` | Community integrations | Third-party tool and model connectors |
| `langchain-text-splitters` | Text chunking utilities | Splits large documents for processing |
| `langsmith` | LangChain observability | Tracing and debugging LLM calls |

### Task Scheduling

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `APScheduler` | Advanced Python scheduler | Self Mode heartbeat (polls every 30 min) |
| `croniter` | Cron expression parser | Scheduling recurring tasks |
| `rq` | Redis Queue for background jobs | Background task processing |
| `redis` | Redis client | Queue backend for async tasks |

### Web & HTTP

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `requests` | HTTP client library | Simple HTTP calls to external services |
| `aiohttp` | Async HTTP client/server | Async web requests in Brain pipeline |
| `websockets` | WebSocket client/server | Real-time communication channels |
| `duckduckgo_search` | DuckDuckGo search API | `search_web` tool for the agent |

### Data & Serialization

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `orjson` | Fast JSON serialization | High-performance JSON parsing in API responses |
| `jsonschema` | JSON schema validation | Validates structured data against schemas |
| `PyYAML` | YAML parser | Reads `litellm_config.yaml` and other configs |
| `strictyaml` | Strict YAML parser | Validated YAML parsing with error reporting |
| `polars` | Fast DataFrame library | High-performance data manipulation |

### Security & Auth

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `PyJWT` | JSON Web Token library | Generates LiveKit room tokens |
| `cryptography` | Cryptographic operations | SSL, token signing, encryption |
| `PyNaCl` | Networking and cryptography | Secure communication |
| `certifi` | SSL certificate bundle | HTTPS verification for API calls |

### Testing

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `pytest` | Python testing framework | Runs all gate tests |
| `pytest-asyncio` | Async test support | Tests async Brain pipeline functions |

### Monitoring & Observability

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `opentelemetry-api` | Distributed tracing API | Traces requests across Brain, LiteLLM, Supabase |
| `opentelemetry-sdk` | Tracing SDK implementation | Collects and exports trace data |
| `opentelemetry-exporter-otlp` | OTLP trace exporter | Sends traces to observability platforms |
| `prometheus_client` | Prometheus metrics | Exposes system metrics for monitoring |
| `rich` | Rich terminal output | Pretty-printed logs and debug output |
| `psutil` | System process utilities | CPU/memory monitoring |

### Cloud Storage

| Package | What It Does | Why CHAMP Needs It |
|---|---|---|
| `boto3` | AWS SDK for Python | S3 storage access if needed |
| `azure-storage-blob` | Azure Blob Storage client | Azure file storage support |
| `azure-identity` | Azure authentication | Azure service authentication |

---

## Data Format Packages (NEW)

These packages enable CHAMP to process any file type. Just installed.

### Documents

| Package | Formats | What It Does | Status |
|---|---|---|---|
| `pymupdf` (fitz) | PDF | Extracts text, images, and tables from PDFs. The fastest Python PDF library | OK |
| `python-docx` | DOCX | Reads and writes Microsoft Word documents. Extracts paragraphs, tables, images | OK |
| `python-pptx` | PPTX | Reads and writes PowerPoint presentations. Extracts slides, text, shapes | OK |
| `striprtf` | RTF | Strips RTF formatting to extract plain text from Rich Text Format files | OK |
| `odfpy` | ODT, ODS, ODP | Reads LibreOffice/OpenOffice documents, spreadsheets, presentations | OK |
| `markdown` | MD | Converts Markdown to HTML. Parses headers, lists, code blocks, links | OK |

### Spreadsheets & Data

| Package | Formats | What It Does | Status |
|---|---|---|---|
| `openpyxl` | XLSX, XLS | Reads and writes Excel spreadsheets. Handles formulas, charts, styles | OK |
| `pyarrow` | Parquet, Arrow | Reads columnar data files. High-performance analytics format | OK |
| `toml` | TOML | Parses TOML config files (like `pyproject.toml`) | OK |
| `csv` (built-in) | CSV, TSV | Reads/writes comma and tab separated data files | Built-in |
| `json` (built-in) | JSON | Parses JSON data and API responses | Built-in |
| `xml` (built-in) | XML | Parses XML documents and data feeds | Built-in |
| `lxml` | XML, HTML | Fast XML/HTML parser with XPath support. More powerful than built-in | OK |

### Images

| Package | Formats | What It Does | Status |
|---|---|---|---|
| `Pillow` | PNG, JPG, GIF, BMP, WEBP, TIFF | Opens, manipulates, and converts image files. Resize, crop, filter | OK |
| `opencv-python` | PNG, JPG, video frames | Computer vision library. Image analysis, frame extraction from video | OK |
| `cairosvg` | SVG | Converts SVG vector graphics to PNG, PDF, or PostScript | NEEDS libcairo |

### Audio

| Package | Formats | What It Does | Status |
|---|---|---|---|
| `pydub` | MP3, WAV, M4A, OGG, FLAC, AAC | Manipulates audio files. Split, merge, convert, extract segments | OK (needs ffmpeg) |
| `openai` (Whisper) | Any audio | Transcribes speech to text using OpenAI's Whisper API | Already installed |

### Video

| Package | Formats | What It Does | Status |
|---|---|---|---|
| `moviepy` | MP4, MOV, WEBM, AVI, MKV | Edits video files. Extract frames, cut clips, get audio track | OK (needs ffmpeg) |
| `opencv-python` | MP4, AVI, frames | Extracts individual frames from video for vision analysis | OK |
| `imageio-ffmpeg` | All video formats | FFmpeg bindings for reading/writing video files | OK |

### Web & Email

| Package | Formats | What It Does | Status |
|---|---|---|---|
| `beautifulsoup4` | HTML | Parses HTML pages. Extracts text, links, tables from web content | OK |
| `extract-msg` | MSG | Reads Microsoft Outlook email files. Extracts sender, subject, body, attachments | OK |
| `email` (built-in) | EML | Parses standard email format files | Built-in |

### Archives

| Package | Formats | What It Does | Status |
|---|---|---|---|
| `rarfile` | RAR | Extracts files from RAR archives | OK |
| `zipfile` (built-in) | ZIP | Creates and extracts ZIP archives | Built-in |
| `tarfile` (built-in) | TAR, GZ, BZ2 | Creates and extracts TAR archives (compressed or not) | Built-in |

---

## Installation Status

### All Packages — Verified

| Package | Status |
|---|---|
| pymupdf | OK |
| python-docx | OK |
| openpyxl | OK |
| python-pptx | OK |
| striprtf | OK |
| odfpy | OK |
| pydub | OK (needs ffmpeg for full functionality) |
| moviepy | OK (needs ffmpeg for full functionality) |
| opencv-python | OK |
| toml | OK |
| pyarrow | OK |
| rarfile | OK |
| extract-msg | OK |
| markdown | OK |
| beautifulsoup4 | OK |
| cairosvg | SKIPPED — needs libcairo (SVG only, low priority) |

### System Dependencies

| Dependency | Status | Install Command |
|---|---|---|
| **ffmpeg** | INSTALLED | `winget install Gyan.FFmpeg` (Admin PowerShell) |
| **libcairo** | SKIPPED | Only needed for SVG rendering — low priority, can revisit later |

### How to Install System Dependencies

```powershell
# Open PowerShell as Administrator (Start menu -> search PowerShell -> right-click -> Run as administrator)
# Do NOT use VS Code terminal — it doesn't have admin privileges

winget install Gyan.FFmpeg

# After install, close and reopen all VS Code terminals to pick up new PATH
```

---

## Formats CHAMP Can Now Process

After all packages are installed and system dependencies are in place:

| Category | Formats | Ready? |
|---|---|---|
| Documents | PDF, DOCX, PPTX, RTF, ODT, ODP, MD, TXT | Yes |
| Spreadsheets | CSV, TSV, XLSX, XLS, ODS, Parquet | Yes |
| Data/Config | JSON, XML, YAML, TOML, SQLite | Yes |
| Images | PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF | Yes |
| SVG | SVG | Skipped (can revisit) |
| Audio | MP3, WAV, M4A, OGG, FLAC, AAC | Yes (ffmpeg installed) |
| Video | MP4, MOV, WEBM, AVI, MKV | Yes (ffmpeg installed) |
| Archives | ZIP, TAR, GZ, BZ2, RAR | Yes |
| Email | EML, MSG | Yes |
| Web | HTML | Yes |
| Code | PY, JS, TS, HTML, CSS, SQL, etc. | Yes (text) |

---

## Package Install Command (For Fresh Setup)

If setting up CHAMP from scratch, run this after creating the venv:

```powershell
# Core CHAMP packages
pip install -r requirements-brain.txt
pip install -r requirements-agent.txt

# Data format packages
pip install pymupdf python-docx openpyxl python-pptx striprtf odfpy cairosvg pydub moviepy opencv-python toml pyarrow rarfile extract-msg markdown beautifulsoup4
```

---

*Documented: March 14, 2026*
*Total packages in venv: 188+*
*Format packages added: 16*
*System dependencies needed: 2 (ffmpeg, libcairo)*
