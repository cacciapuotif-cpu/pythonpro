#!/bin/bash

# Script di inizializzazione automatica del sistema
# Questo script assicura che il sistema sia sempre avviato correttamente

echo "🚀 Inizializzazione Sistema Gestionale..."

# Controlla se Docker è in esecuzione
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker non è in esecuzione. Avvia Docker Desktop e riprova."
    exit 1
fi

echo "✅ Docker è attivo"

# Ferma eventuali container in esecuzione
echo "🛑 Fermando container esistenti..."
docker-compose down -v

# Rimuove immagini vecchie per forzare rebuild
echo "🧹 Pulizia immagini vecchie..."
docker-compose build --no-cache

# Avvia tutti i servizi
echo "🏗️ Avviando servizi..."
docker-compose up -d

# Attende che i servizi siano healthy
echo "⏳ Attendendo che i servizi siano pronti..."
sleep 10

# Controlla lo stato dei servizi
echo "🔍 Controllo stato servizi..."
docker-compose ps

# Controlla health check del backend
echo "🩺 Test connessione backend..."
for i in {1..10}; do
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        echo "✅ Backend connesso!"
        break
    else
        echo "⏳ Tentativo $i/10 - Attendendo backend..."
        sleep 3
    fi
done

# Controlla se il frontend è raggiungibile
echo "🌐 Test connessione frontend..."
for i in {1..10}; do
    if curl -f http://localhost:3001 > /dev/null 2>&1; then
        echo "✅ Frontend connesso!"
        break
    else
        echo "⏳ Tentativo $i/10 - Attendendo frontend..."
        sleep 3
    fi
done

echo ""
echo "🎉 Sistema avviato con successo!"
echo ""
echo "📋 Accesso al gestionale:"
echo "   Frontend: http://localhost:3001"
echo "   API Docs: http://localhost:8001/docs"
echo "   Health:   http://localhost:8001/health"
echo ""
echo "🔧 Comandi utili:"
echo "   docker-compose logs backend   # Log backend"
echo "   docker-compose logs frontend  # Log frontend"
echo "   docker-compose ps            # Stato servizi"
echo "   docker-compose down          # Ferma tutto"
echo ""