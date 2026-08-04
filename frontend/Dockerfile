# ====================
# BUILD STAGE
# ====================
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install ALL dependencies (needed for build)
# Using npm install instead of npm ci because lock file may be out of sync
RUN npm install --no-audit

# Copy source code
COPY . .

# Build argument for API URL (empty = usa URL relativo, nginx fa il proxy)
ARG REACT_APP_API_URL=
ARG APP_COMMIT=unknown
ARG APP_BUILD_DATE=unknown

# Build static files
RUN REACT_APP_API_URL=$REACT_APP_API_URL \
    REACT_APP_GIT_COMMIT=$APP_COMMIT \
    REACT_APP_BUILD_DATE=$APP_BUILD_DATE \
    npm run build

# ====================
# PRODUCTION STAGE
# ====================
FROM nginx:1.27-alpine

ARG APP_COMMIT=unknown
ARG APP_BUILD_DATE=unknown

LABEL org.opencontainers.image.revision="${APP_COMMIT}" \
      org.opencontainers.image.created="${APP_BUILD_DATE}"

# Copy built static files
COPY --from=build /app/build /usr/share/nginx/html

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run /etc/nginx/nginx.conf
USER nginx

# Expose port 8080 (internal, non-root)
EXPOSE 8080

# Healthcheck
# Usa 127.0.0.1 invece di localhost per evitare problemi IPv6
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/healthz || exit 1

# Start nginx (foreground mode)
CMD ["nginx", "-g", "daemon off;"]
