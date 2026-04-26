const express = require('express');
const { scheduleReminderForPrescription } = require('../controllers/prescriptionController');

const router = express.Router();

router.post('/', scheduleReminderForPrescription);

module.exports = router;
