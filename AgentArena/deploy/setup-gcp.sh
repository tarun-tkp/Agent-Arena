#!/usr/bin/env bash
# One-time GCP setup for Agent Arena Cloud Run Job
set -euo pipefail

PROJECT_ID="${1:-}"
REGION="${2:-asia-southeast1}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: ./deploy/setup-gcp.sh PROJECT_ID [REGION]"
  exit 1
fi

gcloud config set project "$PROJECT_ID"

# APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com

# Artifact Registry
gcloud artifacts repositories describe agent-arena \
  --location="$REGION" 2>/dev/null || \
gcloud artifacts repositories create agent-arena \
  --repository-format=docker \
  --location="$REGION" \
  --description="Agent Arena bot images"

# Service account for the job
SA="agent-arena-runner@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$SA" 2>/dev/null || \
gcloud iam service-accounts create agent-arena-runner \
  --display-name="Agent Arena Cloud Run Job"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/secretmanager.secretAccessor" --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/logging.logWriter" --quiet

echo ""
echo "Next steps:"
echo "  1. Create secrets:"
echo "     echo -n 'KEY' | gcloud secrets create gemini-api-key --data-file=-"
echo "     echo -n 'JWT' | gcloud secrets create arena-id-token --data-file=-"
echo "     echo -n 'KEY' | gcloud secrets create traceloop-api-key --data-file=-"
echo "  2. Deploy: gcloud builds submit --config cloudbuild.yaml"
echo "  3. Run:    gcloud run jobs execute agent-arena-amadeus --region=$REGION"
