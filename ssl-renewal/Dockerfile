# Dockerfile for automated SSL certificate renewal
FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Google Cloud SDK
RUN curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    apt-get update && apt-get install -y google-cloud-cli && \
    rm -rf /var/lib/apt/lists/*

# Install certbot and GoDaddy DNS plugin
RUN pip install --no-cache-dir \
    certbot \
    certbot-dns-godaddy

# Create directories
RUN mkdir -p /etc/letsencrypt /var/log/letsencrypt /app

# Copy renewal script
COPY renew.sh /app/renew.sh
RUN chmod +x /app/renew.sh

# Set working directory
WORKDIR /app

# Run the renewal script
CMD ["/app/renew.sh"]
