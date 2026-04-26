const express = require('express');
const { addPatient, getPatient } = require('../controllers/patientController');
const { listPatientPrescriptions } = require('../controllers/prescriptionController');

const router = express.Router();

router.post('/', addPatient);
router.get('/:id', getPatient);
router.get('/:id/prescriptions', listPatientPrescriptions);

module.exports = router;
