#!/usr/bin/env node

/**
 * SMOKE TEST SCRIPT
 *
 * Verifica che il backend sia raggiungibile e che gli endpoint API principali rispondano.
 *
 * Usage:
 *   node scripts/smoke.js
 *
 * Exit codes:
 *   0 - Tutti i test passati
 *   1 - Uno o più test falliti
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

// Configurazione
const BACKEND_HOST = process.env.BACKEND_HOST || 'localhost';
const BACKEND_PORT = process.env.BACKEND_PORT || '8000';
const BASE_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const LOG_FILE = path.join(__dirname, '..', 'artifacts', 'smoke.log');

// Colori console
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

// Logger
class Logger {
  constructor() {
    this.logs = [];
  }

  log(message, color = 'reset') {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${message}`;
    console.log(`${colors[color]}${logEntry}${colors.reset}`);
    this.logs.push(logEntry);
  }

  info(message) {
    this.log(`ℹ️  ${message}`, 'cyan');
  }

  success(message) {
    this.log(`✅ ${message}`, 'green');
  }

  error(message) {
    this.log(`❌ ${message}`, 'red');
  }

  warning(message) {
    this.log(`⚠️  ${message}`, 'yellow');
  }

  save() {
    const dirPath = path.dirname(LOG_FILE);
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
    fs.writeFileSync(LOG_FILE, this.logs.join('\n'), 'utf8');
    this.info(`Log salvato in: ${LOG_FILE}`);
  }
}

const logger = new Logger();

// HTTP request helper
function httpRequest(url, method = 'GET') {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const options = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port,
      path: parsedUrl.pathname + parsedUrl.search,
      method: method,
      timeout: 5000,
    };

    const req = http.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        resolve({
          status: res.statusCode,
          statusText: res.statusMessage,
          headers: res.headers,
          data: data,
        });
      });
    });

    req.on('error', (error) => {
      reject(error);
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });

    req.end();
  });
}

// Test definitions
const tests = [
  {
    name: 'Backend Health Check',
    url: `${BASE_URL}/health`,
    expectedStatus: 200,
    description: 'Verifica che il backend risponda su /health',
  },
  {
    name: 'Root Endpoint',
    url: `${BASE_URL}/`,
    expectedStatus: 200,
    description: 'Verifica che l\'endpoint root sia raggiungibile',
  },
  {
    name: 'Projects API',
    url: `${BASE_URL}/api/v1/projects/`,
    expectedStatus: [200, 401], // 200 se no auth, 401 se richiesta auth
    description: 'Verifica che l\'endpoint progetti sia raggiungibile',
  },
  {
    name: 'Collaborators API',
    url: `${BASE_URL}/api/v1/collaborators/`,
    expectedStatus: [200, 401],
    description: 'Verifica che l\'endpoint collaboratori sia raggiungibile',
  },
  {
    name: 'API Docs',
    url: `${BASE_URL}/docs`,
    expectedStatus: 200,
    description: 'Verifica che la documentazione API sia disponibile',
  },
];

// Main test runner
async function runTests() {
  logger.log('\n' + '='.repeat(60), 'blue');
  logger.log('🧪 SMOKE TEST - Gestionale Backend', 'blue');
  logger.log('='.repeat(60) + '\n', 'blue');

  logger.info(`Target: ${BASE_URL}`);
  logger.info(`Tests da eseguire: ${tests.length}\n`);

  let passedTests = 0;
  let failedTests = 0;

  for (const test of tests) {
    logger.log(`\n📋 Test: ${test.name}`, 'cyan');
    logger.info(`   ${test.description}`);
    logger.info(`   URL: ${test.url}`);

    try {
      const response = await httpRequest(test.url);

      logger.info(`   Status: ${response.status} ${response.statusText}`);

      // Check if status is expected
      const expectedStatuses = Array.isArray(test.expectedStatus)
        ? test.expectedStatus
        : [test.expectedStatus];

      if (expectedStatuses.includes(response.status)) {
        logger.success(`   Test PASSED`);
        passedTests++;

        // Log sample response body (first 200 chars)
        try {
          const bodyPreview = response.data.substring(0, 200);
          logger.info(`   Response preview: ${bodyPreview}...`);
        } catch (e) {
          // Ignore if body can't be parsed
        }
      } else {
        logger.error(`   Test FAILED - Expected status ${expectedStatuses.join(' or ')}, got ${response.status}`);
        logger.warning(`   Response: ${response.data.substring(0, 300)}`);
        failedTests++;
      }
    } catch (error) {
      logger.error(`   Test FAILED - ${error.message}`);
      if (error.code === 'ECONNREFUSED') {
        logger.error(`   Backend non raggiungibile su ${BASE_URL}`);
        logger.warning(`   Verifica che il backend sia avviato sulla porta ${BACKEND_PORT}`);
      }
      failedTests++;
    }
  }

  // Summary
  logger.log('\n' + '='.repeat(60), 'blue');
  logger.log('📊 RISULTATI SMOKE TEST', 'blue');
  logger.log('='.repeat(60), 'blue');

  const total = passedTests + failedTests;
  logger.info(`Totale test:    ${total}`);
  logger.success(`Test passati:   ${passedTests}`);

  if (failedTests > 0) {
    logger.error(`Test falliti:   ${failedTests}`);
  }

  const successRate = total > 0 ? ((passedTests / total) * 100).toFixed(1) : 0;
  logger.info(`Success rate:   ${successRate}%`);

  logger.log('='.repeat(60) + '\n', 'blue');

  // Save logs
  logger.save();

  // Exit with appropriate code
  if (failedTests > 0) {
    logger.error('❌ Smoke test FALLITO\n');
    process.exit(1);
  } else {
    logger.success('✅ Smoke test SUPERATO\n');
    process.exit(0);
  }
}

// Run
runTests().catch((error) => {
  logger.error(`Errore fatale: ${error.message}`);
  logger.save();
  process.exit(1);
});
