#!/bin/bash
set -e
echo "Build frontend..."
docker build -t pythonpro-frontend:latest /DATA/progetti/pythonpro/frontend
echo "Stop vecchio container..."
docker stop pythonpro_frontend || true
docker rm pythonpro_frontend || true
echo "Avvia nuovo container..."
docker run -d \
  --name pythonpro_frontend \
  --network pythonpro_net \
  -p 3001:80 \
  --restart unless-stopped \
  pythonpro-frontend:latest
echo "Done. Attendo health check..."
sleep 5
docker ps | grep frontend
