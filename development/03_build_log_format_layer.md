# CHAMP V3 — Build Log: Format Processing Layer

> Tracks the process, errors, and lessons from adding data format support.

---

## Date: March 14, 2026

### Goal
Enable CHAMP to process any data format — documents, images, audio, video, archives, email, code.

---

## Step 1: Identify the Gap

After all gate tests passed (29/29), we audited what formats CHAMP could process.

**What worked:** Text, voice (real-time), URLs, screenshots, web forms, code execution, file creation
**What was missing:** PDF, CSV, XLSX, DOCX, PPTX, images (analysis), audio files, video files, archives, email

### Key Finding
The Brain's pipeline schema already supports multimodal messages (images in the request),
but `brain/pipeline.py` lines 245-251 **silently drops non-text content**:

```python
if isinstance(msg.content, list):
    text_parts = [part.get("text", "") for part in msg.content
                  if isinstance(part, dict) and part.get("type") == "text"]
```

Image data in requests is ignored. Gemini Flash (vision model) is configured but never receives images.

---

## Step 2: Install Format Packages

### First Attempt — FAILED
Ran pip install from a previous session but packages didn't persist.
Verification showed 0/16 packages actually importable.

**Lesson:** Always verify installs with an import check, not just pip output.

### Second Attempt — SUCCESS
```powershell
pip install pymupdf python-docx openpyxl python-pptx striprtf odfpy cairosvg pydub moviepy opencv-python toml pyarrow rarfile extract-msg markdown beautifulsoup4
```

### Verification Results
| Package | Status |
|---|---|
| pymupdf | OK |
| python-docx | OK |
| openpyxl | OK |
| python-pptx | OK |
| striprtf | OK |
| odfpy | OK |
| pydub | OK (warning: needs ffmpeg) |
| moviepy | OK (needs ffmpeg) |
| opencv-python | OK |
| toml | OK |
| pyarrow | OK |
| rarfile | OK |
| extract-msg | OK |
| markdown | OK |
| beautifulsoup4 | OK |
| cairosvg | FAILED — needs system lib `libcairo` |

---

## Step 3: Install System Dependencies

### ffmpeg

**Attempt 1 — Chocolatey via VS Code terminal:** FAILED
- Error: `&&` doesn't work in PowerShell
- Lesson: PowerShell uses `;` or run lines separately

**Attempt 2 — Chocolatey in VS Code terminal:** FAILED
- Error: `npm.ps1 cannot be loaded because running scripts is disabled`
- Fix: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

**Attempt 3 — Chocolatey install in VS Code terminal:** FAILED
- Error: "Installation of Chocolatey to default folder requires Administrative permissions"
- Lesson: Chocolatey install MUST use Admin PowerShell, not VS Code

**Attempt 4 — Chocolatey install in Admin PowerShell:** PARTIAL
- Chocolatey was already partially installed from a previous attempt
- But `choco` command still not found — PATH not set

**Attempt 5 — Full path to choco:** FAILED
- `C:\ProgramData\chocolatey\bin\choco` doesn't exist
- Chocolatey installation was corrupted/incomplete

**Attempt 6 — winget (built into Windows 11):** SUCCESS
```powershell
winget install Gyan.FFmpeg
```
- Installed ffmpeg 8.0.1
- Commands added: ffmpeg, ffplay, ffprobe
- Lesson: Use `winget` on Windows 11 instead of Chocolatey — no extra setup needed

### libcairo (for SVG)

**Attempt 1 — winget:** FAILED
- `winget install GnuWin32.Cairo` — "No package found matching input criteria"
- Decision: Skip for now. SVG is low priority. Can revisit later.
- CHAMP can still read SVG as text (it's XML). Missing only SVG-to-image rendering.

---

## Step 4: Restart Terminals

After installing ffmpeg, all VS Code terminals need to be killed and reopened
so they pick up the new PATH environment variable.

---

## Current Status

### Packages: 15/16 installed and verified
### System Dependencies: 1/2 installed (ffmpeg yes, libcairo skipped)

### Formats Ready
| Category | Formats | Status |
|---|---|---|
| Documents | PDF, DOCX, PPTX, RTF, ODT, MD, TXT | Ready |
| Spreadsheets | CSV, TSV, XLSX, XLS, ODS, Parquet | Ready |
| Data/Config | JSON, XML, YAML, TOML, SQLite | Ready |
| Images | PNG, JPG, GIF, BMP, WEBP, TIFF | Ready |
| Audio | MP3, WAV, M4A, OGG, FLAC, AAC | Ready |
| Video | MP4, MOV, WEBM, AVI, MKV | Ready |
| Archives | ZIP, TAR, GZ, BZ2, RAR | Ready |
| Email | EML, MSG | Ready |
| Web | HTML | Ready |
| Code | PY, JS, TS, CSS, SQL, etc. | Ready |
| SVG | SVG | Skipped (needs libcairo) |

### What's Still Needed (Build Phase)
1. ~~**File processor module**~~ — DONE: `brain/file_processor.py`
2. ~~**Upload endpoint**~~ — DONE: `POST /v1/upload` + `GET /v1/files/{file_id}`
3. ~~**Pipeline fix**~~ — DONE: Images route to Gemini Flash automatically
4. **Frontend upload UI** — drag-and-drop or file picker on dashboard (not built yet)

---

## Step 5: Build the Format Processing Layer — COMPLETED

### What Was Built

#### 1. `brain/file_processor.py` (New File)
Universal file processor. Takes any file, detects type, extracts content.

- **detect_handler()** — Maps filename/MIME to handler (30+ format types)
- **process_file()** — Routes to the right extractor, returns FileProcessResult
- **FileProcessResult** — Structured output with text, metadata, image_b64, mime_type

Handlers built for every format:
| Handler | Formats | Package Used |
|---|---|---|
| `_process_pdf` | PDF | pymupdf (fitz) |
| `_process_docx` | DOCX | python-docx |
| `_process_pptx` | PPTX | python-pptx |
| `_process_rtf` | RTF | striprtf |
| `_process_odt` | ODT, ODS, ODP | odfpy |
| `_process_csv` | CSV, TSV | csv (built-in) |
| `_process_xlsx` | XLSX, XLS | openpyxl |
| `_process_json` | JSON | json (built-in) |
| `_process_xml` | XML | lxml |
| `_process_yaml` | YAML | pyyaml |
| `_process_toml` | TOML | toml |
| `_process_parquet` | Parquet | pyarrow |
| `_process_sqlite` | SQLite | sqlite3 (built-in) |
| `_process_image` | PNG, JPG, GIF, BMP, WEBP, TIFF | Pillow + base64 |
| `_process_svg` | SVG | Read as XML text |
| `_process_audio` | MP3, WAV, M4A, OGG, FLAC, AAC | pydub |
| `_process_video` | MP4, MOV, WEBM, AVI, MKV | moviepy |
| `_process_zip` | ZIP | zipfile (built-in) |
| `_process_tar` | TAR, GZ, BZ2 | tarfile (built-in) |
| `_process_rar` | RAR | rarfile |
| `_process_eml` | EML | email (built-in) |
| `_process_msg` | MSG | extract-msg |
| `_process_html` | HTML | beautifulsoup4 |
| `_process_text` | PY, JS, TS, CSS, SQL, MD, TXT, etc. | UTF-8 decode |

#### 2. `POST /v1/upload` (New Endpoint in brain/main.py)
- Accepts multipart file upload + optional message
- Calls `process_file()` to extract content
- Caches result with a `file_id` for later retrieval
- If message included: runs it through full Brain pipeline with file content injected
- Images auto-route to Gemini Flash (vision model)

#### 3. `GET /v1/files/{file_id}` (New Endpoint in brain/main.py)
- Retrieves processed file content by ID
- Returns text, file_type, filename, metadata

#### 4. Pipeline Fix (brain/pipeline.py)
- Added `_has_images()` method to detect image content in messages
- Both `handle_request()` and `handle_stream()` now auto-route to `gemini-flash` when images detected
- Images are no longer silently dropped

### Errors During Build

| Error | Fix |
|---|---|
| `request` not defined in upload handler | Added `request: Request` parameter to endpoint function |
| Image upload returned 500 | Same fix — needed Request object to access `app.state.pipeline` |

### Test Results

```
=== CSV Upload ===
Status: 200 | file_id: file-3c0c5069 | Type: csv

=== CSV + Message (through Brain pipeline) ===
Status: 200 | Champ responded with data summary

=== Get File by ID ===
Status: 200 | Retrieved file content

=== Handler Detection (13 formats) ===
All detected correctly: pdf, csv, image, audio, video, docx, pptx, xlsx, zip, eml, html, text, yaml

=== Process Text/CSV/JSON/Image ===
All extracted correctly with proper metadata
```

---

## Errors & Lessons Learned

| Error | Root Cause | Lesson |
|---|---|---|
| `&&` fails in PowerShell | PowerShell syntax differs from bash | Run commands on separate lines in PS |
| `npm.ps1 cannot be loaded` | Script execution policy blocked | Run `Set-ExecutionPolicy` once per user |
| `vite is not recognized` | node_modules not installed | Always run `npm install` before `npm run dev` |
| Chocolatey install fails in VS Code | No admin privileges in VS Code terminal | System installs must use Admin PowerShell |
| `choco` not found after install | PATH not refreshed | Close and reopen terminal after system installs |
| Chocolatey corrupted install | Partial install from failed attempt | Use `winget` instead — built into Windows 11 |
| cairosvg import crash | Missing system library `libcairo` | Some Python packages need system-level C libraries |
| Packages "installed" but not importable | pip ran in wrong env or didn't complete | Always verify with `import` check, not just pip output |
| Frontend on port 3000 not 5173 | Vite config overrides default | Check actual output, don't assume default ports |

---

*Last updated: March 14, 2026*
