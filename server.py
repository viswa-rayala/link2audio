import os
import re
import time
import json
import uuid
import shutil
import tempfile
import urllib.request
import ssl
import base64
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
from pydantic import BaseModel

import yt_dlp
import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Use system ephemeral temp directory so files are NEVER stored on user local repo storage
TEMP_DIR = Path(tempfile.gettempdir()) / "yt_mp3_converter_temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="YouTube to MP3 Converter API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

# In-memory storage for active and recent jobs
jobs: Dict[str, Dict[str, Any]] = {}

def extract_video_id(url: str) -> Optional[str]:
    """Extract 11-char video ID from any YouTube URL format."""
    pattern = r'(?:https?:\/\/)?(?:www\.|m\.|music\.)?(?:youtube\.com\/(?:watch\?.*?v=|shorts\/|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url.strip())
    return match.group(1) if match else None

def clean_youtube_url(url: str) -> str:
    """Extract and normalize canonical YouTube video URL from various formats."""
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url.strip()

def extract_spotify_id(url: str) -> Optional[str]:
    """Extract 22-char Spotify track ID from any Spotify URL (supports localized, embed, and shortened)."""
    clean_u = url.strip()
    if "spotify.link" in clean_u or "spoti.fi" in clean_u:
        try:
            req = urllib.request.Request(clean_u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                clean_u = resp.geturl()
        except Exception:
            pass
    pattern = r'(?:open\.spotify\.com\/(?:intl-[a-z]{2,5}\/)?track\/|spotify:track:)([a-zA-Z0-9]{22})'
    match = re.search(pattern, clean_u)
    return match.group(1) if match else None

def fetch_spotify_track_info(track_id: str) -> Optional[Dict[str, Any]]:
    """Instant lookup of Spotify track metadata, duration, and HD album art."""
    try:
        url = f"https://open.spotify.com/embed/track/{track_id}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=6) as r:
            html = r.read().decode("utf-8")
        
        matches = re.findall(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
        if matches:
            data = json.loads(matches[0])
            entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
            if entity and (entity.get('name') or entity.get('title')):
                title = entity.get('name') or entity.get('title')
                artists_list = entity.get('artists', [])
                artist = ", ".join([a.get('name') for a in artists_list if a.get('name')]) if artists_list else "Spotify Artist"
                duration_ms = entity.get('duration')
                duration_sec = int(duration_ms / 1000) if duration_ms else None
                
                images = entity.get('visualIdentity', {}).get('image', [])
                thumbnail = ""
                if images:
                    sorted_imgs = sorted(images, key=lambda x: x.get('maxWidth', 0), reverse=True)
                    thumbnail = sorted_imgs[0].get('url', '')
                    
                return {
                    "id": track_id,
                    "platform": "spotify",
                    "url": f"https://open.spotify.com/track/{track_id}",
                    "title": title,
                    "author": artist,
                    "duration": duration_sec,
                    "duration_formatted": format_duration(duration_sec) if duration_sec else "Ready to convert",
                    "thumbnail": thumbnail,
                    "preview_url": entity.get('audioPreview', {}).get('url'),
                    "view_count": 0
                }
    except Exception as e:
        print(f"Spotify embed metadata fetch note: {e}")
    
    # Fallback to Spotify oEmbed
    try:
        oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{track_id}"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            return {
                "id": track_id,
                "platform": "spotify",
                "url": f"https://open.spotify.com/track/{track_id}",
                "title": data.get("title", "Spotify Track"),
                "author": "Spotify Artist",
                "duration": None,
                "duration_formatted": "Ready to convert",
                "thumbnail": data.get("thumbnail_url", ""),
                "view_count": 0
            }
    except Exception as e2:
        print(f"Spotify oEmbed fallback note: {e2}")
        return None

def search_youtube_for_track(artist: str, title: str) -> Optional[str]:
    """Search YouTube for the corresponding audio track and return the 11-char video ID."""
    clean_artist = re.sub(r'[\(\)\[\]\{\}\/\\,"]', ' ', artist).strip()
    clean_title = re.sub(r'[\(\)\[\]\{\}\/\\,"]', ' ', title).strip()
    queries = [
        f"{clean_artist} - {clean_title} audio",
        f"{clean_artist} {clean_title} official",
        f"{clean_artist} {clean_title}"
    ]
    
    ctx = ssl.create_default_context()
    for q in queries:
        try:
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}"
            req = urllib.request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            })
            with urllib.request.urlopen(req, context=ctx, timeout=6) as r:
                html = r.read().decode("utf-8")
                vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                if vids:
                    return vids[0]
        except Exception as e:
            print(f"YouTube search attempt note for '{q}': {e}")
            
    # Fallback: yt-dlp ytsearch
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'default_search': 'ytsearch1',
            'no_warnings': True,
            'socket_timeout': 6,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch1:{clean_artist} {clean_title} audio", download=False)
            if res and 'entries' in res and len(res['entries']) > 0:
                return res['entries'][0].get('id')
    except Exception as e2:
        print(f"yt-dlp search fallback note: {e2}")
        
    return None

def fetch_fast_video_info(video_id: str) -> Optional[Dict[str, Any]]:
    """Instant lookup via YouTube's public oEmbed API (<200ms response time)."""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            hq_thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            return {
                "id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": data.get("title", "YouTube Audio"),
                "author": data.get("author_name", "YouTube Channel"),
                "duration": None,
                "duration_formatted": "Ready to convert",
                "thumbnail": data.get("thumbnail_url") or hq_thumb,
                "view_count": 0
            }
    except Exception as e:
        print(f"Fast oEmbed lookup note: {e}")
        return None

_cached_tubeapi_key = "66d0abdc85f3b52ac9df11d95ebce90a"
_cached_y2mate_key = "y2mate_3bf573e166560094af6dd7eae06709db866e5b28dfb0189b8a9f254ff8119aee"
_cached_ytmp3_key = "ytmp3_9243bb365836f75a94b74494405da4575fdea0290bf6206cac235a46c68a3dc3"

def get_tubeapi_key(force_refresh: bool = False) -> str:
    """Retrieve or dynamically scrape key from tubeapi.org."""
    global _cached_tubeapi_key
    if _cached_tubeapi_key and not force_refresh:
        return _cached_tubeapi_key
    try:
        req = urllib.request.Request("https://tubeapi.org/", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
            html = resp.read().decode("utf-8")
            m = re.search(r"var apiKey=['\"]([^'\"]+)['\"];", html)
            if m:
                _cached_tubeapi_key = m.group(1)
                return _cached_tubeapi_key
    except Exception as e:
        print(f"TubeAPI key fetch note: {e}")
    return _cached_tubeapi_key or "66d0abdc85f3b52ac9df11d95ebce90a"

def get_y2mate_key(force_refresh: bool = False) -> str:
    """Retrieve or dynamically decode the converter worker key from y2mate."""
    global _cached_y2mate_key
    if _cached_y2mate_key and not force_refresh:
        return _cached_y2mate_key
    try:
        req = urllib.request.Request(
            "https://y2mate.gs/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
            html = resp.read().decode("utf-8")
            m = re.search(r"decodeKey\([\"']([^\"']+)[\"']\)", html)
            if m:
                decoded = base64.b64decode(m.group(1)[::-1]).decode("utf-8")
                if decoded.startswith("y2mate_"):
                    _cached_y2mate_key = decoded
                    return decoded
    except Exception as e:
        print(f"Dynamic y2mate key fetch note: {e}")
    return _cached_y2mate_key or "y2mate_3bf573e166560094af6dd7eae06709db866e5b28dfb0189b8a9f254ff8119aee"

def get_ytmp3_key(force_refresh: bool = False) -> str:
    """Retrieve or dynamically decode the converter worker key from ytmp3.gl."""
    global _cached_ytmp3_key
    if _cached_ytmp3_key and not force_refresh:
        return _cached_ytmp3_key
    try:
        req = urllib.request.Request(
            "https://ytmp3.gl/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
            html = resp.read().decode("utf-8")
            m = re.search(r"decodeKey\([\"']([^\"']+)[\"']\)", html)
            if m:
                decoded = base64.b64decode(m.group(1)[::-1]).decode("utf-8")
                if decoded.startswith("ytmp3_"):
                    _cached_ytmp3_key = decoded
                    return decoded
    except Exception as e:
        print(f"Dynamic ytmp3 key fetch note: {e}")
    return _cached_ytmp3_key or "ytmp3_9243bb365836f75a94b74494405da4575fdea0290bf6206cac235a46c68a3dc3"

def fetch_via_converter_api(video_id: str, job: Dict[str, Any], quality: str, raw_output_path: str) -> Dict[str, Any]:
    """
    Direct audio resolution engine utilizing multi-cluster failover:
    Strategy 1: TubeAPI / 123tokyo cluster (Fastest, <1s response, global CDN stream)
    Strategy 2: etacloud.org cluster (Official y2mate.gs upstream)
    Strategy 3: gammacloud.net cluster (Official ytmp3.gl upstream)
    Strategy 4: Cloudflare worker fallback
    """
    ctx = ssl.create_default_context()
    
    # 1. Strategy 1: TubeAPI / 123tokyo Cluster (Ultra fast, verified cloud deployment safe)
    try:
        job['status_text'] = "Connecting to high-speed audio resolver..."
        job['progress'] = 25
        api_key = get_tubeapi_key()
        now_ms = int(time.time() * 1000)
        tube_url = f"https://hidden-sun-3c87.holy-breeze-fec5.workers.dev/?e=i&v={video_id}&api_key={api_key}&_={now_ms}"
        req = urllib.request.Request(
            tube_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://tubeapi.org/"
            }
        )
        with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
            
        title = data.get("title") or ""
        download_url = data.get("link")
        
        # If it's processing, poll up to 20 times (every 3 seconds)
        if data.get("status") == "processing" and not download_url:
            job['status_text'] = "Extracting audio track from high-speed cluster..."
            for step in range(20):
                time.sleep(3)
                poll_url = f"https://hidden-sun-3c87.holy-breeze-fec5.workers.dev/?e=i&v={video_id}&api_key={api_key}&_={int(time.time() * 1000)}"
                p_req = urllib.request.Request(poll_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://tubeapi.org/"})
                try:
                    with urllib.request.urlopen(p_req, context=ctx, timeout=10) as pr:
                        p_data = json.loads(pr.read().decode("utf-8"))
                        if p_data.get("title") and not title:
                            title = p_data.get("title")
                        if p_data.get("status") == "ok" and p_data.get("link"):
                            download_url = p_data.get("link")
                            break
                        job['progress'] = min(25 + (step * 2), 68)
                except Exception as pe:
                    print(f"TubeAPI poll warning: {pe}")
                    
        if download_url:
            job['status'] = 'downloading'
            job['progress'] = 70
            job['status_text'] = 'Streaming high-speed audio data...'
            dl_req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(dl_req, context=ctx, timeout=90) as dl_resp:
                with open(raw_output_path, "wb") as f:
                    while True:
                        chunk = dl_resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
            if os.path.exists(raw_output_path) and os.path.getsize(raw_output_path) > 10000:
                return {"title": title, "duration": data.get("duration"), "format": "mp3"}
    except Exception as e:
        print(f"TubeAPI strategy note: {e}")

    # 2. Strategy 2: Official eta.etacloud.org Cluster (y2mate.gs)
    try:
        y_key = get_y2mate_key()
        y_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://y2mate.gs/",
            "Origin": "https://y2mate.gs"
        }
        job['status_text'] = "Authenticating with conversion cluster..."
        job['progress'] = 30
        now_ms = int(time.time() * 1000)
        auth_url = f"https://eta.etacloud.org/api/v1/auth?api_key={y_key}&_={now_ms}"
        req = urllib.request.Request(auth_url, headers=y_headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            auth_data = json.loads(r.read().decode("utf-8"))
        bearer = auth_data.get("key")
        
        if bearer:
            init_url = f"https://eta.etacloud.org/api/v1/init?_={int(time.time() * 1000)}"
            init_headers = dict(y_headers)
            init_headers["Authorization"] = f"Bearer {bearer}"
            req = urllib.request.Request(init_url, headers=init_headers)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                init_data = json.loads(r.read().decode("utf-8"))
            convert_url = init_data.get("convertURL")
            
            if convert_url:
                job['status_text'] = "Resolving audio format..."
                job['progress'] = 45
                c_url = f"{convert_url}&v={video_id}&f=mp3&_={int(time.time() * 1000)}"
                req = urllib.request.Request(c_url, headers=y_headers)
                with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
                    c_data = json.loads(r.read().decode("utf-8"))
                    
                if c_data.get("redirect") == 1:
                    redir_url = c_data["redirectURL"]
                    if "&v=" not in redir_url:
                        redir_url += f"&v={video_id}&f=mp3&_={int(time.time() * 1000)}"
                    req = urllib.request.Request(redir_url, headers=y_headers)
                    with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
                        c_data = json.loads(r.read().decode("utf-8"))
                
                download_url = c_data.get("downloadURL")
                title = c_data.get("title") or ""
                
                # If progress needed, poll
                if c_data.get("status") == "progress" and c_data.get("progressURL"):
                    prog_url = c_data["progressURL"]
                    job['status_text'] = "Converting track..."
                    for step in range(25):
                        time.sleep(2)
                        p_req = urllib.request.Request(f"{prog_url}&_={int(time.time()*1000)}", headers=y_headers)
                        try:
                            with urllib.request.urlopen(p_req, context=ctx, timeout=10) as p_resp:
                                p_data = json.loads(p_resp.read().decode("utf-8"))
                                job['progress'] = min(45 + (step * 2), 68)
                                if p_data.get("title") and not title:
                                    title = p_data.get("title")
                                if p_data.get("progress", 0) >= 3 or p_data.get("downloadURL"):
                                    download_url = p_data.get("downloadURL") or download_url
                                    break
                        except Exception as poll_e:
                            print(f"Etacloud poll note: {poll_e}")
                            
                if download_url:
                    job['status'] = 'downloading'
                    job['progress'] = 70
                    job['status_text'] = 'Streaming high-speed audio data...'
                    dl_headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://y2mate.gs/"}
                    dl_req = urllib.request.Request(download_url, headers=dl_headers)
                    with urllib.request.urlopen(dl_req, context=ctx, timeout=90) as dl_resp:
                        with open(raw_output_path, "wb") as f:
                            while True:
                                chunk = dl_resp.read(65536)
                                if not chunk:
                                    break
                                f.write(chunk)
                    if os.path.exists(raw_output_path) and os.path.getsize(raw_output_path) > 10000:
                        return {"title": title, "format": "mp3"}
    except Exception as e:
        print(f"Etacloud strategy note: {e}")

    # 3. Strategy 3: Official gamma.gammacloud.net Cluster (ytmp3.gl)
    try:
        g_key = get_ytmp3_key()
        g_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://ytmp3.gl/",
            "Origin": "https://ytmp3.gl"
        }
        now_ms = int(time.time() * 1000)
        auth_url = f"https://gamma.gammacloud.net/api/v1/auth?api_key={g_key}&_={now_ms}"
        req = urllib.request.Request(auth_url, headers=g_headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            auth_data = json.loads(r.read().decode("utf-8"))
        bearer = auth_data.get("key")
        
        if bearer:
            init_url = f"https://gamma.gammacloud.net/api/v1/init?_={int(time.time() * 1000)}"
            init_headers = dict(g_headers)
            init_headers["Authorization"] = f"Bearer {bearer}"
            req = urllib.request.Request(init_url, headers=init_headers)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                init_data = json.loads(r.read().decode("utf-8"))
            convert_url = init_data.get("convertURL")
            
            if convert_url:
                c_url = f"{convert_url}&v={video_id}&f=mp3&_={int(time.time() * 1000)}"
                req = urllib.request.Request(c_url, headers=g_headers)
                with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
                    c_data = json.loads(r.read().decode("utf-8"))
                    
                if c_data.get("redirect") == 1:
                    redir_url = c_data["redirectURL"]
                    if "&v=" not in redir_url:
                        redir_url += f"&v={video_id}&f=mp3&_={int(time.time() * 1000)}"
                    req = urllib.request.Request(redir_url, headers=g_headers)
                    with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
                        c_data = json.loads(r.read().decode("utf-8"))
                
                download_url = c_data.get("downloadURL")
                title = c_data.get("title") or ""
                
                if download_url:
                    dl_headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://ytmp3.gl/"}
                    dl_req = urllib.request.Request(download_url, headers=dl_headers)
                    with urllib.request.urlopen(dl_req, context=ctx, timeout=90) as dl_resp:
                        with open(raw_output_path, "wb") as f:
                            while True:
                                chunk = dl_resp.read(65536)
                                if not chunk:
                                    break
                                f.write(chunk)
                    if os.path.exists(raw_output_path) and os.path.getsize(raw_output_path) > 10000:
                        return {"title": title, "format": "mp3"}
    except Exception as e:
        print(f"Gammacloud strategy note: {e}")

    # 4. Strategy 4: Cloudflare Worker fallback
    try:
        now_ms = int(time.time() * 1000)
        worker_init_url = f"https://fancy-sea-5d3d.holy-breeze-fec5.workers.dev/?m=i&k={get_y2mate_key()}&v={video_id}&f=mp3&_={now_ms}"
        req = urllib.request.Request(worker_init_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://y2mate.gs/"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("error", 0) == 0:
            download_url = data.get("downloadURL")
            title = data.get("title") or ""
            if download_url:
                dl_req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://y2mate.gs/"})
                with urllib.request.urlopen(dl_req, context=ctx, timeout=90) as dl_resp:
                    with open(raw_output_path, "wb") as f:
                        while True:
                            chunk = dl_resp.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                if os.path.exists(raw_output_path) and os.path.getsize(raw_output_path) > 10000:
                    return {"title": title, "format": "mp3"}
    except Exception as e:
        print(f"Worker strategy note: {e}")

    raise Exception("Could not resolve audio stream via converter engines")

def sanitize_filename(name: str) -> str:
    """Sanitize string for safe filesystem usage and HTTP headers."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r'[\s_]+', ' ', clean).strip()
    return clean[:120] if clean else "audio"

def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds into readable MM:SS or HH:MM:SS."""
    if not seconds or seconds < 0:
        return "Unknown"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def purge_file(path: Optional[str], job_id: Optional[str] = None):
    """Safely remove a file and update job state."""
    if not path:
        return
    try:
        p = Path(path)
        if p.exists():
            p.unlink(missing_ok=True)
            print(f"Ephemeral cleanup: removed {path}")
    except Exception as e:
        print(f"Error purging file {path}: {e}")
    
    if job_id and job_id in jobs:
        jobs[job_id]['file_path'] = None

class InfoRequest(BaseModel):
    url: str

class ConvertRequest(BaseModel):
    url: str
    quality: str = "320" # 128, 192, 256, 320
    title: Optional[str] = None
    artist: Optional[str] = None
    embed_thumbnail: bool = True
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None

@app.post("/api/info")
def get_video_info(req: InfoRequest):
    """Fetch video or Spotify track metadata with fast lookup."""
    url_str = req.url.strip()
    
    # 1. Spotify Track Path
    spotify_id = extract_spotify_id(url_str)
    if spotify_id:
        spot_info = fetch_spotify_track_info(spotify_id)
        if spot_info:
            return {"success": True, "data": spot_info}
        raise HTTPException(status_code=400, detail="Could not load Spotify track details. Please check the link.")
        
    # 2. YouTube Path
    clean_url = clean_youtube_url(url_str)
    video_id = extract_video_id(clean_url)
    
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid link. Please provide a valid YouTube or Spotify track URL.")

    # 1. Ultra-fast path: YouTube public oEmbed API (~150ms)
    fast_info = fetch_fast_video_info(video_id)
    if fast_info:
        return {"success": True, "data": fast_info}
    
    # 2. Fallback: yt-dlp
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'socket_timeout': 5,
        'extractor_args': {'youtube': {'player_client': ['android']}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if not info:
                raise HTTPException(status_code=400, detail="Could not extract video metadata.")
            
            title = info.get('title') or "Unknown Title"
            author = info.get('uploader') or info.get('channel') or "Unknown Artist"
            duration = info.get('duration')
            thumbnail = info.get('thumbnail') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            view_count = info.get('view_count') or 0
            
            return {
                "success": True,
                "data": {
                    "id": video_id,
                    "platform": "youtube",
                    "url": clean_url,
                    "title": title,
                    "author": author,
                    "duration": duration,
                    "duration_formatted": format_duration(duration),
                    "thumbnail": thumbnail,
                    "view_count": view_count
                }
            }
    except Exception as e:
        error_msg = str(e)
        if "is not a valid URL" in error_msg or "Unsupported URL" in error_msg:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL. Please provide a valid YouTube link.")
        raise HTTPException(status_code=400, detail=f"Failed to fetch video details: {error_msg}")

def run_conversion_job(job_id: str, req: ConvertRequest):
    """
    Seamless worker task that converts YouTube & Spotify links to studio-grade MP3.
    Uses the high-speed cloud worker engine as primary resolver to completely
    bypass YouTube bot blocks on datacenter IPs without requiring cookies.
    """
    job = jobs[job_id]
    job['status'] = 'downloading'
    job['progress'] = 10
    job['status_text'] = 'Analyzing audio source...'

    url_str = req.url.strip()
    spotify_id = extract_spotify_id(url_str)

    try:
        out_base = str(TEMP_DIR / job_id)
        raw_mp3_path = f"{out_base}_raw.mp3"
        final_mp3_path = Path(f"{out_base}.mp3")
        quality = req.quality if req.quality in ["128", "192", "256", "320"] else "320"
        
        video_id = None
        duration = None
        
        if spotify_id:
            job['status_text'] = 'Matching Spotify track to high-fidelity audio stream...'
            job['progress'] = 15
            spot_meta = fetch_spotify_track_info(spotify_id)
            video_title = req.title.strip() if req.title and req.title.strip() else (spot_meta.get("title") if spot_meta else "Spotify Track")
            video_artist = req.artist.strip() if req.artist and req.artist.strip() else (spot_meta.get("author") if spot_meta else "Spotify Artist")
            thumbnail_url = spot_meta.get("thumbnail") if spot_meta else ""
            duration = spot_meta.get("duration") if spot_meta else None
            
            # Find corresponding YouTube video ID
            video_id = search_youtube_for_track(video_artist, video_title)
            if not video_id:
                raise Exception(f"Could not find an audio stream matching '{video_artist} - {video_title}'")
            clean_url = f"https://www.youtube.com/watch?v={video_id}"
        else:
            clean_url = clean_youtube_url(url_str)
            video_id = extract_video_id(clean_url)
            fast_meta = fetch_fast_video_info(video_id) if video_id else None
            video_title = req.title.strip() if req.title and req.title.strip() else (fast_meta.get("title") if fast_meta else "YouTube Audio")
            video_artist = req.artist.strip() if req.artist and req.artist.strip() else (fast_meta.get("author") if fast_meta else "YouTube")
            thumbnail_url = fast_meta.get("thumbnail") if fast_meta else (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "")

        converted_via_worker = False

        # 1. Primary Engine: High-speed Cloudflare Worker (inspired by y2mate.gs)
        # Avoids YouTube datacenter IP blocks on Render completely without cookies
        if video_id:
            try:
                worker_res = fetch_via_converter_api(video_id, job, quality, raw_mp3_path)
                if not spotify_id and worker_res.get("title") and (not req.title or not req.title.strip()):
                    video_title = worker_res["title"]
                if not duration and worker_res.get("duration"):
                    duration = int(worker_res["duration"])
                converted_via_worker = True
            except Exception as worker_err:
                print(f"Converter worker note ({worker_err}), falling back to secondary yt-dlp...")
                if os.path.exists(raw_mp3_path):
                    try:
                        os.remove(raw_mp3_path)
                    except Exception:
                        pass

        # 2. Secondary Engine: Local yt-dlp fallback (visionOS / Android profiles)
        if not converted_via_worker:
            job['status_text'] = 'Resolving audio stream via secondary engine...'
            raw_output = f"{out_base}.%(ext)s"
            client_profiles = [
                ['visionos'],
                ['tv_embedded'],
                ['android_creator'],
                ['android']
            ]
            meta = None
            last_err = None
            for profile in client_profiles:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': raw_output,
                    'socket_timeout': 30,
                    'extractor_args': {
                        'youtube': {
                            'player_client': profile,
                            'player_skip': ['web', 'mweb']
                        }
                    },
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': quality,
                    }],
                    'quiet': True,
                    'no_warnings': True,
                }
                if shutil.which("node"):
                    ydl_opts['js_runtimes'] = {'node': {'path': shutil.which("node")}}
                    ydl_opts['remote_components'] = ['ejs:github']
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        meta = ydl.extract_info(clean_url, download=True)
                        if meta:
                            if not req.title or not req.title.strip():
                                video_title = meta.get('title') or video_title
                            if not req.artist or not req.artist.strip():
                                video_artist = meta.get('uploader') or meta.get('channel') or video_artist
                            if meta.get('thumbnail'):
                                thumbnail_url = meta.get('thumbnail')
                            duration = meta.get('duration')
                            break
                except Exception as err:
                    last_err = err
                    continue
            if not meta and not final_mp3_path.exists():
                job['status'] = 'error'
                job['error'] = f"Unable to extract audio for this video: {last_err or 'Stream blocked'}"
                job['status_text'] = job['error']
                return

        # If converted via worker, transcode / trim with FFmpeg to produce final_mp3_path
        if converted_via_worker:
            job['progress'] = 80
            job['status'] = 'converting'
            job['status_text'] = f'Encoding {quality}kbps MP3 audio with FFmpeg...'
            
            ffmpeg_cmd = ["ffmpeg", "-y", "-i", raw_mp3_path]
            if req.trim_start is not None and req.trim_start > 0:
                ffmpeg_cmd.extend(["-ss", str(req.trim_start)])
            if req.trim_end is not None and req.trim_end > 0:
                ffmpeg_cmd.extend(["-to", str(req.trim_end)])
            ffmpeg_cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{quality}k", str(final_mp3_path)])
            
            res = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if res.returncode != 0 or not final_mp3_path.exists():
                # If re-encoding failed, move raw file to final
                shutil.move(raw_mp3_path, str(final_mp3_path))
            else:
                if os.path.exists(raw_mp3_path):
                    os.remove(raw_mp3_path)

        if not final_mp3_path.exists():
            job['status'] = 'error'
            job['error'] = "MP3 conversion failed - output file could not be generated."
            job['status_text'] = job['error']
            return

        # Trimming for yt-dlp path if requested
        if not converted_via_worker and (req.trim_start is not None or req.trim_end is not None):
            job['progress'] = 80
            job['status_text'] = 'Trimming audio segment...'
            trimmed_path = Path(f"{out_base}_trimmed.mp3")
            ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(final_mp3_path)]
            if req.trim_start is not None and req.trim_start > 0:
                ffmpeg_cmd.extend(["-ss", str(req.trim_start)])
            if req.trim_end is not None and req.trim_end > 0:
                ffmpeg_cmd.extend(["-to", str(req.trim_end)])
            ffmpeg_cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{quality}k", str(trimmed_path)])
            res = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if res.returncode == 0 and trimmed_path.exists():
                final_mp3_path.unlink(missing_ok=True)
                trimmed_path.rename(final_mp3_path)

        # ID3 Tagging & Album Art with Mutagen
        job['status'] = 'tagging'
        job['progress'] = 90
        job['status_text'] = 'Embedding ID3 metadata & album art...'

        try:
            audio = MP3(str(final_mp3_path), ID3=ID3)
            try:
                audio.add_tags()
            except Exception:
                pass

            audio.tags.add(TIT2(encoding=3, text=video_title))
            audio.tags.add(TPE1(encoding=3, text=video_artist))
            audio.tags.add(TALB(encoding=3, text="Spotify Track" if spotify_id else "YouTube Audio"))

            if req.embed_thumbnail and thumbnail_url:
                try:
                    thumb_req = urllib.request.Request(
                        thumbnail_url,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    with urllib.request.urlopen(thumb_req, timeout=6) as resp:
                        img_data = resp.read()
                        mime = 'image/jpeg' if ('jpg' in thumbnail_url or 'jpeg' in thumbnail_url) else 'image/png'
                        audio.tags.add(APIC(
                            encoding=3,
                            mime=mime,
                            type=3,
                            desc='Cover',
                            data=img_data
                        ))
                except Exception as thumb_err:
                    print(f"Thumbnail embed note: {thumb_err}")

            audio.save()
            if not duration and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                duration = int(audio.info.length)
        except Exception as tag_err:
            print(f"ID3 Tagging note: {tag_err}")

        # Finalize file details
        safe_title = sanitize_filename(video_title)
        safe_artist = sanitize_filename(video_artist)
        generic_artists = {"youtube", "spotify artist", "spotify", "unknown artist"}
        if safe_artist and safe_artist.lower() not in generic_artists and not safe_title.lower().startswith(safe_artist.lower()):
            download_filename = f"{safe_artist} - {safe_title}.mp3"
        else:
            download_filename = f"{safe_title}.mp3"
        file_size = final_mp3_path.stat().st_size

        job['progress'] = 100
        job['status'] = 'completed'
        job['status_text'] = 'Conversion complete! Your MP3 is ready.'
        job['file_path'] = str(final_mp3_path)
        job['filename'] = download_filename
        job['file_size'] = file_size
        job['file_size_formatted'] = f"{file_size / (1024 * 1024):.2f} MB"
        job['title'] = video_title
        job['artist'] = video_artist
        job['duration'] = duration
        job['duration_formatted'] = format_duration(duration)
        job['thumbnail'] = thumbnail_url
        job['quality'] = f"{quality} kbps"
        job['expires_at'] = time.time() + 300 # 5 minutes ephemeral lifespan

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        job['status_text'] = f"Failed: {str(e)}"
        print(f"Error converting {clean_url}: {e}")

@app.post("/api/convert")
def start_conversion(req: ConvertRequest):
    """Start an asynchronous conversion job."""
    clean_url = clean_youtube_url(req.url)
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        'id': job_id,
        'url': clean_url,
        'status': 'queued',
        'progress': 0,
        'status_text': 'Preparing download request...',
        'created_at': time.time(),
        'error': None,
        'file_path': None,
        'filename': None,
        'file_size': 0,
        'file_size_formatted': '',
        'title': req.title or "Processing...",
        'artist': req.artist or "",
        'quality': req.quality
    }
    
    executor.submit(run_conversion_job, job_id, req)
    return {"success": True, "job_id": job_id}

@app.get("/api/progress/{job_id}")
def get_job_progress(job_id: str):
    """Check status and progress of a conversion job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return {
        "id": job['id'],
        "status": job['status'],
        "progress": job['progress'],
        "status_text": job['status_text'],
        "error": job.get('error'),
        "filename": job.get('filename'),
        "file_size_formatted": job.get('file_size_formatted'),
        "title": job.get('title'),
        "artist": job.get('artist'),
        "duration_formatted": job.get('duration_formatted'),
        "thumbnail": job.get('thumbnail'),
        "quality": job.get('quality')
    }

@app.api_route("/api/stream/{job_id}", methods=["GET", "HEAD"])
def stream_audio(job_id: str):
    """Stream converted MP3 directly for in-browser playback."""
    if job_id not in jobs or jobs[job_id]['status'] != 'completed':
        raise HTTPException(status_code=404, detail="Audio file not ready or not found")
    
    file_path = jobs[job_id].get('file_path')
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File on disk has been purged")
    
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"}
    )

@app.api_route("/api/download/{job_id}", methods=["GET", "HEAD"])
def download_audio(job_id: str):
    """
    Download converted MP3 file.
    Ephemeral policy: The file is instantly deleted from disk as soon as streaming finishes!
    """
    if job_id not in jobs or jobs[job_id]['status'] != 'completed':
        raise HTTPException(status_code=404, detail="File not ready or expired")
    
    job = jobs[job_id]
    file_path = job.get('file_path')
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File already downloaded and purged from server memory.")
    
    filename = job.get('filename') or "audio.mp3"
    from urllib.parse import quote
    encoded_filename = quote(filename)
    
    # BackgroundTask executes automatically the moment the response transfer finishes
    cleanup_task = BackgroundTask(purge_file, file_path, job_id)
    
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"
        },
        background=cleanup_task
    )

@app.get("/api/history")
def get_conversion_history():
    """Retrieve list of recent conversion jobs."""
    completed = [
        {
            "id": j['id'],
            "title": j.get('title'),
            "artist": j.get('artist'),
            "duration_formatted": j.get('duration_formatted'),
            "thumbnail": j.get('thumbnail'),
            "file_size_formatted": j.get('file_size_formatted'),
            "quality": j.get('quality'),
            "created_at": j.get('created_at'),
            "filename": j.get('filename'),
            "is_available": bool(j.get('file_path') and os.path.exists(j.get('file_path')))
        }
        for j in jobs.values()
        if j['status'] == 'completed'
    ]
    completed.sort(key=lambda x: x.get('created_at', 0), reverse=True)
    return {"success": True, "history": completed[:15]}

@app.delete("/api/history/{job_id}")
def delete_conversion(job_id: str):
    """Explicitly purge a file and its job."""
    if job_id in jobs:
        file_path = jobs[job_id].get('file_path')
        purge_file(file_path, job_id)
        del jobs[job_id]
        return {"success": True, "message": "Conversion deleted and purged"}
    raise HTTPException(status_code=404, detail="Job not found")

@app.get("/api/diag")
def diagnostic_health_check(v: str = "JGwWNGJdvx8"):
    """Live diagnostic check for external cluster health and network connectivity."""
    report = {
        "status": "ok",
        "video_id": v,
        "time": time.time(),
        "tests": {}
    }
    
    # 1. Test TubeAPI Cluster
    try:
        api_key = get_tubeapi_key()
        u = f"https://hidden-sun-3c87.holy-breeze-fec5.workers.dev/?e=i&v={v}&api_key={api_key}&_={int(time.time()*1000)}"
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://tubeapi.org/"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
            report["tests"]["tubeapi"] = {
                "status": "ok" if data.get("status") in ["ok", "processing"] else "fail",
                "cluster_status": data.get("status"),
                "has_link": bool(data.get("link")),
                "title": data.get("title")
            }
    except Exception as e:
        report["tests"]["tubeapi"] = {"status": "error", "error": str(e)}

    # 2. Test Etacloud Cluster Auth
    try:
        y_key = get_y2mate_key()
        auth_url = f"https://eta.etacloud.org/api/v1/auth?api_key={y_key}&_={int(time.time()*1000)}"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://y2mate.gs/", "Origin": "https://y2mate.gs"}
        req = urllib.request.Request(auth_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
            report["tests"]["etacloud_auth"] = {
                "status": "ok" if data.get("key") else "fail",
                "geo": data.get("geo"),
                "has_key": bool(data.get("key"))
            }
    except Exception as e:
        report["tests"]["etacloud_auth"] = {"status": "error", "error": str(e)}

    # 3. System binaries
    report["system"] = {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "nodejs": shutil.which("node") is not None,
        "temp_writable": os.access(str(TEMP_DIR), os.W_OK)
    }
    
    return report

# Ephemeral Garbage Collector: Purges any files in temp older than 5 minutes
def ephemeral_cleanup_worker():
    now = time.time()
    for f in TEMP_DIR.glob("*.mp3"):
        try:
            if now - f.stat().st_mtime > 300: # 5 minutes old
                f.unlink(missing_ok=True)
                print(f"Expired file removed: {f.name}")
        except Exception:
            pass

@app.on_event("startup")
async def startup_event():
    ephemeral_cleanup_worker()
    # Schedule background cleanup loop every 60 seconds
    async def periodic_sweeper():
        while True:
            await asyncio.sleep(60)
            ephemeral_cleanup_worker()
    asyncio.create_task(periodic_sweeper())

# Serve static frontend files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting YouTube to MP3 Converter on http://0.0.0.0:{port} ...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
