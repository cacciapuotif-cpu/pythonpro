# ====================
# BUILD STAGE
# ====================
FROM node:18-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install ALL dependencies (needed for build)
# Using npm install instead of npm ci because lock file may be out of sync
RUN npm install --no-audit

# Copy source code
COPY . .

# Build argument for API URL
ARG REACT_APP_API_URL=http://localhost:8001/api/v1

# Build static files
RUN REACT_APP_API_URL=$REACT_APP_API_URL npm run build

# ====================
# PRODUCTION STAGE
# ====================
FROM nginx:1.27-alpine

# Copy built static files
COPY --from=build /app/build /usr/share/nginx/html

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port 80 (internal)
EXPOSE 80

# Healthcheck
# Usa 127.0.0.1 invece di localhost per evitare problemi IPv6
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/healthz || exit 1

# Start nginx (foreground mode)
CMD ["nginx", "-g", "daemon off;"]
