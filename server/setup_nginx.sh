#!/usr/bin/env bash
set -euo pipefail

# Minimal helper to configure nginx and (optionally) obtain Let's Encrypt certs
# Intended to run on Raspberry Pi (Debian/Ubuntu). Review before running.

SITE_CONF=server/nginx/weatherpi.conf
DEST_CONF=/etc/nginx/sites-available/weatherpi
WEBROOT=/var/www/letsencrypt

if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root (sudo)." >&2
  exit 1
fi

read -p "Enter your domain name or public IP (for certs use a domain): " DOMAIN
if [ -z "$DOMAIN" ]; then
  echo "Domain is required." >&2
  exit 1
fi

echo "Installing nginx and certbot..."
apt update
apt install -y nginx certbot python3-certbot-nginx

echo "Creating webroot for ACME..."
mkdir -p $WEBROOT
chown www-data:www-data $WEBROOT

echo "Copying nginx config (editing server_name and paths)..."
sed "s/your.domain.example/$DOMAIN/g" $SITE_CONF > $DEST_CONF

ln -sf $DEST_CONF /etc/nginx/sites-enabled/weatherpi

echo "Testing nginx configuration..."
nginx -t

echo "Reloading nginx..."
systemctl reload nginx

read -p "Attempt to obtain Let's Encrypt certificate for $DOMAIN now? (y/N) " DOLETS
if [[ "$DOLETS" =~ ^[Yy]$ ]]; then
  certbot --nginx -d $DOMAIN
  echo "Obtained certificate. Reloading nginx..."
  systemctl reload nginx
else
  echo "Skipping Let's Encrypt. Creating self-signed certificate for local use..."
  SSL_DIR=/etc/ssl/weatherpi
  mkdir -p $SSL_DIR
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout $SSL_DIR/privkey.pem -out $SSL_DIR/fullchain.pem \
    -subj "/CN=$DOMAIN"
  echo "Self-signed cert created at $SSL_DIR. You need to update nginx config to point to this cert." 
fi

echo "Done. Please review /etc/nginx/sites-enabled/weatherpi and adjust paths if needed."
