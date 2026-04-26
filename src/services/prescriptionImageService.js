const axios = require('axios');
const sharp = require('sharp');
const { config } = require('../config');
const { analyzePrescriptionImage } = require('./geminiService');

const NOT_PRESCRIPTION_MESSAGE = "Sorry, I couldn't detect a prescription in this image. Please send a clear photo of your prescription. 📋";
const GEMINI_UNAVAILABLE_MESSAGE = 'Our AI is temporarily unavailable. Please try again in a moment. 🔄';
const MAX_GEMINI_IMAGE_BYTES = 4 * 1024 * 1024;

function inferMimeType(fileName, fallback = 'image/jpeg') {
  const name = String(fileName || '').toLowerCase();
  if (name.endsWith('.png')) return 'image/png';
  if (name.endsWith('.jpg') || name.endsWith('.jpeg')) return 'image/jpeg';
  if (name.endsWith('.webp')) return 'image/webp';
  if (name.endsWith('.pdf')) return 'application/pdf';
  return fallback;
}

async function downloadTwilioMedia(mediaUrl) {
  const response = await axios.get(mediaUrl, {
    responseType: 'arraybuffer',
    auth: {
      username: config.twilioAccountSid,
      password: config.twilioAuthToken,
    },
  });

  return {
    buffer: Buffer.from(response.data),
    mimeType: String(response.headers['content-type'] || 'image/jpeg').split(';')[0],
  };
}

async function normalizePrescriptionUpload(buffer, mimeType) {
  const normalizedMimeType = String(mimeType || 'image/jpeg').split(';')[0];
  if (normalizedMimeType === 'application/pdf') {
    return { buffer, mimeType: normalizedMimeType };
  }

  if (!normalizedMimeType.startsWith('image/')) {
    return { buffer, mimeType: normalizedMimeType };
  }

  if (buffer.length <= MAX_GEMINI_IMAGE_BYTES) {
    return { buffer, mimeType: normalizedMimeType };
  }

  const compressed = await sharp(buffer)
    .rotate()
    .resize({ width: 1600, height: 1600, fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 82, mozjpeg: true })
    .toBuffer();

  return { buffer: compressed, mimeType: 'image/jpeg' };
}

function isNonPrescriptionAnalysis(analysis) {
  const text = String(analysis || '').toLowerCase();
  return (
    !text.trim() ||
    text.includes('could not detect') ||
    text.includes("couldn't detect") ||
    text.includes('not a prescription') ||
    text.includes('no prescription') ||
    text.includes('no medicines detected') ||
    text.includes('unable to identify any medicines')
  );
}

async function analyzePrescriptionBuffer({ buffer, mimeType }) {
  const normalized = await normalizePrescriptionUpload(buffer, mimeType);
  const analysis = await analyzePrescriptionImage(normalized.buffer.toString('base64'), normalized.mimeType);

  if (isNonPrescriptionAnalysis(analysis)) {
    return {
      analysis: NOT_PRESCRIPTION_MESSAGE,
      detected: false,
      mimeType: normalized.mimeType,
      bytes: normalized.buffer.length,
    };
  }

  return {
    analysis,
    detected: true,
    mimeType: normalized.mimeType,
    bytes: normalized.buffer.length,
  };
}

module.exports = {
  GEMINI_UNAVAILABLE_MESSAGE,
  NOT_PRESCRIPTION_MESSAGE,
  analyzePrescriptionBuffer,
  downloadTwilioMedia,
  inferMimeType,
};
