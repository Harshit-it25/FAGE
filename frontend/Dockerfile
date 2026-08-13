FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json .
COPY tsconfig.json .
COPY vite.config.ts .
COPY index.html .

# Install dependencies
RUN npm install

# Copy source code
COPY src/ ./src/

# Build production bundle
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    add_header X-Content-Type-Options nosniff always; \
    add_header X-Frame-Options DENY always; \
    add_header Referrer-Policy no-referrer always; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://backend:8000/; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
}' > /etc/nginx/conf.d/default.conf

# Create a startup script to handle dynamic ports
RUN echo '#!/bin/sh' > /start.sh && \
    echo 'sed -i -e "s/listen 80;/listen ${PORT:-80};/g" /etc/nginx/conf.d/default.conf' >> /start.sh && \
    echo 'exec nginx -g "daemon off;"' >> /start.sh && \
    chmod +x /start.sh

EXPOSE 80

CMD ["/start.sh"]
