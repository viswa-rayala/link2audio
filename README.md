# Link2Audio — YouTube, Spotify & Instagram Downloader (MP3 & MP4) 🎵🎬📸

> A modern, high-performance web application to extract, convert, and download YouTube videos, Spotify tracks, and Instagram Reels/Posts as studio-grade 320kbps MP3 audio or crisp 720p/1080p MP4 HD video.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-link2mate.onrender.com-ff1a40?style=for-the-badge&logo=render)](https://link2mate.onrender.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)](Dockerfile)
[![Python](https://img.shields.io/badge/FastAPI-3.11+-009688?style=for-the-badge&logo=fastapi)](server.py)

---

### 🌐 Live Deployment
The application is live and accessible online at:  
👉 **[https://link2mate.onrender.com/](https://link2mate.onrender.com/)**

---

## ✨ Features & Capabilities

- **🎬 Dual Format Conversion (MP3 Audio & MP4 Video)**:
  - **MP3 Audio**: Studio quality up to 320 kbps (with 256k, 192k, 128k options), custom ID3 tags, and embedded HD album cover artwork.
  - **MP4 Video**: High-definition 720p HD / 1080p Full HD video streams packaged with AAC audio, ready for offline playback on any device.

- **🔥 Triple Platform Engine: YouTube, Spotify & Instagram**:
  - **YouTube**: Standard videos, YouTube Shorts, YouTube Music (`youtube.com`, `youtu.be`, `music.youtube.com`).
  - **Spotify**: Seamlessly matches Spotify tracks (`open.spotify.com/track/...`, `spotify:track:...`) to high-fidelity audio without requiring Spotify developer accounts.
  - **Instagram**: Public Reels, Posts, Videos, and IGTV (`instagram.com/reel/...`, `instagram.com/p/...`, `instagram.com/share/r/...`). Supports both HD MP4 video download and 320kbps MP3 audio extraction.

- **🛡️ 100% Cookie-Free & Bot-Resistant**:
  - Powered by high-speed cloud stream clusters and TLS fingerprint browser impersonation (`curl-cffi`).
  - Zero cookies required, zero user accounts, zero browser extensions. Just paste a link and convert immediately.

- **⚡ Instant Sub-Second Metadata (~150ms)**:
  - Fetches titles, artists, and HD album artwork via ultra-fast public oEmbed & embed resolvers.
  - Client-side automatic fallback ensures the preview card renders immediately even during server cold-starts.

- **🎛️ Drag & Drop / One-Click Paste**:
  - Drag and drop share links from other browser tabs directly onto the drop zone.
  - Native clipboard paste button (`Paste`) and keyboard shortcut (`Ctrl+V` / `Cmd+V`) support.
  - Handles all link variations (standard, shortened, mobile app shares).

- **🧹 100% Ephemeral (Zero Permanent Disk Storage)**:
  - Audio and video files are stored temporarily in volatile system temp memory (`/tmp`).
  - **Instant Post-Download Cleanup**: Uses Starlette background tasks to permanently destroy temporary MP3/MP4 files the instant the browser finishes downloading.
  - **Auto Garbage Collector**: Any uncollected preview files older than 5 minutes are purged automatically.

- **🎥 Built-in HTML5 Audio & Video Player**:
  - Preview MP3 audio directly in the browser with seeking and playback controls.
  - Watch converted MP4 videos inside the inline responsive HTML5 video player before downloading.

- **✂️ Trimmer (Optional)**:
  - Extract a specific segment, chorus, or snippet by setting start and end timestamps.

- **🏷️ ID3 Tags & HD Cover Art Embedding (MP3)**:
  - Tags MP3 files with Song Title (`TIT2`), Artist (`TPE1`), and Album (`TALB`).
  - Embeds high-resolution cover artwork (`APIC`), displaying seamlessly across Apple Music, Spotify Local Files, iTunes, Android, and car infotainment systems.

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
