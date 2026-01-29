#!/bin/sh
set -e

echo "=== Starting Video Downloader Service ==="
echo "PORT: $PORT"
echo "Current directory: $(pwd)"
echo "Files in directory:"
ls -la

echo "=== Testing Python imports ==="
python3 -c "import flask; import yt_dlp; print('All imports OK')"

echo "=== Starting Gunicorn ==="
exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --log-level debug app:app
