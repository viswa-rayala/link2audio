# Link2Audio — YouTube & Spotify to MP3 Converter 🎵

> A modern, high-performance web application to extract, tag, and download YouTube & Spotify audio as studio-grade 320kbps MP3s.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-link2mate.onrender.com-ff1a40?style=for-the-badge&logo=render)](https://link2mate.onrender.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)](Dockerfile)
[![Python](https://img.shields.io/badge/FastAPI-3.11+-009688?style=for-the-badge&logo=fastapi)](server.py)

---

### 🌐 Live Deployment
The application is live and accessible online at:  
👉 **[https://link2mate.onrender.com/](https://link2mate.onrender.com/)**

---

## ✨ Features & Capabilities

- **🟢 Dual YouTube & Spotify Support**:
  - Paste or drag & drop any YouTube video link (`youtube.com`, `youtu.be`, Shorts, YouTube Music) OR Spotify track link (`open.spotify.com/track/...`, `spotify:track:...`, `spotify.link/...`).
  - Seamlessly extracts metadata, matching Spotify tracks to pristine audio streams without requiring Spotify developer keys or user logins.

- **⚡ Instant Sub-Second Metadata (~150ms)**:
  - Fetches titles, artists, and HD album artwork via ultra-fast public oEmbed & embed resolvers.
  - Client-side automatic fallback ensures the preview card renders immediately even during server cold-starts.

- **🎛️ Drag & Drop / One-Click Paste**:
  - Drag and drop share links from other browser tabs directly onto the drop zone.
  - Native clipboard paste button (`Paste`) and keyboard shortcut (`Ctrl+V` / `Cmd+V`) support.
  - Handles all link variations:
    - Standard watch links (`youtube.com/watch?v=...`)
    - Shortened links (`youtu.be/...`)
    - YouTube Shorts (`youtube.com/shorts/...`)
    - YouTube Music & Mobile (`music.youtube.com/...`, `m.youtube.com/...`)

- **🛡️ Seamless Cloud Audio Resolver (Zero Cookies Required)**:
  - Powered by a direct stream resolution architecture (inspired by `y2mate.gs`) that extracts high-speed audio streams without getting blocked by YouTube bot checks on cloud datacenter IPs (Render, AWS, GCP).
  - No cookies, extensions, or sign-ins needed — just drop the link and get your MP3 instantly.
  - Secondary fallback engine using local `yt-dlp` (`visionos` / `tv_embedded`) ensures reliable conversions.

- **🧹 100% Ephemeral (Zero Permanent Disk Storage)**:
  - Audio files are stored temporarily in volatile system temp memory (`/tmp`).
  - **Instant Post-Download Cleanup**: Uses Starlette background tasks to permanently destroy the temporary MP3 the instant the browser finishes downloading the stream.
  - **Auto Garbage Collector**: Any uncollected preview files older than 5 minutes are purged automatically.

- **🎧 Built-in HTML5 Audio Preview**:
  - Listen to converted audio directly in the browser with seeking, playback controls, and duration display before saving to disk.

- **✂️ Audio Trimmer (Optional)**:
  - Extract a specific segment, chorus, or podcast snippet by setting start and end timestamps.

- **🏷️ ID3 Tags & HD Cover Art Embedding**:
  - Tags MP3 files with Song Title (`TIT2`), Artist (`TPE1`), and Album (`TALB`).
  - Embeds the YouTube thumbnail as front album cover artwork (`APIC`), displaying seamlessly across Apple Music, Spotify Local Files, iTunes, Android, and car infotainment systems.

- **🎚️ Studio Quality Bitrates**:
  - Select between **320 kbps** (Studio Quality), **256 kbps**, **192 kbps**, or **128 kbps** encoded via FFmpeg (`libmp3lame`).

---

## 🚀 Quick Start Guide (Local Setup)

### Prerequisites
- Python 3.10+
- FFmpeg installed (`sudo apt install ffmpeg` on Ubuntu/Debian)
- Node.js installed (`sudo apt install nodejs`)

### 1. Installation
Clone or navigate to the repository:
```bash
git clone https://github.com/viswa-rayala/link2audio-.git
cd link2audio-
```

Create and activate the virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Server
Use the included helper script (kills any stale process on port 8000 and restarts with auto-reload):
```bash
./run.sh
```

Or run directly with Uvicorn:
```bash
fuser -k 8000/tcp || true; .venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open in Browser
Visit:
```
http://localhost:8000
```

---

## 🐳 Docker Deployment

Run locally with Docker:
```bash
# Build the container
docker build -t link2audio .

# Run container on port 8000
docker run -p 8000:8000 link2audio
```

---

## ☁️ Deploying to Render (Step-by-Step)

1. Fork or push this repository to GitHub.
2. Sign in to **[Render.com](https://render.com)** with your GitHub account.
3. Click **New +** -> **Web Service**.
4. Select your repository (`link2audio-`).
5. Choose **Docker** as the runtime (Render will automatically detect the [Dockerfile](Dockerfile)).
6. Select the **Free** instance plan.
7. Click **Deploy Web Service**.

Your live URL will be ready in 1–2 minutes!

---

## 🛠 Project Structure

```
.
├── Dockerfile             # Production container setup (FFmpeg + Node.js + Python)
├── .dockerignore          # Docker build optimizations
├── .gitignore             # Keeps repository free of temporary audio files
├── render.yaml            # 1-click blueprint deployment configuration
├── requirements.txt       # Production dependencies
├── run.sh                 # 1-command port killer & server starter
├── server.py              # FastAPI backend with multi-profile extractor & ephemeral cleanup
└── static/
    ├── index.html         # Responsive web interface
    ├── css/
    │   └── style.css      # Dark glassmorphic design & animations
    └── js/
        └── app.js         # Client-side audio preview, drag & drop, and API handling
```

---

## 🔒 Privacy & Safety
- Conversion files are treated as ephemeral streams and are deleted immediately upon download.
- No personal user data or listening history is permanently stored.
- Sanitized filenames prevent directory traversal and header injection.

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
