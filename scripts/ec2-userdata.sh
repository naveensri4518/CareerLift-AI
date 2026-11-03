#!/bin/bash
# CareerLift EC2 bootstrap (cloud-init user-data). OS-level setup only; app is deployed via scp afterward.
# Runs as root on first boot. Idempotent-ish.
set -xe
exec > /var/log/careerlift-bootstrap.log 2>&1

dnf update -y
dnf install -y docker nginx python3.12 python3.12-pip git tar gzip

# Node.js 20 (for the frontend build on-box)
curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
dnf install -y nodejs

# Docker on
systemctl enable --now docker
usermod -aG docker ec2-user

# App user dirs
mkdir -p /opt/careerlift
chown ec2-user:ec2-user /opt/careerlift

# --- mount the data volume at /data (device may be /dev/nvme1n1 or /dev/xvdf) ---
mkdir -p /data
for i in $(seq 1 30); do
  DEV=""
  for cand in /dev/nvme1n1 /dev/xvdf /dev/sdf; do [ -b "$cand" ] && DEV="$cand" && break; done
  if [ -n "$DEV" ]; then
    # make a filesystem only if the device has none
    if ! blkid "$DEV"; then mkfs -t xfs "$DEV"; fi
    UUID=$(blkid -s UUID -o value "$DEV")
    grep -q "$UUID" /etc/fstab || echo "UUID=$UUID /data xfs defaults,nofail 0 2" >> /etc/fstab
    mount -a || true
    break
  fi
  sleep 5
done
mkdir -p /data/sessions
chown -R ec2-user:ec2-user /data

# nginx on (config pushed during deploy)
systemctl enable nginx

echo "BOOTSTRAP_COMPLETE" > /opt/careerlift/.bootstrap-done
