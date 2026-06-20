# GCP Deployment

Deploy the Agent Arena bot as a **Cloud Run Job** — ideal for batch agent runs that execute and exit (not a long-lived web server).

## Why Cloud Run Job?

| Requirement | Cloud Run Job |
|-------------|---------------|
| Run agent to completion | ✅ Task runs `python agent.py` and exits |
| Secrets (API keys, JWT) | ✅ Secret Manager integration |
| Scale parallel runs | ✅ Execute multiple job instances |
| Same region as Arena MCP | ✅ Deploy to `asia-southeast1` |
| Evaluation artifacts | ✅ Mount volume or upload to GCS after run |

## Prerequisites

- Google Cloud project with billing enabled
- `gcloud` CLI authenticated
- Docker (for local builds) or Cloud Build

## One-Time Setup

```bash
chmod +x deploy/setup-gcp.sh
./deploy/setup-gcp.sh YOUR_PROJECT_ID asia-southeast1
```

This enables APIs, creates Artifact Registry, and sets up the `agent-arena-runner` service account.

## Create Secrets

```bash
echo -n "your-gemini-key" | gcloud secrets create gemini-api-key --data-file=-
echo -n "your-firebase-jwt" | gcloud secrets create arena-id-token --data-file=-
echo -n "your-traceloop-key" | gcloud secrets create traceloop-api-key --data-file=-
```

**Note:** `arena-id-token` expires in ~1 hour. For production, refresh via CI/CD before each scheduled run, or use a token refresh mechanism.

## Deploy via Cloud Build

```bash
gcloud builds submit --config cloudbuild.yaml
```

This builds the Docker image, pushes to Artifact Registry, and deploys the Cloud Run Job.

## Execute a Run

```bash
gcloud run jobs execute agent-arena-amadeus --region=asia-southeast1
```

View logs:

```bash
gcloud run jobs executions list --job=agent-arena-amadeus --region=asia-southeast1
gcloud logging read "resource.type=cloud_run_job" --limit=50
```

## Scale — Parallel Runs

Each execution gets a unique `run_id`. Launch multiple in parallel:

```bash
for i in 1 2 3; do
  gcloud run jobs execute agent-arena-amadeus --region=asia-southeast1 &
done
wait
```

Or increase `parallelism` in `deploy/cloud-run-job.yaml`.

## Configuration via Environment

Set at deploy time (see `cloudbuild.yaml`):

| Env var | Default | Description |
|---------|---------|-------------|
| `AGENT_NAME` | `AgentArena-Amadeus-v1` | Leaderboard name |
| `MAX_TASKS` | `20` | Tasks per execution |
| `MODEL` | `gemini-2.0-flash` | Gemini model |
| `TEMPERATURE` | `0.1` | Generation temperature |
| `EVAL_OUTPUT_DIR` | `/app/runs` | Report output path |

Update a deployed job:

```bash
gcloud run jobs update agent-arena-amadeus \
  --region=asia-southeast1 \
  --set-env-vars=MAX_TASKS=30,MODEL=gemini-2.5-pro-preview
```

## Persist Evaluation Reports

Option A — **Cloud Storage upload** (add to `agent.py` post-run or use a sidecar script):

```bash
gsutil cp runs/*.json gs://YOUR_BUCKET/evaluations/
```

Option B — **Mount GCS FUSE** on Cloud Run (requires additional setup).

Option C — **Log the JSON** — Cloud Logging captures stdout; query with Log Explorer.

## Scheduled Runs

```bash
gcloud scheduler jobs create http arena-nightly \
  --location=asia-southeast1 \
  --schedule="0 2 * * *" \
  --uri="https://asia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT/jobs/agent-arena-amadeus:run" \
  --http-method=POST \
  --oauth-service-account-email=agent-arena-runner@YOUR_PROJECT.iam.gserviceaccount.com
```

Refresh `arena-id-token` secret before scheduled runs if JWT has expired.

## Local Docker Test

```bash
docker build -t agent-arena-amadeus .
docker run --env-file .env -v $(pwd)/runs:/app/runs agent-arena-amadeus
```

## Cost Considerations

- Cloud Run Job: billed per vCPU-second and memory during execution
- Gemini API: billed per token (model-dependent)
- Traceloop: free tier available
- Typical run (20 tasks): ~10–30 minutes on 2 vCPU / 2 GiB

## Security Checklist

- [ ] Secrets in Secret Manager — never in Docker image or git
- [ ] Service account has minimal roles (`secretAccessor`, `logWriter`)
- [ ] `.env` in `.gitignore`
- [ ] Rotate Firebase JWT before each production run
