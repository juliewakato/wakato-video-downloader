from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp
import os
import tempfile
import shutil
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Video Download Service", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for blocking yt-dlp operations
executor = ThreadPoolExecutor(max_workers=2)

class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = "720"

class DownloadResponse(BaseModel):
    video_url: str
    title: Optional[str] = None
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    platform: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format_id: Optional[str] = None
    ext: Optional[str] = None

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "video-download"}

@app.post("/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest):
    """Download video and return direct URL"""
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Configure yt-dlp options
        quality_format = {
            "360": "best[height<=360][ext=mp4]/best[height<=360]",
            "480": "best[height<=480][ext=mp4]/best[height<=480]",
            "720": "best[height<=720][ext=mp4]/best[height<=720]",
            "1080": "best[height<=1080][ext=mp4]/best[height<=1080]",
            "best": "best[ext=mp4]/best"
        }.get(request.quality, "best[height<=720][ext=mp4]/best[height<=720]")
        
        ydl_opts = {
            'format': quality_format,
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(request.url, download=True)
                return info
        
        info = await asyncio.get_event_loop().run_in_executor(executor, download)
        
        video_id = info['id']
        ext = info.get('ext', 'mp4')
        downloaded_file = os.path.join(temp_dir, f"{video_id}.{ext}")
        
        if not os.path.exists(downloaded_file):
            files = os.listdir(temp_dir)
            for f in files:
                if video_id in f:
                    downloaded_file = os.path.join(temp_dir, f)
                    ext = f.split('.')[-1]
                    break
        
        persistent_dir = "/tmp/videos"
        os.makedirs(persistent_dir, exist_ok=True)
        final_path = os.path.join(persistent_dir, f"{video_id}.{ext}")
        shutil.move(downloaded_file, final_path)
        
        platform = detect_platform(request.url)
        
        return DownloadResponse(
            video_url=f"/videos/{video_id}.{ext}",
            title=info.get('title'),
            duration=info.get('duration'),
            thumbnail=info.get('thumbnail'),
            platform=platform,
            width=info.get('width'),
            height=info.get('height'),
            format_id=info.get('format_id'),
            ext=ext
        )
        
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

@app.get("/videos/{filename}")
async def serve_video(filename: str):
    """Serve downloaded video file"""
    file_path = f"/tmp/videos/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(file_path, media_type="video/mp4")

@app.post("/extract-info")
async def extract_info(request: DownloadRequest):
    """Extract video info without downloading"""
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        def get_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(request.url, download=False)
        
        info = await asyncio.get_event_loop().run_in_executor(executor, get_info)
        
        formats = []
        if 'formats' in info:
            for f in info['formats']:
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    formats.append({
                        'format_id': f.get('format_id'),
                        'quality': f.get('quality_label') or f"{f.get('height', 'unknown')}p",
                        'ext': f.get('ext'),
                        'filesize': f.get('filesize'),
                        'has_audio': f.get('acodec') != 'none'
                    })
        
        return {
            'title': info.get('title'),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail'),
            'platform': detect_platform(request.url),
            'uploader': info.get('uploader'),
            'formats': formats[:10]
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Extraction failed: {str(e)}")

def detect_platform(url: str) -> str:
    """Detect platform from URL"""
    url = url.lower()
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'tiktok.com' in url:
        return 'tiktok'
    elif 'instagram.com' in url:
        return 'instagram'
    elif 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    elif 'facebook.com' in url or 'fb.watch' in url:
        return 'facebook'
    elif 'vimeo.com' in url:
        return 'vimeo'
    elif 'reddit.com' in url:
        return 'reddit'
    elif 'twitch.tv' in url:
        return 'twitch'
    elif 'linkedin.com' in url:
        return 'linkedin'
    else:
        return 'unknown'

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
