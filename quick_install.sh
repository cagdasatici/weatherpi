#!/bin/bash

# WeatherPi v2.0.0 Enterprise Edition - Quick Install & Verification Script
# This script downloads and deploys the enterprise WeatherPi system

set -euo pipefail

echo "🚀 WeatherPi v2.0.0 Enterprise Edition - Quick Install"
echo "=================================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This appears to not be a Raspberry Pi"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create workspace
INSTALL_DIR="$HOME/weatherpi-enterprise"
echo "📁 Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Download the latest release
echo "⬇️  Downloading WeatherPi v2.0.0 Enterprise Edition..."
if command -v git &> /dev/null; then
    git clone https://github.com/cagdasatici/weatherpi.git .
    git checkout v2.0.0-enterprise
else
    curl -L https://github.com/cagdasatici/weatherpi/archive/v2.0.0-enterprise.tar.gz | tar xz --strip-components=1
fi

# Make deployment script executable
chmod +x deploy_enhanced.sh

echo "✅ Download complete!"
echo ""
echo "🛠️  Next Steps:"
echo "1. Review the configuration in README_ENHANCED.md"
echo "2. Set up your OpenWeather API key:"
echo "   export OPENWEATHER_API_KEY='your_api_key_here'"
echo "3. Run the deployment script:"
echo "   ./deploy_enhanced.sh"
echo ""
echo "📊 After deployment, access monitoring at:"
echo "   http://$(hostname -I | awk '{print $1}'):5001"
echo ""
echo "📚 Full documentation: README_ENHANCED.md"
echo "🧪 Run tests with: python -m pytest test_working_proxy.py -v"
echo ""
echo "🎉 Ready to deploy! Run ./deploy_enhanced.sh when ready."