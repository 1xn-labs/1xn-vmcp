FROM node:20-slim AS builder

# Accept build arguments for environment variables
ARG VITE_BACKEND_URL
ARG VITE_UNIFIED_BACKEND_URL
ARG VITE_MCP_SERVER_URL
ARG VITE_ENTITY_STRING
ARG VITE_BASE_PATH
ARG VITE_ASSET_PREFIX
ARG NODE_ENV

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --include=dev

# Copy source code
COPY . .

# Set environment variables for the build process
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
ENV VITE_UNIFIED_BACKEND_URL=$VITE_UNIFIED_BACKEND_URL
ENV VITE_MCP_SERVER_URL=$VITE_MCP_SERVER_URL
ENV VITE_ENTITY_STRING=$VITE_ENTITY_STRING
ENV VITE_BASE_PATH=$VITE_BASE_PATH
ENV VITE_ASSET_PREFIX=$VITE_ASSET_PREFIX
ENV NODE_ENV=$NODE_ENV

# Show what we have
RUN echo "=== Current directory ===" && pwd && \
    echo "=== Directory contents ===" && ls -la && \
    echo "=== Node version ===" && node --version && \
    echo "=== NPM version ===" && npm --version

# Build the Vite application
RUN npm run build || (echo "Build failed with exit code $?" && exit 1)

# Verify the build was created
RUN echo "=== Build verification ===" && \
    ls -la && \
    echo "=== dist directory contents ===" && \
    ls -la dist/ || (echo "dist directory not found - build may have failed" && exit 1)

# Production stage - use nginx to serve static files
FROM nginx:alpine

# Copy custom nginx config
COPY <<EOF /etc/nginx/conf.d/default.conf
server {
    listen 3000;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback - serve index.html for all routes
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 3000
EXPOSE 3000

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
