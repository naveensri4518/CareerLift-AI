#!/usr/bin/env bash
# Set up real trusted HTTPS via Let's Encrypt using a nip.io hostname (no domain purchase needed).
# nip.io resolves <ip-with-dashes>.nip.io -> the IP, so HTTP-01 validation works.
set -xe
IP=3.235.53.227
HOST="${IP//./-}.nip.io"   # 3-235-53-227.nip.io

sudo dnf install -y certbot python3-certbot-nginx

# certbot --nginx will add the 443 server block + cert and set up HTTP->HTTPS redirect.
sudo certbot --nginx -d "$HOST" --non-interactive --agree-tos -m admin@"$HOST" --redirect

# Ensure our SPA/proxy config applies to the HTTPS server too: certbot edits the existing server block
# (server_name _) -> it will have switched server_name to the host. Make sure /api proxy + SPA fallback
# are present in the TLS block. Re-assert a clean config keyed to the host:
sudo tee /etc/nginx/conf.d/careerlift.conf >/dev/null <<EOF
server {
    listen 80;
    server_name $HOST;
    return 301 https://\$host\$request_uri;
}
server {
    listen 443 ssl;
    server_name $HOST;
    ssl_certificate /etc/letsencrypt/live/$HOST/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$HOST/privkey.pem;
    root /var/www/careerlift;
    index index.html;
    location /api/ { proxy_pass http://127.0.0.1:8000/; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; }
    location / { try_files \$uri \$uri/ /index.html; }
}
EOF
# remove certbot's duplicate default (it may have created one); keep our file authoritative
sudo rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
sudo nginx -t
sudo systemctl restart nginx
echo "HTTPS_HOST=$HOST"
echo "=== local https check ==="
curl -sk https://$HOST/api/health && echo
