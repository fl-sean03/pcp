FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Node.js for Claude Code
    curl \
    git \
    gnupg \
    # PDF processing
    poppler-utils \
    # File type detection
    file \
    # Image processing
    imagemagick \
    # OCR for images
    tesseract-ocr \
    # Database CLI
    sqlite3 \
    # General utilities
    jq \
    procps \
    # OneDrive access via rclone
    rclone \
    # Chrome/Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    fonts-noto-color-emoji \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    # Docker CLI for self-modification
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code globally
RUN npm install -g @anthropic-ai/claude-code

# Install Playwright MCP server globally
RUN npm install -g @playwright/mcp

# Install Python dependencies
RUN pip install --no-cache-dir \
    requests \
    chromadb \
    python-dateutil \
    pytesseract \
    Pillow \
    PyPDF2 \
    playwright

# Create non-root user with docker group access
RUN groupadd -g 130 docker || true \
    && useradd -m -u 1000 -G docker pcp

# Install Playwright browser dependencies and Chrome as root
# This avoids the su authentication issue when running as non-root
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN mkdir -p /opt/playwright-browsers \
    && npx playwright install --with-deps chromium \
    && chmod -R 755 /opt/playwright-browsers

# Set working directory
WORKDIR /workspace

# Copy workspace files
COPY --chown=pcp:pcp . /workspace/

# Create required directories
RUN mkdir -p /workspace/vault/files /workspace/vault/onedrive_cache /workspace/knowledge \
    && chown -R pcp:pcp /workspace

# Switch to non-root user
USER pcp

# Set home directory
ENV HOME=/home/pcp

# Keep container running (for docker exec)
CMD ["tail", "-f", "/dev/null"]
