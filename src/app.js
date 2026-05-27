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

function corsOptionsDelegate(req, callback) {
  const origin = req.header('Origin');
  if (!origin || config.allowedOrigins.length === 0 || config.allowedOrigins.includes(origin)) {
    return callback(null, { origin: origin || false, credentials: true });
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
