#!/usr/bin/env python3
"""Simple HTTP server for weather kiosk HTML interface"""

import http.server
import socketserver
import os
import logging
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class WeatherHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def log_message(self, format, *args):
        # Use our logging system instead of default
        logging.info(f"{self.client_address[0]} - {format % args}")

def start_server(port=8000):
    """Start the web server"""
    try:
        with socketserver.TCPServer(("", port), WeatherHandler) as httpd:
            logging.info(f"Weather Kiosk server starting on port {port}")
            logging.info(f"Access at: http://localhost:{port}/weather.html")
            httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error(f"Server error: {e}")

if __name__ == "__main__":
    start_server()