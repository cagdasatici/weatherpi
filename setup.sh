#!/bin/bash

# Install required packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-kivy

# Install Python dependencies
pip3 install -r requirements.txt

# Set up autostart service
sudo cp weatherkiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable weatherkiosk
sudo systemctl start weatherkiosk

# Add API key to environment
echo "export OWM_API_KEY=your_api_key_here" >> ~/.bashrc
echo "export OWM_API_KEY=your_api_key_here" >> ~/.profile