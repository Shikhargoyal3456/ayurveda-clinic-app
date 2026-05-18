require('dotenv').config();

const twilio = require('twilio');

function sanitizeWhatsAppNumber(number) {
  if (!number) return null;
  let cleaned = String(number).trim().replace(/[\s-]/g, '');
  if (!cleaned.startsWith('whatsapp:+')) {
    if (/^\+?\d+$/.test(cleaned)) {
      cleaned = `whatsapp:${cleaned.startsWith('+') ? cleaned : `+${cleaned}`}`;
    }
  }
  return cleaned;
}

function printSuccess(label, message) {
  console.log(`✅ ${label} - ${message}`);
}

function printFailure(label, error) {
  const message = error && error.message ? error.message : String(error);
  console.log(`❌ ${label} - Failed: ${message}`);
}

function requireEnv(name) {
  const value = String(process.env[name] || '').trim();
  if (!value) {
    throw new Error(`Missing environment variable: ${name}`);
  }
  return value;
}

function maskPhoneNumber(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  const lastFour = digits.slice(-4) || 'unknown';
  return `****${lastFour}`;
}

function normalizeWhatsappNumber(phone) {
  const raw = String(phone || '').trim().replace(/^whatsapp:/i, '');
  const digits = raw.replace(/\D/g, '');
  if (!digits) {
    throw new Error('TEST_PHONE_NUMBER is invalid.');
  }
  if (digits.length === 10) {
    return `whatsapp:+91${digits}`;
  }
  if (digits.length === 12 && digits.startsWith('91')) {
    return `whatsapp:+${digits}`;
  }
  if (raw.startsWith('+')) {
    return `whatsapp:+${digits}`;
  }
  return `whatsapp:+${digits}`;
}

async function testTwilioAccount(client) {
  try {
    const account = await client.api.accounts(requireEnv('TWILIO_ACCOUNT_SID')).fetch();
    const accountName = account.friendlyName || account.sid;
    printSuccess('Twilio Account', `Connected: ${accountName}`);
  } catch (error) {
    printFailure('Twilio Account', error);
  }
}

async function testWhatsappNumber(client) {
  try {
    const sender = sanitizeWhatsAppNumber(requireEnv('TWILIO_WHATSAPP_NUMBER'));
    if (!/^whatsapp:\+\d+$/.test(sender)) {
      throw new Error('TWILIO_WHATSAPP_NUMBER must be in whatsapp:+<E.164> format.');
    }

    const rawSender = sender.replace(/^whatsapp:/i, '');
    const incomingNumbers = await client.incomingPhoneNumbers.list({ limit: 100 });
    const foundSender = incomingNumbers.find((number) => number.phoneNumber === rawSender);

    if (foundSender || rawSender === '+14155238886') {
      printSuccess('WhatsApp Number', 'Approved & Active');
      return;
    }

    throw new Error('Sender not found in account phone numbers. Verify that the WhatsApp sender is approved in Twilio.');
  } catch (error) {
    printFailure('WhatsApp Number', error);
  }
}

async function testSendWhatsappMessage(client) {
  try {
    const from = sanitizeWhatsAppNumber(requireEnv('TWILIO_WHATSAPP_NUMBER'));
    const to = normalizeWhatsappNumber(requireEnv('TEST_PHONE_NUMBER'));
    const message = await client.messages.create({
      from,
      to,
      body: 'Aksh AI Twilio Test - Working! ✅',
    });

    printSuccess('WhatsApp Send', `Message SID: ${message.sid} to ${maskPhoneNumber(to)}`);
    return message.sid;
  } catch (error) {
    printFailure('WhatsApp Send', error);
    return null;
  }
}

async function testMessageStatus(client, messageSid) {
  try {
    if (!messageSid) {
      throw new Error('Message SID unavailable because send step did not succeed.');
    }

    await new Promise((resolve) => setTimeout(resolve, 3000));
    const message = await client.messages(messageSid).fetch();
    printSuccess('Message Status', message.status);
  } catch (error) {
    const message = error && error.message ? error.message : String(error);
    console.log(`❌ Status Check Failed: ${message}`);
  }
}

async function main() {
  const accountSid = requireEnv('TWILIO_ACCOUNT_SID');
  const authToken = requireEnv('TWILIO_AUTH_TOKEN');
  const client = twilio(accountSid, authToken);

  await testTwilioAccount(client);
  await testWhatsappNumber(client);
  const messageSid = await testSendWhatsappMessage(client);
  await testMessageStatus(client, messageSid);
}

main().catch((error) => {
  const message = error && error.message ? error.message : String(error);
  console.error(`❌ Twilio Live Test Runner - Failed: ${message}`);
  process.exitCode = 1;
});
