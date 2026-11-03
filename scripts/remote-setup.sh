#!/usr/bin/env bash
# Runs ON the EC2 instance (as ec2-user). Sets up backend venv, frontend build, systemd, nginx.
# Mock mode initially (Bedrock still throttled). Pepper fetched from SSM at service start.
set -xe
APP=/opt/careerlift
cd "$APP"

# ---------- backend venv ----------
python3.12 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install --upgrade pip -q
"$APP/.venv/bin/pip" install -q fastapi uvicorn pydantic boto3 strands-agents

# ---------- frontend build ----------
cd "$APP/frontend"
npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
npm run build
sudo mkdir -p /var/www/careerlift
sudo cp -r dist/* /var/www/careerlift/
cd "$APP"

# ---------- env file for the API (pepper fetched from SSM at start by the unit) ----------
sudo tee /etc/careerlift.env >/dev/null <<EOF
CAREERLIFT_MODEL_MODE=mock
AWS_REGION=us-east-1
SHIP_MODEL=us.amazon.nova-2-lite-v1:0
CAREERLIFT_DB=/data/careerlift.db
CAREERLIFT_SESSIONS=/data/sessions
EOF
sudo chmod 600 /etc/careerlift.env

# start-wrapper: pulls the pepper from SSM (SecureString) into the env, then execs uvicorn
sudo tee /opt/careerlift/start-api.sh >/dev/null <<'EOF'
#!/bin/bash
set -e
set -a; source /etc/careerlift.env; set +a
# pepper from SSM SecureString via the instance role; never logged
export CAREERLIFT_AUTH_PEPPER="$(/usr/bin/aws ssm get-parameter --name /careerlift/auth_pepper --with-decryption --region us-east-1 --query Parameter.Value --output text)"
exec /opt/careerlift/.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1
EOF
sudo chmod 755 /opt/careerlift/start-api.sh

# aws cli on the box (needed by start-api.sh) — AL2023 has it preinstalled at /usr/bin/aws; verify
which aws || sudo dnf install -y awscli

# ---------- systemd unit ----------
sudo tee /etc/systemd/system/careerlift-api.service >/dev/null <<EOF
[Unit]
Description=CareerLift AI FastAPI
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/careerlift
ExecStart=/opt/careerlift/start-api.sh
Restart=on-failure
RestartSec=3
StandardOutput=append:/var/log/careerlift-api.log
StandardError=append:/var/log/careerlift-api.log

[Install]
WantedBy=multi-user.target
EOF
sudo touch /var/log/careerlift-api.log && sudo chown ec2-user:ec2-user /var/log/careerlift-api.log
sudo systemctl daemon-reload
sudo systemctl enable --now careerlift-api
sleep 4

# ---------- nginx (serve SPA + proxy /api) ----------
sudo tee /etc/nginx/conf.d/careerlift.conf >/dev/null <<'EOF'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/careerlift;
    index index.html;
    location /api/ { proxy_pass http://127.0.0.1:8000/; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; }
    location / { try_files $uri $uri/ /index.html; }
}
EOF
# remove the default server block if present (avoid clash)
sudo sed -i 's/^\(\s*listen\s*80\s*default_server;\)/# \1/' /etc/nginx/nginx.conf || true
sudo nginx -t
sudo systemctl restart nginx

echo "REMOTE_SETUP_DONE"
echo "--- health via loopback ---"
sleep 2
curl -s http://127.0.0.1:8000/health || echo "API not yet responding"
echo
curl -s http://127.0.0.1/api/health || echo "nginx proxy not yet responding"
