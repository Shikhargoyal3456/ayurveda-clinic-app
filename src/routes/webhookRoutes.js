const express = require('express');
const { handleWhatsAppWebhook } = require('../controllers/webhookController');

const router = express.Router();

router.post('/whatsapp', handleWhatsAppWebhook);

module.exports = router;
