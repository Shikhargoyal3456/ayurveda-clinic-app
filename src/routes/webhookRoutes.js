const express = require('express');
const twilio = require('twilio');
const { handleWhatsAppWebhook } = require('../controllers/webhookController');

const router = express.Router();

function createTwilioWebhookValidationMiddleware() {
  const authToken = process.env.TWILIO_AUTH_TOKEN || '';
  const validator = twilio.webhook(authToken);
  return (req, res, next) => validator(req, res, (error) => {
    if (!authToken || error) {
      return res.status(403).json({ error: 'Invalid Twilio signature.' });
    }
    return next();
  });
}

router.post('/whatsapp', createTwilioWebhookValidationMiddleware(), handleWhatsAppWebhook);

module.exports = router;
module.exports.createTwilioWebhookValidationMiddleware = createTwilioWebhookValidationMiddleware;
