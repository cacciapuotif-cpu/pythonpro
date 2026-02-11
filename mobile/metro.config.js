const { getDefaultConfig } = require('expo/metro-config');
const net = require('net');

// Porte vietate (già occupate da altri servizi)
const BLOCKED_PORTS = [3000, 3001, 8000, 8001, 5434, 6381, 3200, 4317, 4318, 8888, 9000, 9001, 9090];

// Porta di partenza per Metro
const METRO_START_PORT = 8090;

/**
 * Auto-detect available port for Metro bundler
 * Starts from METRO_START_PORT and tries sequential ports
 */
async function findAvailablePort(startPort = METRO_START_PORT) {
  let port = startPort;
  const maxAttempts = 20;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const candidatePort = port + attempt;

    // Skip blocked ports
    if (BLOCKED_PORTS.includes(candidatePort)) {
      console.log(`⚠️  Port ${candidatePort} is blocked, skipping...`);
      continue;
    }

    const isAvailable = await checkPortAvailable(candidatePort);
    if (isAvailable) {
      console.log(`✅ Metro bundler will use port ${candidatePort}`);
      return candidatePort;
    } else {
      console.log(`⚠️  Port ${candidatePort} is already in use, trying next...`);
    }
  }

  throw new Error(`Could not find available port after ${maxAttempts} attempts`);
}

/**
 * Check if a port is available
 */
function checkPortAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();

    server.once('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        resolve(false);
      } else {
        resolve(false);
      }
    });

    server.once('listening', () => {
      server.close();
      resolve(true);
    });

    server.listen(port, '0.0.0.0');
  });
}

const config = getDefaultConfig(__dirname);

// Override server configuration
config.server = {
  ...config.server,
  port: parseInt(process.env.EXPO_METRO_PORT || METRO_START_PORT, 10),
  // Bind to 0.0.0.0 for LAN access
  enhanceMiddleware: (middleware) => {
    return middleware;
  },
};

// Log Metro configuration on startup
console.log('\n🚀 Metro Bundler Configuration:');
console.log(`📍 Port: ${config.server.port}`);
console.log(`🌐 Host: 0.0.0.0 (LAN accessible)`);
console.log(`🚫 Blocked ports: ${BLOCKED_PORTS.join(', ')}\n`);

module.exports = config;
