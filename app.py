from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import shutil

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "video-download"})

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality', '720')
        
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        
        # Quality mapping
        quality_format = {
            "360": "best[height<=360]",
            "480": "best[height<=480]",
            "720": "best[height<=720]",
            "1080": "best[height<=1080]",
            "best": "best"
        }.get(quality, "best[height<=720]")
        
        # Download options
        ydl_opts = {
            'format': quality_format,
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'quiet': True,
        }
        
        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        
        video_id = info['id']
        ext = info.get('ext', 'mp4')
        downloaded_file = os.path.join(temp_dir, f"{video_id}.{ext}")
        
        # Find the file
        if not os.path.exists(downloaded_file):
            for f in os.listdir(temp_dir):
                if video_id in f:
                    downloaded_file = os.path.join(temp_dir, f)
                    ext = f.split('.')[-1]
                    break
        
        # Move to persistent storage
        persistent_dir = "/tmp/videos"
        os.makedirs(persistent_dir, exist_ok=True)
        final_path = os.path.join(persistent_dir, f"{video_id}.{ext}")
        shutil.move(downloaded_file, final_path)
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Detect platform
        url_lower = url.lower()
        platform = 'unknown'
        if 'youtube' in url_lower or 'youtu.be' in url_lower:
            platform = 'youtube'
        elif 'tiktok' in url_lower:
            platform = 'tiktok'
        elif 'instagram' in url_lower:
            platform = 'instagram'
        elif 'twitter' in url_lower or 'x.com' in url_lower:
            platform = 'twitter'
        elif 'facebook' in url_lower:
            platform = 'facebook'
        
        return jsonify({
            "video_url": f"/videos/{video_id}.{ext}",
            "title": info.get('title'),
            "duration": info.get('duration'),
            "thumbnail": info.get('thumbnail'),
            "platform": platform,
            "width": info.get('width'),
            "height": info.get('height'),
            "ext": ext
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/videos/<filename>')
def serve_video(filename):
    file_path = f"/tmp/videos/{filename}"
    if not os.path.exists(file_path):
        return jsonify({"error": "Video not found"}), 404
    return send_file(file_path, mimetype="video/mp4")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
