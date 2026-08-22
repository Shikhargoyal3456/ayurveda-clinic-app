const path = require('path');
const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const { config } = require('./config');
const { initDatabase } = require('./models/database');
const patientRoutes = require('./routes/patientRoutes');
const prescriptionRoutes = require('./routes/prescriptionRoutes');
const reminderRoutes = require('./routes/reminderRoutes');
const webhookRoutes = require('./routes/webhookRoutes');
const healthRoutes = require('./routes/healthRoutes');
const { errorHandler, notFoundHandler } = require('./middleware/errorHandler');

initDatabase();

const app = express();

const requestBuckets = new Map();
const csrfTokens = new Map();

function clientIp(req) {
  const forwardedFor = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
  return forwardedFor || req.ip || req.socket?.remoteAddress || 'unknown';
}

function applyInMemoryRateLimit(req, res, next) {
  const windowMs = Math.max(1000, config.apiIpRateLimitWindowSeconds * 1000);
  const now = Date.now();
  const key = `${clientIp(req)}:${req.method}`;
  const bucket = requestBuckets.get(key) || [];
  const active = bucket.filter((timestamp) => now - timestamp < windowMs);
  if (active.length >= Math.max(1, config.apiIpRateLimitRequests)) {
    const retryAfter = Math.max(1, Math.ceil((windowMs - (now - active[0])) / 1000));
    res.setHeader('Retry-After', String(retryAfter));
    return res.status(429).json({ success: false, error: 'Too many requests. Please slow down.', retry_after: retryAfter });
  }
  active.push(now);
  requestBuckets.set(key, active);
  return next();
}

function csrfTokenForClient(req) {
  const key = clientIp(req);
  const existing = csrfTokens.get(key);
  if (existing) return existing;
  const token = require('crypto').randomBytes(32).toString('hex');
  csrfTokens.set(key, token);
  return token;
}

function applyCsrfProtection(req, res, next) {
  const unsafeMethod = !['GET', 'HEAD', 'OPTIONS'].includes(req.method);
  if (!unsafeMethod || req.path.startsWith('/webhook')) {
    return next();
  }
  const hasAuthCookie = Boolean(req.headers.cookie);
  if (!hasAuthCookie) {
    return next();
  }
  const expected = csrfTokenForClient(req);
  const supplied = String(req.get('x-csrf-token') || req.body?._csrf || req.body?.csrf_token || '');
  if (supplied && supplied === expected) {
    return next();
  }
  return res.status(403).json({ success: false, error: 'Invalid CSRF token.' });
}

function corsOptionsDelegate(req, callback) {
  const origin = req.header('Origin');
  // Requests without an Origin header (same-origin navigations, curl, server-to-server)
  // need no CORS reflection.
  if (!origin) {
    return callback(null, { origin: false, credentials: true });
  }
  // Only reflect origins explicitly present in the configured env allowlist
  // (ALLOWED_ORIGINS / CORS_ORIGINS). An empty allowlist denies all cross-origin
  // requests instead of reflecting arbitrary origins with credentials.
  if (config.allowedOrigins.includes(origin)) {
    return callback(null, { origin, credentials: true });
  }
  return callback(new Error('Origin not allowed by CORS'));
}

app.disable('x-powered-by');
if (config.trustProxy) {
  app.set('trust proxy', 1);
}
app.use((req, res, next) => {
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  res.setHeader('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'");
  next();
});
app.use(cors(corsOptionsDelegate));
app.use(morgan(config.nodeEnv === 'production' ? 'combined' : 'dev'));
app.use(applyInMemoryRateLimit);
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false }));
app.use((req, res, next) => {
  res.setHeader('X-CSRF-Token', csrfTokenForClient(req));
  next();
});
// SECURITY TODO: add CSRF middleware (csurf) on state-changing routes.
// A custom double-submit-style guard (applyCsrfProtection) is wired below, but it only
// enforces when a Cookie header is present and stores tokens in-memory keyed by client IP.
// Adopting a vetted library (csurf / csrf-csrf) is a pending dependency decision.
app.use(applyCsrfProtection);
app.use('/static', express.static(path.join(__dirname, '..', 'public')));
app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(config.publicDir, 'dashboard.html'));
});

app.use('/patients', patientRoutes);
app.use('/prescriptions', prescriptionRoutes);
app.use('/reminders', reminderRoutes);
app.use('/webhook', webhookRoutes);
app.use('/health', healthRoutes);

app.use(notFoundHandler);
app.use(errorHandler);

if (require.main === module) {
  app.listen(config.port, () => {
    console.log(`WhatsApp notification service listening on port ${config.port}`);
  });
}

module.exports = app;
