#!/bin/bash
#
# Deploy Daily Brief Agent to Google Cloud Run Jobs
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Docker installed (for local testing)
#
# Usage:
#   ./deploy.sh              # Full deployment
#   ./deploy.sh setup        # First-time setup only
#   ./deploy.sh build        # Build and push image only
#   ./deploy.sh secrets      # Update secrets only
#   ./deploy.sh schedule     # Update scheduler only
#   ./deploy.sh run          # Manually trigger the job
#

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-daily-brief-agent-recess}"
REGION="us-central1"
JOB_NAME="daily-brief-agent"
REPO_NAME="daily-brief"
IMAGE_NAME="daily-brief-agent"
SCHEDULE_TIME="0 16 * * 1-5"  # 4 PM MST, Monday-Friday (Cloud Scheduler uses UTC, adjust as needed)
SCHEDULE_TIMEZONE="America/Phoenix"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# First-time setup
setup() {
    log_info "Setting up GCP resources for Daily Brief Agent..."

    # Enable required APIs
    log_info "Enabling required GCP APIs..."
    gcloud services enable \
        run.googleapis.com \
        cloudbuild.googleapis.com \
        artifactregistry.googleapis.com \
        cloudscheduler.googleapis.com \
        secretmanager.googleapis.com \
        --project="$PROJECT_ID"

    # Create Artifact Registry repository
    log_info "Creating Artifact Registry repository..."
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Daily Brief Agent container images" \
        --project="$PROJECT_ID" 2>/dev/null || log_warn "Repository already exists"

    # Configure Docker auth
    log_info "Configuring Docker authentication..."
    gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

    log_info "Setup complete! Next steps:"
    echo "  1. Run: ./deploy.sh secrets"
    echo "  2. Run: ./deploy.sh build"
    echo "  3. Run: ./deploy.sh schedule"
}

# Create/update secrets in Secret Manager
setup_secrets() {
    log_info "Setting up secrets in Secret Manager..."

    # Load from .env file
    if [ ! -f ".env" ]; then
        log_error ".env file not found. Please create it first."
        exit 1
    fi

    # List of required secrets
    SECRETS=(
        "ANTHROPIC_API_KEY"
        "AIRTABLE_API_KEY"
        "AIRTABLE_BASE_ID"
        "AIRTABLE_TABLE_NAME"
        "ASANA_ACCESS_TOKEN"
        "ASANA_WORKSPACE_GID"
        "SLACK_BOT_TOKEN"
        "SLACK_CHANNEL_ID"
    )

    for secret_name in "${SECRETS[@]}"; do
        # Get value from .env
        secret_value=$(grep "^${secret_name}=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")

        if [ -z "$secret_value" ]; then
            log_warn "Secret $secret_name not found in .env, skipping..."
            continue
        fi

        # Check if secret exists
        if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
            log_info "Updating secret: $secret_name"
            echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
                --data-file=- \
                --project="$PROJECT_ID"
        else
            log_info "Creating secret: $secret_name"
            echo -n "$secret_value" | gcloud secrets create "$secret_name" \
                --data-file=- \
                --replication-policy="automatic" \
                --project="$PROJECT_ID"
        fi
    done

    # Grant Cloud Run access to secrets
    log_info "Granting Cloud Run service account access to secrets..."
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

    for secret_name in "${SECRETS[@]}"; do
        gcloud secrets add-iam-policy-binding "$secret_name" \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/secretmanager.secretAccessor" \
            --project="$PROJECT_ID" 2>/dev/null || true
    done

    log_info "Secrets configured successfully!"
}

# Build and push Docker image
build() {
    log_info "Building and pushing Docker image..."

    IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME"

    # Build image
    log_info "Building image: $IMAGE_URI:latest"
    docker build -t "$IMAGE_URI:latest" .

    # Push image
    log_info "Pushing image to Artifact Registry..."
    docker push "$IMAGE_URI:latest"

    log_info "Image pushed successfully: $IMAGE_URI:latest"
}

# Deploy Cloud Run Job
deploy_job() {
    log_info "Deploying Cloud Run Job..."

    IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:latest"

    # Load config from .env and create a temporary env vars file
    # (needed because TEAM_MEMBERS contains spaces in names)
    TEAM_MEMBERS_VAL=$(grep "^TEAM_MEMBERS=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    ASANA_AGE_LIMIT=$(grep "^ASANA_TASK_AGE_LIMIT_DAYS=" .env | cut -d'=' -f2- || echo "45")
    YOUR_NAME_VAL=$(grep "^YOUR_NAME=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'" || echo "")
    MONITORED_USERS_VAL=$(grep "^MONITORED_USERS=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'" || echo "Deuce Thevenow,Jack Shannon")

    # Create temporary YAML file for env vars (handles spaces in values)
    ENV_FILE=$(mktemp)
    cat > "$ENV_FILE" << EOF
TEAM_MEMBERS: "${TEAM_MEMBERS_VAL}"
ASANA_TASK_AGE_LIMIT_DAYS: "${ASANA_AGE_LIMIT}"
YOUR_NAME: "${YOUR_NAME_VAL}"
MONITORED_USERS: "${MONITORED_USERS_VAL}"
EOF

    log_info "Using env vars file with TEAM_MEMBERS (${#TEAM_MEMBERS_VAL} chars)"

    gcloud run jobs deploy "$JOB_NAME" \
        --image="$IMAGE_URI" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --memory="1Gi" \
        --cpu="1" \
        --task-timeout="15m" \
        --max-retries="1" \
        --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,AIRTABLE_API_KEY=AIRTABLE_API_KEY:latest,AIRTABLE_BASE_ID=AIRTABLE_BASE_ID:latest,AIRTABLE_TABLE_NAME=AIRTABLE_TABLE_NAME:latest,ASANA_ACCESS_TOKEN=ASANA_ACCESS_TOKEN:latest,ASANA_WORKSPACE_GID=ASANA_WORKSPACE_GID:latest,SLACK_BOT_TOKEN=SLACK_BOT_TOKEN:latest,SLACK_CHANNEL_ID=SLACK_CHANNEL_ID:latest" \
        --env-vars-file="$ENV_FILE"

    # Clean up temp file
    rm -f "$ENV_FILE"

    log_info "Cloud Run Job deployed successfully!"
}

# Set up Cloud Scheduler
setup_scheduler() {
    log_info "Setting up Cloud Scheduler..."

    # Check if scheduler job exists
    if gcloud scheduler jobs describe "$JOB_NAME-scheduler" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        log_info "Updating existing scheduler job..."
        gcloud scheduler jobs update http "$JOB_NAME-scheduler" \
            --location="$REGION" \
            --project="$PROJECT_ID" \
            --schedule="$SCHEDULE_TIME" \
            --time-zone="$SCHEDULE_TIMEZONE" \
            --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run" \
            --http-method="POST" \
            --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com"
    else
        log_info "Creating new scheduler job..."
        gcloud scheduler jobs create http "$JOB_NAME-scheduler" \
            --location="$REGION" \
            --project="$PROJECT_ID" \
            --schedule="$SCHEDULE_TIME" \
            --time-zone="$SCHEDULE_TIMEZONE" \
            --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run" \
            --http-method="POST" \
            --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com"
    fi

    log_info "Scheduler configured: $SCHEDULE_TIME ($SCHEDULE_TIMEZONE)"
    log_info "Note: 4 PM MST = 11 PM UTC during standard time, 10 PM UTC during daylight saving"
}

# Manually run the job
run_job() {
    log_info "Manually triggering Cloud Run Job..."

    gcloud run jobs execute "$JOB_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --wait

    log_info "Job execution complete!"
}

# Full deployment
full_deploy() {
    log_info "Starting full deployment..."
    build
    deploy_job
    log_info "Full deployment complete!"
    log_info ""
    log_info "To manually run: ./deploy.sh run"
    log_info "To view logs: gcloud run jobs executions logs $JOB_NAME --region=$REGION"
}

# Show usage
usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup     - First-time GCP setup (APIs, Artifact Registry)"
    echo "  secrets   - Create/update secrets in Secret Manager"
    echo "  build     - Build and push Docker image"
    echo "  deploy    - Deploy Cloud Run Job (after build)"
    echo "  schedule  - Set up Cloud Scheduler"
    echo "  run       - Manually trigger the job"
    echo "  (none)    - Full deployment (build + deploy)"
    echo ""
    echo "First-time setup:"
    echo "  1. ./deploy.sh setup"
    echo "  2. ./deploy.sh secrets"
    echo "  3. ./deploy.sh build"
    echo "  4. ./deploy.sh deploy"
    echo "  5. ./deploy.sh schedule"
}

# Main
case "${1:-}" in
    setup)
        setup
        ;;
    secrets)
        setup_secrets
        ;;
    build)
        build
        ;;
    deploy)
        deploy_job
        ;;
    schedule)
        setup_scheduler
        ;;
    run)
        run_job
        ;;
    help|--help|-h)
        usage
        ;;
    "")
        full_deploy
        ;;
    *)
        log_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac
