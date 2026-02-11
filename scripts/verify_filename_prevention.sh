#!/bin/bash
# Script per verificare che il codice segua le regole di prevenzione nomi "null"
#
# Uso:
#   bash scripts/verify_null_prevention.sh
#   bash scripts/verify_null_prevention.sh --verbose

VERBOSE=false
if [[ "$1" == "--verbose" ]]; then
  VERBOSE=true
fi

echo "=================================================="
echo "Verifica Prevenzione Nomi File 'null'"
echo "=================================================="
echo ""

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Funzione per stampare errori
print_error() {
  echo -e "${RED}[ERROR]${NC} $1"
  ((ERRORS++))
}

# Funzione per stampare warning
print_warning() {
  echo -e "${YELLOW}[WARN]${NC} $1"
  ((WARNINGS++))
}

# Funzione per stampare successi
print_success() {
  echo -e "${GREEN}[OK]${NC} $1"
}

# 1. Verifica che non ci siano file/cartelle con "null" nel nome
echo "1. Controllo file/cartelle con nomi problematici..."
if python scripts/check_null_filenames.py > /dev/null 2>&1; then
  print_success "Nessun file/cartella con nome problematico trovato"
else
  print_error "Trovati file/cartelle con nomi problematici. Esegui: python scripts/check_null_filenames.py --fix"
fi
echo ""

# 2. Verifica che le utility functions esistano
echo "2. Verifica esistenza utility functions..."

# Backend
if [ -f "backend/file_upload.py" ]; then
  if grep -q "validate_name_not_null" backend/file_upload.py; then
    print_success "Backend: validate_name_not_null trovata"
  else
    print_error "Backend: validate_name_not_null mancante in file_upload.py"
  fi

  if grep -q "sanitize_filename" backend/file_upload.py; then
    print_success "Backend: sanitize_filename trovata"
  else
    print_error "Backend: sanitize_filename mancante in file_upload.py"
  fi
else
  print_error "Backend: file_upload.py non trovato"
fi

# Frontend
if [ -f "frontend/src/utils/fileNameValidator.js" ]; then
  print_success "Frontend: fileNameValidator.js trovato"

  if grep -q "export function isValidFileName" frontend/src/utils/fileNameValidator.js; then
    print_success "Frontend: isValidFileName esportata"
  else
    print_error "Frontend: isValidFileName non esportata"
  fi

  if grep -q "export function sanitizeFileName" frontend/src/utils/fileNameValidator.js; then
    print_success "Frontend: sanitizeFileName esportata"
  else
    print_error "Frontend: sanitizeFileName non esportata"
  fi
else
  print_error "Frontend: fileNameValidator.js non trovato"
fi
echo ""

# 3. Verifica che non ci siano usi diretti senza validazione
echo "3. Verifica uso sicuro di nomi file nel codice..."

# Backend - cerca usi di f-strings o concatenazioni con possibili variabili null
BACKEND_UNSAFE=$(grep -rn "f\".*{.*filename.*}\"" backend/*.py 2>/dev/null | grep -v "sanitize" | grep -v "validate" | wc -l)
if [ "$BACKEND_UNSAFE" -eq 0 ]; then
  print_success "Backend: nessun uso diretto pericoloso trovato"
else
  print_warning "Backend: trovati $BACKEND_UNSAFE potenziali usi diretti di filename. Verificare manualmente."
  if [ "$VERBOSE" = true ]; then
    grep -rn "f\".*{.*filename.*}\"" backend/*.py 2>/dev/null | grep -v "sanitize" | grep -v "validate"
  fi
fi

# Frontend - cerca usi diretti di .download senza validazione
FRONTEND_UNSAFE=$(grep -rn "\.download.*=" frontend/src 2>/dev/null | grep -v "safeFilename" | grep -v "sanitize" | wc -l)
if [ "$FRONTEND_UNSAFE" -eq 0 ]; then
  print_success "Frontend: nessun uso diretto pericoloso trovato"
else
  print_warning "Frontend: trovati $FRONTEND_UNSAFE potenziali usi diretti di .download. Verificare manualmente."
  if [ "$VERBOSE" = true ]; then
    grep -rn "\.download.*=" frontend/src 2>/dev/null | grep -v "safeFilename" | grep -v "sanitize"
  fi
fi
echo ""

# 4. Verifica esistenza test
echo "4. Verifica test..."

if [ -f "frontend/src/utils/fileNameValidator.test.js" ]; then
  print_success "Frontend: test trovati"
else
  print_warning "Frontend: test non trovati per fileNameValidator.js"
fi

# Cerca test nel backend
if grep -rq "test.*validate_name_not_null\|def.*test.*null.*filename" backend/tests/ 2>/dev/null; then
  print_success "Backend: test per validazione trovati"
else
  print_warning "Backend: test per validazione non trovati"
fi
echo ""

# 5. Verifica documentazione
echo "5. Verifica documentazione..."

if [ -f "PREVENT_NULL_FILENAMES.md" ]; then
  print_success "Documentazione trovata: PREVENT_NULL_FILENAMES.md"

  if grep -q "fileNameValidator.js" PREVENT_NULL_FILENAMES.md; then
    print_success "Documentazione aggiornata con utility frontend"
  else
    print_warning "Documentazione non aggiornata con utility frontend"
  fi
else
  print_error "Documentazione mancante: PREVENT_NULL_FILENAMES.md"
fi
echo ""

# Riepilogo
echo "=================================================="
echo "Riepilogo"
echo "=================================================="
echo -e "Errori: ${RED}$ERRORS${NC}"
echo -e "Warning: ${YELLOW}$WARNINGS${NC}"

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
  echo -e "\n${GREEN}✓ Tutti i controlli superati!${NC}"
  exit 0
elif [ "$ERRORS" -eq 0 ]; then
  echo -e "\n${YELLOW}✓ Controlli superati con warning${NC}"
  exit 0
else
  echo -e "\n${RED}✗ Alcuni controlli falliti${NC}"
  exit 1
fi
