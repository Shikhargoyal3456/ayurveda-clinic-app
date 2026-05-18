const twilio = require('twilio');
const { config } = require('../config');

let client;

function getTwilioClient() {
  if (!config.twilioAccountSid || !config.twilioAuthToken) {
    throw new Error('Twilio credentials are not configured.');
  }
  if (!client) {
    client = twilio(config.twilioAccountSid, config.twilioAuthToken);
  }
  return client;
}

function sanitizeWhatsAppNumber(number) {
  if (!number) return null;

  let cleaned = String(number).trim().replace(/[\s-]/g, '');

  if (!cleaned.startsWith('whatsapp:+')) {
    if (cleaned.startsWith('+')) {
      cleaned = `whatsapp:${cleaned}`;
    } else if (/^\d+$/.test(cleaned)) {
      cleaned = cleaned.length === 10 ? `whatsapp:+91${cleaned}` : `whatsapp:+${cleaned}`;
    }
  }

  const validFormat = /^whatsapp:\+\d{10,15}$/;
  if (!validFormat.test(cleaned)) {
    return null;
  }

  return cleaned;
}

function normalizeWhatsappNumber(phone) {
  if (!phone) {
    throw new Error('Patient phone number is required.');
  }

  const normalized = sanitizeWhatsAppNumber(phone);
  if (!normalized) {
    console.warn('Invalid WhatsApp number format after normalization');
    return null;
  }
  return normalized;
}

function formatDoctorName(doctorName) {
  const doctor = String(doctorName || '').trim();
  if (!doctor) {
    return '';
  }
  return doctor.startsWith('Dr.') ? doctor : `Dr. ${doctor}`;
}

function buildPrescriptionMessage({ prescription, doctorName }) {
  return [
    '🌿 *Kash AI - Smart Clinic Platform*',
    '━━━━━━━━━━━━━━━━━━━━',
    `👤 Patient: ${prescription.patientName || 'Patient'}`,
    `📋 Prescription by ${doctorName}`,
    '━━━━━━━━━━━━━━━━━━━━',
    `💊 Medicine: ${prescription.medicineName}`,
    `📏 Dosage: ${prescription.dosage}`,
    `🔄 Frequency: ${prescription.frequency}`,
    `📅 Duration: ${prescription.duration}`,
    '━━━━━━━━━━━━━━━━━━━━',
    '🤖 Powered by Kash AI',
    '_Smart Clinic Platform_',
  ].join('\n');
}

function buildLogoMediaUrl() {
  if (config.kashAiLogoUrl) {
    return config.kashAiLogoUrl;
  }
  if (!config.publicUrl) {
    return '';
  }
  return new URL(config.logoMediaPath, `${config.publicUrl}/`).toString();
}

async function sendLogoMessage(to) {
  const logoMediaUrl = buildLogoMediaUrl();
  if (!logoMediaUrl) {
    return null;
  }
  return getTwilioClient().messages.create({
    from: config.twilioWhatsappNumber,
    to,
    mediaUrl: [logoMediaUrl],
  });
}

async function sendPrescriptionNotification({ patient, prescription }) {
  const to = normalizeWhatsappNumber(patient.phone);
  const doctorName = formatDoctorName(prescription.doctorName);
  const contentVariables = {
    patient_name: patient.name,
    medicine_name: prescription.medicineName,
    dosage: prescription.dosage,
    frequency: prescription.frequency,
    duration: prescription.duration,
    doctor_name: doctorName,
  };

  const payload = {
    from: config.twilioWhatsappNumber,
    to,
  };

  if (config.twilioPrescriptionContentSid) {
    payload.contentSid = config.twilioPrescriptionContentSid;
    payload.contentVariables = JSON.stringify(contentVariables);
  } else {
    payload.body = buildPrescriptionMessage({
      prescription: {
        ...prescription,
        patientName: patient.name,
      },
      doctorName,
    });
  }

  const textMessage = await getTwilioClient().messages.create(payload);
  return Object.assign(textMessage, {
    mediaMessage: null,
    textMessage,
  });
}

async function sendReminder({ patient, prescription }) {
  const to = normalizeWhatsappNumber(patient.phone);
  const body = `⏰ *Kash AI Reminder:*\nTime to take your ${prescription.medicineName} - ${prescription.dosage}`;
  const mediaMessage = await sendLogoMessage(to);
  const textMessage = await getTwilioClient().messages.create({
    from: config.twilioWhatsappNumber,
    to,
    body,
  });
  return Object.assign(textMessage, {
    mediaMessage,
    textMessage,
  });
}

async function sendWhatsAppReply({ to, body }) {
  const whatsappTo = normalizeWhatsappNumber(to);
  const mediaMessage = await sendLogoMessage(whatsappTo);
  const textMessage = await getTwilioClient().messages.create({
    from: config.twilioWhatsappNumber,
    to: whatsappTo,
    body: `🤖 *Kash AI:*\n${body}`,
  });
  return Object.assign(textMessage, {
    mediaMessage,
    textMessage,
  });
}

async function sendWhatsAppText({ to, body }) {
  const whatsappTo = normalizeWhatsappNumber(to);
  if (!whatsappTo) {
    throw new Error('Patient phone number is invalid.');
  }
  return getTwilioClient().messages.create({
    from: config.twilioWhatsappNumber,
    to: whatsappTo,
    body,
  });
}

function splitWhatsAppMessage(body, maxLength = 1600) {
  const text = String(body || '').trim();
  if (!text) {
    return [];
  }

  const chunks = [];
  let remaining = text;
  while (remaining.length > maxLength) {
    let splitAt = remaining.lastIndexOf('\n\n', maxLength);
    if (splitAt < maxLength * 0.5) {
      splitAt = remaining.lastIndexOf('\n', maxLength);
    }
    if (splitAt < maxLength * 0.5) {
      splitAt = remaining.lastIndexOf(' ', maxLength);
    }
    if (splitAt <= 0) {
      splitAt = maxLength;
    }
    chunks.push(remaining.slice(0, splitAt).trim());
    remaining = remaining.slice(splitAt).trim();
  }
  if (remaining) {
    chunks.push(remaining);
  }
  return chunks;
}

async function sendWhatsAppChunks({ to, body, maxLength = 1600 }) {
  const chunks = splitWhatsAppMessage(body, maxLength);
  const results = [];
  let successCount = 0;

  for (let index = 0; index < chunks.length; index += 1) {
    const chunk = chunks[index];
    try {
      const message = await sendWhatsAppText({ to, body: chunk });
      results.push({
        chunkIndex: index + 1,
        success: true,
        error: null,
        body: chunk,
        sid: message.sid,
        status: message.status,
        from: message.from,
        to: message.to,
        message,
      });
      successCount += 1;
    } catch (error) {
      results.push({
        chunkIndex: index + 1,
        success: false,
        error: error && error.message ? error.message : String(error),
        body: chunk,
      });
    }
  }

  console.info(`${successCount}/${chunks.length} chunks sent successfully`);
  return results;
}

module.exports = {
  buildLogoMediaUrl,
  buildPrescriptionMessage,
  formatDoctorName,
  sanitizeWhatsAppNumber,
  normalizeWhatsappNumber,
  sendLogoMessage,
  sendPrescriptionNotification,
  sendReminder,
  sendWhatsAppChunks,
  sendWhatsAppReply,
  sendWhatsAppText,
  splitWhatsAppMessage,
};
