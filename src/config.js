const path = require('path');
require('dotenv').config();

const rootDir = path.resolve(__dirname, '..');

const config = {
  nodeEnv: process.env.NODE_ENV || 'development',
  port: Number(process.env.PORT || 3000),
  publicDir: path.join(rootDir, 'public'),
  publicUrl: (process.env.PUBLIC_URL || '').replace(/\/$/, ''),
  kashAiLogoUrl: process.env.KASH_AI_LOGO_URL || '',
  logoMediaPath: process.env.LOGO_MEDIA_PATH || '/static/images/kash-ai-logo.png',
  databasePath: process.env.SQLITE_DB_PATH || path.join(rootDir, 'data', 'whatsapp_notifications.sqlite'),
  twilioAccountSid: process.env.TWILIO_ACCOUNT_SID || '',
  twilioAuthToken: process.env.TWILIO_AUTH_TOKEN || '',
  twilioWhatsappNumber: process.env.TWILIO_WHATSAPP_NUMBER || 'whatsapp:+14155238886',
  twilioPrescriptionContentSid: process.env.TWILIO_PRESCRIPTION_CONTENT_SID || '',
  geminiApiKey: process.env.GEMINI_API_KEY || '',
  geminiModel: process.env.GEMINI_MODEL || 'gemini-2.5-flash',
  geminiVisionModel: process.env.GEMINI_VISION_MODEL || 'gemini-1.5-pro',
  geminiVisionFallbackModel: process.env.GEMINI_VISION_FALLBACK_MODEL || process.env.GEMINI_MODEL || 'gemini-2.5-flash',
  redisUrl: process.env.REDIS_URL || 'redis://127.0.0.1:6379',
  testMode: String(process.env.TEST_MODE || '').toLowerCase() === 'true',
  testUploadsDir: process.env.TEST_UPLOADS_DIR || path.join(rootDir, 'temp', 'test-uploads'),
};

module.exports = { config };
