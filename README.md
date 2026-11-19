# YouTube to MP3 Converter Web Application

A modern, high-performance web application that extracts and converts YouTube share links (including regular videos, Shorts, mobile links, and YouTube Music) into high-fidelity MP3 audio files with ID3 metadata and embedded album art.

---

## ✨ Features

- **Drag & Drop / Paste Input**:
  - Drag and drop any YouTube link directly from another browser tab or desktop onto the drop zone.
  - One-click "Paste" button or standard keyboard shortcuts (`Ctrl+V` / `Cmd+V`).
  - Supports all link variations:
    - Standard: `https://www.youtube.com/watch?v=...`
    - Shortened share links: `https://youtu.be/...`
    - YouTube Shorts: `https://youtube.com/shorts/...`
    - Mobile & YouTube Music: `https://m.youtube.com/...` & `https://music.youtube.com/...`
- **Instant Metadata Extraction**:
  - Automatically fetches video title, channel/artist, duration, and high-resolution thumbnail before conversion.
  - Allows in-place editing of title and artist name before generating the MP3.
- **Studio-Quality Audio Encoding**:
  - Bitrate options: **320 kbps** (Studio Quality), **256 kbps**, **192 kbps**, **128 kbps**.
  - Uses FFmpeg's `libmp3lame` encoder for clean audio dynamics.
- **ID3 Metadata & HD Album Art Embedding**:
  - Injects Title (`TIT2`), Artist (`TPE1`), and Album (`TALB`) tags.
  - Automatically downloads and embeds the high-res thumbnail as front cover artwork (`APIC`) directly into the MP3 file, making it display beautifully in Apple Music, Spotify local files, iTunes, Android music players, and car infotainment systems.
- **Audio Trimmer (Optional)**:
  - Specify start and end timestamps (in seconds or MM:SS) to extract only a desired snippet/chorus of a song or podcast.
- **Live Conversion Progress**:
  - Real-time progress bar displaying download percentage, encoding step, speed, and ETA.
- **Built-in HTML5 Audio Preview**:
  - Listen to the converted MP3 directly in the browser with seeking, playback controls, and duration before downloading to disk.
- **Recent Conversions Library**:
  - Keeps track of converted files for the session with one-click re-download, preview playback, and deletion.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+
- FFmpeg (`ffmpeg` installed on system)
- Node.js (for yt-dlp JS challenge execution)

### 1. Installation
Clone or navigate to the project directory:
```bash
cd "youtube to mp3 converter"
```

Activate the virtual environment (pre-configured) or create a new one:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the Server
Run with the one-click restart script (automatically kills any existing process on port 8000 and restarts):
```bash
./run.sh
```

Or run the single command directly in your terminal:
```bash
fuser -k 8000/tcp || true; .venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open in Browser
Open your browser and navigate to:
```
http://localhost:8000
```

---

## 🛠 Project Structure

```
youtube to mp3 converter/
├── server.py              # FastAPI backend with yt-dlp and FFmpeg pipeline
├── requirements.txt       # Python dependencies (yt-dlp, fastapi, uvicorn, mutagen, etc.)
├── static/
│   ├── index.html         # Modern web client UI
│   ├── css/
│   │   └── style.css      # Dark glassmorphic styling & responsive layouts
│   └── js/
│       └── app.js         # Client-side drag/drop, audio player, API communication
└── downloads/             # Temporary folder storing converted MP3 files
```

---

## 🔒 Security & Privacy
- Temporary audio files are safely sanitized and automatically cleaned up.
- File operations prevent directory traversal and special character injection in filenames.
# link2audio-
