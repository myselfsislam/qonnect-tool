#!/bin/bash

set -e

echo "=========================================="
echo "SSL Certificate Renewal - Started"
echo "=========================================="
echo "Domain: $DOMAIN"
echo "Project: $GCP_PROJECT"
echo "Time: $(date)"
echo ""

# Validate required environment variables
if [ -z "$DOMAIN" ] || [ -z "$GCP_PROJECT" ] || [ -z "$GODADDY_API_KEY" ] || [ -z "$GODADDY_API_SECRET" ]; then
    echo "ERROR: Required environment variables not set!"
    echo "Required: DOMAIN, GCP_PROJECT, GODADDY_API_KEY, GODADDY_API_SECRET"
    exit 1
fi

# Create GoDaddy credentials file
echo "Creating GoDaddy credentials file..."
mkdir -p /root/.secrets
cat > /root/.secrets/godaddy.ini << EOF
dns_godaddy_key = $GODADDY_API_KEY
dns_godaddy_secret = $GODADDY_API_SECRET
EOF
chmod 600 /root/.secrets/godaddy.ini

# Authenticate with GCP (uses service account from Cloud Run)
echo "Authenticating with GCP..."
gcloud config set project $GCP_PROJECT

# Renew certificate using certbot with GoDaddy DNS
echo ""
echo "=========================================="
echo "Step 1: Renewing certificate with Let's Encrypt"
echo "=========================================="
certbot certonly \
    --dns-godaddy \
    --dns-godaddy-credentials /root/.secrets/godaddy.ini \
    --dns-godaddy-propagation-seconds 120 \
    --non-interactive \
    --agree-tos \
    --email $ADMIN_EMAIL \
    --domains $DOMAIN \
    --force-renewal

if [ $? -ne 0 ]; then
    echo "ERROR: Certificate renewal failed!"
    exit 1
fi

echo "✅ Certificate renewed successfully!"
echo ""

# Generate certificate name with date
CERT_NAME="qualitest-letsencrypt-$(date +%Y%m%d-%H%M%S)"
echo "New certificate name: $CERT_NAME"

# Upload new certificate to GCP
echo ""
echo "=========================================="
echo "Step 2: Uploading certificate to GCP"
echo "=========================================="
gcloud compute ssl-certificates create $CERT_NAME \
    --certificate=/etc/letsencrypt/live/$DOMAIN/fullchain.pem \
    --private-key=/etc/letsencrypt/live/$DOMAIN/privkey.pem \
    --project=$GCP_PROJECT \
    --global

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to upload certificate to GCP!"
    exit 1
fi

echo "✅ Certificate uploaded to GCP successfully!"
echo ""

# Wait for certificate to be ready
echo "Waiting 10 seconds for certificate to be available..."
sleep 10

# Update HTTPS proxy to use new certificate
echo ""
echo "=========================================="
echo "Step 3: Updating HTTPS proxy"
echo "=========================================="
gcloud compute target-https-proxies update $HTTPS_PROXY_NAME \
    --ssl-certificates=$CERT_NAME \
    --project=$GCP_PROJECT \
    --global

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to update HTTPS proxy!"
    echo "WARNING: New certificate uploaded but not active!"
    exit 1
fi

echo "✅ HTTPS proxy updated successfully!"
echo ""

# Wait for changes to propagate
echo "Waiting 30 seconds for changes to propagate..."
sleep 30

# Verify the certificate is active
echo ""
echo "=========================================="
echo "Step 4: Verifying certificate"
echo "=========================================="
ACTIVE_CERT=$(gcloud compute target-https-proxies describe $HTTPS_PROXY_NAME \
    --project=$GCP_PROJECT \
    --global \
    --format="value(sslCertificates[0])" | xargs basename)

echo "Active certificate: $ACTIVE_CERT"

if [ "$ACTIVE_CERT" = "$CERT_NAME" ]; then
    echo "✅ Verification successful! New certificate is active."
else
    echo "⚠️  WARNING: Expected $CERT_NAME but got $ACTIVE_CERT"
fi

echo ""

# Delete old certificates (keep last 3)
echo "=========================================="
echo "Step 5: Cleaning up old certificates"
echo "=========================================="
OLD_CERTS=$(gcloud compute ssl-certificates list \
    --project=$GCP_PROJECT \
    --filter="name~qualitest-letsencrypt" \
    --format="value(name)" \
    --sort-by=creationTimestamp | head -n -3)

if [ ! -z "$OLD_CERTS" ]; then
    echo "Old certificates to delete:"
    echo "$OLD_CERTS"
    echo ""

    for cert in $OLD_CERTS; do
        # Don't delete if it's currently in use
        if [ "$cert" != "$ACTIVE_CERT" ]; then
            echo "Deleting old certificate: $cert"
            gcloud compute ssl-certificates delete $cert \
                --project=$GCP_PROJECT \
                --global \
                --quiet || echo "  ⚠️  Failed to delete $cert (might be in use)"
        else
            echo "Skipping $cert (currently active)"
        fi
    done
    echo "✅ Cleanup complete!"
else
    echo "No old certificates to clean up."
fi

echo ""
echo "=========================================="
echo "SSL Certificate Renewal - Completed Successfully!"
echo "=========================================="
echo "Certificate: $CERT_NAME"
echo "Domain: $DOMAIN"
echo "Expires: ~90 days from now"
echo "Next renewal: ~60 days from now"
echo "Completed at: $(date)"
echo "=========================================="

# Clean up sensitive files
rm -f /root/.secrets/godaddy.ini

exit 0
