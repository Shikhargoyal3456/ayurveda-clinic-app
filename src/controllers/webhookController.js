const { findPatientByPhone } = require('../models/patientModel');
const { logMessage } = require('../models/messageLogModel');
const { answerPatientQuery } = require('../services/geminiService');
const { GEMINI_UNAVAILABLE_MESSAGE, downloadTwilioMedia, analyzePrescriptionBuffer } = require('../services/prescriptionImageService');
const { sendWhatsAppChunks } = require('../services/twilioService');

const SCANNING_MESSAGE = '🔍 *Kash AI is scanning your prescription...*\nPlease wait a moment while our AI analyzes your medicines. ⏳';

function maskPhoneNumber(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  const lastFour = digits.slice(-4) || 'unknown';
  return `****${lastFour}`;
}

async function processPrescriptionImageWebhook({ payload, from, patient }) {
  const mediaUrl = payload.MediaUrl0 || payload.mediaUrl0;
  const mediaType = payload.MediaContentType0 || payload.mediaContentType0 || 'image/jpeg';

  try {
    logMessage({
      patientId: patient?.id || null,
      direction: 'received',
      fromNumber: from,
      toNumber: payload.To || '',
      body: payload.Body || '[Prescription image]',
      providerMessageId: payload.MessageSid || '',
      status: 'received',
      metadata: { provider: 'twilio', messageType: 'prescription_image', mediaUrl, mediaType },
    });

    const media = await downloadTwilioMedia(mediaUrl);
    const result = await analyzePrescriptionBuffer({
      buffer: media.buffer,
      mimeType: media.mimeType || mediaType,
    });

    const replies = await sendWhatsAppChunks({ to: from, body: result.analysis });
    const successfulReplies = replies.filter((reply) => reply.success);
    successfulReplies.forEach((reply) => {
      logMessage({
        patientId: patient?.id || null,
        direction: 'sent',
        fromNumber: reply.from,
        toNumber: reply.to,
        body: result.analysis,
        providerMessageId: reply.sid,
        status: reply.status,
        metadata: {
          provider: 'twilio',
          messageType: 'prescription_analysis',
          chunkIndex: reply.chunkIndex,
          chunkCount: replies.length,
          detected: result.detected,
          mimeType: result.mimeType,
          bytes: result.bytes,
        },
      });
    });
  } catch (error) {
    console.error('Prescription image analysis failed:', error);
    try {
      const fallbackReplies = await sendWhatsAppChunks({ to: from, body: GEMINI_UNAVAILABLE_MESSAGE });
      const successfulFallbackReplies = fallbackReplies.filter((reply) => reply.success);
      successfulFallbackReplies.forEach((reply) => {
        logMessage({
          patientId: patient?.id || null,
          direction: 'sent',
          fromNumber: reply.from,
          toNumber: reply.to,
          body: GEMINI_UNAVAILABLE_MESSAGE,
          providerMessageId: reply.sid,
          status: reply.status,
          metadata: { provider: 'twilio', messageType: 'prescription_analysis_error' },
        });
      });

      const failedFallbackReplies = fallbackReplies.filter((reply) => !reply.success);
      if (failedFallbackReplies.length > 0) {
        console.error('Prescription fallback WhatsApp send failed', {
          timestamp: new Date().toISOString(),
          phone: maskPhoneNumber(from),
          error: failedFallbackReplies.map((reply) => reply.error).join('; '),
        });
      }
    } catch (fallbackError) {
      console.error('Prescription fallback WhatsApp send failed', {
        timestamp: new Date().toISOString(),
        phone: maskPhoneNumber(from),
        error: fallbackError && fallbackError.message ? fallbackError.message : String(fallbackError),
      });
    }
  }
}

async function handleWhatsAppWebhook(req, res, next) {
  try {
    const from = req.body.From || req.body.from;
    const body = req.body.Body || req.body.body || '';
    const mediaUrl = req.body.MediaUrl0 || req.body.mediaUrl0;
    const mediaType = req.body.MediaContentType0 || req.body.mediaContentType0 || '';

    if (!from || (!body && !mediaUrl)) {
      return res.status(400).json({ error: 'From and Body or MediaUrl0 are required.' });
    }

    const patientPhone = from.replace(/^whatsapp:/, '');
    const patient = findPatientByPhone(patientPhone) || findPatientByPhone(from);

    if (mediaUrl && (!mediaType || mediaType.startsWith('image/') || mediaType === 'application/pdf')) {
      void processPrescriptionImageWebhook({ payload: req.body, from, patient });
      return res.status(200).type('text/xml').send(`<Response><Message>${SCANNING_MESSAGE}</Message></Response>`);
    }

    logMessage({
      patientId: patient?.id || null,
      direction: 'received',
      fromNumber: from,
      toNumber: req.body.To || '',
      body,
      providerMessageId: req.body.MessageSid || '',
      status: 'received',
      metadata: { provider: 'twilio' },
    });

    let answer;
    let answerStatus = 'ok';
    try {
      answer = await answerPatientQuery({ patient, message: body });
    } catch (error) {
      console.error('Patient text analysis failed:', error);
      answer = GEMINI_UNAVAILABLE_MESSAGE;
      answerStatus = 'gemini_unavailable';
    }
    const replies = await sendWhatsAppChunks({ to: from, body: `🤖 *Kash AI:*\n${answer}` });
    const successfulReplies = replies.filter((reply) => reply.success);
    successfulReplies.forEach((reply) => {
      logMessage({
        patientId: patient?.id || null,
        direction: 'sent',
        fromNumber: reply.from,
        toNumber: reply.to,
        body: answer,
        providerMessageId: reply.sid,
        status: reply.status,
        metadata: {
          provider: 'twilio',
          messageType: 'ai_reply',
          answerStatus,
          chunkIndex: reply.chunkIndex,
          chunkCount: replies.length,
        },
      });
    });

    return res.status(200).type('text/xml').send('<Response></Response>');
  } catch (error) {
    return next(error);
  }
}

module.exports = { handleWhatsAppWebhook };
