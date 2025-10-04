Local kiosk preview

To preview the kiosk locally (desktop), run a simple HTTP server from the repo root and open the preview page in your browser:

# from repo root
python3 -m http.server 8000 --directory .
# then open local_preview.html in a browser (it loads pages from http://localhost:8000)
