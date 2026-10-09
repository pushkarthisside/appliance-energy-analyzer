# DEPLOYMENT.md — Operational runbook

How to create, deploy, operate and recover NILMTrace on AWS. The design behind these steps is in [ARCHITECTURE.md](ARCHITECTURE.md) §3, §12, §15, §16.

**Placeholders** — replace everywhere:

| Placeholder | Meaning |
|---|---|
| `<bucket>` | S3 bucket name, e.g. `nilmtrace-<random-suffix>` (globally unique) |
| `<account-id>` | 12-digit AWS account ID |
| `<topic-arn>` | SNS topic ARN, e.g. `arn:aws:sns:ap-south-1:<account-id>:nilmtrace-alerts` |
| `<demo-email>` | Inbox that receives alerts during the demo |
| `<elastic-ip>` | Public IP attached to the instance |
| `<your-ip>` | Your current public IP, for SSH (`/32`) |
| `<repo-url>` | GitHub HTTPS clone URL |
| `<key.pem>` | EC2 key pair file (never committed) |

Region for everything: **ap-south-1 (Mumbai)**.

---

## 1. Account prerequisites (T-004)

1. Enable MFA on the root user. Stop using root after this step.
2. Create an IAM user for yourself with console access and `AdministratorAccess`; enable MFA; use it from now on.
3. Billing → Budgets → create a **monthly cost budget** with an email alert at a low threshold you choose. Do this before creating any resource.
4. Install the AWS CLI v2 locally and run `aws configure` with your admin user's keys, default region `ap-south-1`.

Cost note: EC2 instances, EBS volumes and public IPv4 addresses (including Elastic IPs) are billed hourly. Check current prices on the AWS pricing pages before launch, and stop the instance when you are not working (§12).

---

## 2. S3 bucket (T-301)

```bash
aws s3api create-bucket --bucket <bucket> --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1

aws s3api put-public-access-block --bucket <bucket> \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-encryption --bucket <bucket> \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-bucket-lifecycle-configuration --bucket <bucket> \
  --lifecycle-configuration '{"Rules":[{"ID":"expire-uploads","Status":"Enabled","Filter":{"Prefix":"uploads/"},"Expiration":{"Days":7}}]}'
```

Check: `aws s3api get-public-access-block --bucket <bucket>` shows all four `true`.

---

## 3. IAM

### 3.1 EC2 instance role (T-302)

Create role `nilmtrace-ec2` (trusted entity: EC2) with this inline policy, then an instance profile of the same name (the console creates it automatically when you create an EC2 role).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ListBucket", "Effect": "Allow", "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<bucket>" },
    { "Sid": "ReadArtifacts", "Effect": "Allow", "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::<bucket>/*" },
    { "Sid": "WriteUploads", "Effect": "Allow", "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::<bucket>/uploads/*" },
    { "Sid": "PublishAlerts", "Effect": "Allow", "Action": "sns:Publish",
      "Resource": "<topic-arn>" }
  ]
}
```

### 3.2 IAM user for Teammate A (T-303)

User `nilmtrace-ml`, programmatic access only, inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::<bucket>" },
    { "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": [
        "arn:aws:s3:::<bucket>/models/*",
        "arn:aws:s3:::<bucket>/samples/*",
        "arn:aws:s3:::<bucket>/evaluation/*",
        "arn:aws:s3:::<bucket>/config/*"
      ] }
  ]
}
```

Send the access key to Teammate A over a private channel, never in git or a group chat. A runs `aws configure --profile nilmtrace-ml`. Delete the key after the hackathon.

---

## 4. SNS (T-304)

```bash
aws sns create-topic --name nilmtrace-alerts --region ap-south-1
aws sns subscribe --topic-arn <topic-arn> --protocol email --notification-endpoint <demo-email>
```

Open the confirmation email and click the link. Then test:

```bash
aws sns publish --topic-arn <topic-arn> --subject "NILMTrace test" --message "Test alert"
```

Check the spam folder; mark the sender as not spam. Subscribe and confirm **at least a day before the demo**.

---

## 5. EC2 instance (T-305)

Launch with these settings:

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Type | `t3.medium` (U-08: confirm with TS-PERF) |
| Key pair | New key pair `<key.pem>`, stored outside the repo |
| Storage | 20 GiB gp3 |
| IAM instance profile | `nilmtrace-ec2` |
| Security group `nilmtrace-sg` | Inbound TCP 80 from `0.0.0.0/0`; TCP 22 from `<your-ip>/32`. No other inbound rules |

Then allocate an **Elastic IP** and associate it with the instance.

Base setup over SSH:

```bash
ssh -i <key.pem> ubuntu@<elastic-ip>

sudo apt-get update && sudo apt-get install -y python3.12-venv git unzip
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
python3.12 --version && node --version     # expect 3.12.x and v22.x

sudo mkdir -p /srv/nilmtrace /var/lib/nilmtrace/cache
sudo chown -R ubuntu:ubuntu /srv/nilmtrace /var/lib/nilmtrace
git clone <repo-url> /srv/nilmtrace
```

Check the role works (no keys configured on the instance):

```bash
sudo snap install aws-cli --classic
aws s3 ls s3://<bucket>/
```

---

## 6. Application install (T-306)

### 6.1 Environment file

`/etc/nilmtrace.env` (root-owned, mode 644; contains no secrets). Variables are defined in ARCHITECTURE §15.

```bash
sudo tee /etc/nilmtrace.env >/dev/null <<'EOF'
NILM_BUCKET=<bucket>
NILM_TOPIC_ARN=<topic-arn>
NILM_ALERTS_ENABLED=true
NILM_SYNC_ON_STARTUP=true
NILM_CACHE_DIR=/var/lib/nilmtrace/cache
NILM_FRONTEND_DIST=/srv/nilmtrace/frontend/dist
NILM_MOCK=false
NILM_DEV_CORS=false
AWS_DEFAULT_REGION=ap-south-1
EOF
```

For the first deploy (checkpoint C1, before models exist) set `NILM_MOCK=true` and `NILM_SYNC_ON_STARTUP=false`.

### 6.2 systemd unit

```bash
sudo tee /etc/systemd/system/nilmtrace.service >/dev/null <<'EOF'
[Unit]
Description=NILMTrace API and frontend
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/srv/nilmtrace/backend
EnvironmentFile=/etc/nilmtrace.env
ExecStart=/srv/nilmtrace/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 80 --workers 1
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable nilmtrace
```

`AmbientCapabilities` lets the non-root `ubuntu` user bind port 80.

---

## 7. First deploy (C1, mock mode)

```bash
cd /srv/nilmtrace/backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
sudo systemctl start nilmtrace
curl -fsS http://127.0.0.1/api/health
```

From a phone on mobile data: open `http://<elastic-ip>/` and `http://<elastic-ip>/api/health`.

---

## 8. Redeploy (T-508; scripted in T-605)

`deploy/deploy.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /srv/nilmtrace
git pull --ff-only
backend/.venv/bin/pip install -q -r backend/requirements.txt
(cd frontend && npm ci --silent && npm run build)
sudo systemctl restart nilmtrace
for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1/api/health | grep -q '"samples_ready":true'; then
    curl -fsS http://127.0.0.1/api/health; echo; exit 0
  fi
  sleep 5
done
echo "Service not ready after 5 minutes"; sudo journalctl -u nilmtrace -n 50 --no-pager; exit 1
```

**New models or artifacts only** (no code change): Teammate A syncs to S3 (TASKS T-114), then on the instance `sudo systemctl restart nilmtrace` (startup re-syncs from S3).

Before switching off mock mode for good, edit `/etc/nilmtrace.env` (`NILM_MOCK=false`, `NILM_SYNC_ON_STARTUP=true`) and restart.

---

## 9. Logs and troubleshooting

```bash
sudo systemctl status nilmtrace
sudo journalctl -u nilmtrace -f              # follow
sudo journalctl -u nilmtrace -n 200 --no-pager
curl -s http://127.0.0.1/api/health
free -m
```

| Symptom | Likely cause | Fix |
|---|---|---|
| Browser cannot reach the IP | Security group, instance stopped, Elastic IP not associated | Check port 80 rule; start instance; re-associate EIP |
| `Permission denied` binding port 80 | `AmbientCapabilities` missing | Check the unit file; `daemon-reload`; restart |
| `health.s3_synced: false` | Role not attached or wrong bucket name | Check instance profile; `aws s3 ls s3://<bucket>/` on the instance |
| An appliance in `appliances_failed` | Missing/corrupt ONNX or registry path typo | Check `models/` in S3 vs `registry.json`; re-sync; restart |
| `samples_ready` stays false | Exception while precomputing samples | `journalctl`; usually a missing sample file or schema error |
| 404 on page refresh | Frontend dist path wrong | Check `NILM_FRONTEND_DIST`; rebuild frontend |
| No alert email | Subscription unconfirmed, spam folder, `NILM_TOPIC_ARN` empty | Confirm; check spam; check env; `aws sns publish` test |
| Instance slow or killed | Memory | `free -m`; consider a larger instance (U-08) |

---

## 10. Verification checklist (AWS-01…06)

- [ ] Budget alert active (AWS-01)
- [ ] Bucket: public access blocked, SSE on, lifecycle on `uploads/` (AWS-02)
- [ ] Instance has `nilmtrace-ec2` role; `~/.aws/credentials` does **not** exist on the instance (AWS-03)
- [ ] SNS subscription status "Confirmed" (AWS-04)
- [ ] Security group has only ports 80 and 22, SSH limited to `/32` (AWS-05)
- [ ] `nilmtrace-ml` user can write `models/` but not `uploads/` (AWS-06)

---

## 11. Demo day

### 11.1 Pre-demo checklist (T-706; keep a copy in `deploy/PREDEMO.md`)

One hour before:

- [ ] Instance running; `http://<elastic-ip>/api/health` shows `status: ok`, all expected appliances loaded, `samples_ready: true`, `s3_synced: true`
- [ ] Both samples load from the presenting laptop on the venue network
- [ ] `problem_week` sends an email to the demo inbox (check arrival time)
- [ ] Phone logged into the demo inbox; alert screenshot saved on the phone
- [ ] Backup video on the laptop (offline copy) and on a second device
- [ ] Laptop fallback ready (§11.2), already tested that morning
- [ ] Browser zoom set so every screen fits 1280×720; notifications off
- [ ] Rehearsed answers to the judge questions (DECISIONS.md §1)

### 11.2 Laptop fallback

Prepare beforehand on the presenting laptop:

```bash
git clone <repo-url> nilmtrace && cd nilmtrace
aws s3 sync s3://<bucket>/ fallback-cache/ --exclude "uploads/*"   # needs credentials with read access
(cd frontend && npm ci && npm run build)
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Run (works without internet once prepared):

```bash
cd backend
NILM_CACHE_DIR=../fallback-cache NILM_SYNC_ON_STARTUP=false NILM_ALERTS_ENABLED=false \
NILM_FRONTEND_DIST=../frontend/dist .venv/bin/uvicorn app.main:app --port 8000
```

Open `http://localhost:8000`. Email alerts are off; show the screenshot. Say plainly that you are running locally.

### 11.3 Rollback

- **Code:** tag every good deploy (`git tag demo-ready-N && git push --tags`). To roll back on the instance: `cd /srv/nilmtrace && git checkout demo-ready-N && ./deploy/deploy.sh`. Return to `main` afterwards.
- **Model:** point the registry entry back to the previous `v{n}`, sync, restart (ARCH §9.5).
- **Total failure:** laptop fallback; if that fails too, the backup video.

---

## 12. Cost control and teardown

- Stop the instance when not working: `aws ec2 stop-instances --instance-ids <id>`. The Elastic IP stays associated (it is still billed).
- After judging: terminate the instance, release the Elastic IP, delete the SNS topic, empty and delete the bucket, delete `nilmtrace-ml` keys and user, delete the role. Keep the budget alert until the next bill arrives.
