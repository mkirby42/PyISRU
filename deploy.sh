#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting deployment...${NC}"

# Function to stop and remove container if it exists
cleanup_container() {
    local container_name=$1
    if docker ps -a --format "table {{.Names}}" | grep -q "^${container_name}$"; then
        echo -e "${YELLOW}Stopping and removing existing ${container_name} container...${NC}"
        docker stop $container_name
        docker rm $container_name
    else
        echo -e "${GREEN}No existing ${container_name} container found${NC}"
    fi
}

# Stop and remove existing containers
cleanup_container "flask-app"
cleanup_container "cloudflared"

# Create network if it doesn't exist
echo -e "${YELLOW}Ensuring flask-net network exists...${NC}"
docker network create flask-net 2>/dev/null || echo -e "${GREEN}Network flask-net already exists${NC}"

# Unlock keychain for Docker build
echo -e "${YELLOW}Unlocking keychain...${NC}"
security -v unlock-keychain ~/Library/Keychains/login.keychain-db

# Rebuild flask app image
echo -e "${YELLOW}Rebuilding flask app image...${NC}"
if docker build -t pyisru .; then
    echo -e "${GREEN}Flask app image built successfully${NC}"
else
    echo -e "${RED}Failed to build flask app image${NC}"
    exit 1
fi

# Ensure host comments directory exists
COMMENTS_HOST_DIR="/srv/pyisru-comments"
mkdir -p "$COMMENTS_HOST_DIR"

# Run flask app container with comments volume
echo -e "${YELLOW}Starting flask app container...${NC}"
if docker run -d -p 8000:8000 --name flask-app --network flask-net \
    -e COMMENTS_DB_PATH=/data/comments.sqlite3 \
    -v "$COMMENTS_HOST_DIR":/data \
    pyisru; then
    echo -e "${GREEN}Flask app container started successfully${NC}"
else
    echo -e "${RED}Failed to start flask app container${NC}"
    exit 1
fi

# Wait a moment for flask app to start
echo -e "${YELLOW}Waiting for flask app to initialize...${NC}"
sleep 5

# Check if CLOUDFLARE_TOKEN is set
if [ -z "$CLOUDFLARE_TOKEN" ]; then
    echo -e "${RED}Error: CLOUDFLARE_TOKEN environment variable is not set${NC}"
    echo -e "${YELLOW}Set it with: export CLOUDFLARE_TOKEN=your_token_here${NC}"
    exit 1
fi

# Run cloudflared container
echo -e "${YELLOW}Starting cloudflared container...${NC}"
if docker run -d \
  --name cloudflared \
  --network flask-net \
  --restart=always \
  cloudflare/cloudflared:latest \
  --no-autoupdate tunnel run \
  --token $CLOUDFLARE_TOKEN \
  --url http://flask-app:8000; then
    echo -e "${GREEN}Cloudflared container started successfully${NC}"
else
    echo -e "${RED}Failed to start cloudflared container${NC}"
    exit 1
fi

# Wait for tunnel to establish
echo -e "${YELLOW}Waiting for tunnel to establish...${NC}"
sleep 5

# Test connectivity
echo -e "${YELLOW}Testing site connectivity...${NC}"
if curl -s -o /dev/null -w "%{http_code}" https://mathewkirby.com | grep -q "200"; then
    echo -e "${GREEN}✅ Deployment successful! Site is reachable at https://mathewkirby.com${NC}"
else
    echo -e "${RED}❌ Site connectivity test failed${NC}"
    echo -e "${YELLOW}Checking container status:${NC}"
    docker ps --filter "name=flask-app" --filter "name=cloudflared"
    exit 1
fi

echo -e "${GREEN}🚀 Deployment completed successfully!${NC}" 