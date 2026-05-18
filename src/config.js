// Twilio WhatsApp routing:
// - This Node stack owns Twilio-backed WhatsApp delivery for prescriptions,
//   reminders, inbound Twilio webhooks, and AI-generated WhatsApp replies.
// - Python app flows that use Meta WhatsApp Cloud API are configured separately
//   in app/config.py and services/whatsapp.py.
const path = require('path');
require('dotenv').config();

const rootDir = path.resolve(__dirname, '..');

function sanitizeWhatsAppNumber(number) {
  if (!number) return null;

  let cleaned = String(number).trim().replace(/[\s-]/g, '');

  if (!cleaned.startsWith('whatsapp:+')) {
    if (/^\+?\d+$/.test(cleaned)) {
      cleaned = `whatsapp:${cleaned.startsWith('+') ? cleaned : `+${cleaned}`}`;
    }
  }

  const validFormat = /^whatsapp:\+\d{10,15}$/;
  if (!validFormat.test(cleaned)) {
    throw new Error('TWILIO_WHATSAPP_NUMBER format invalid after sanitization');
  }

  return cleaned;
}

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
  twilioWhatsappNumber: sanitizeWhatsAppNumber(process.env.TWILIO_WHATSAPP_NUMBER || 'whatsapp:+14155238886'),
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
