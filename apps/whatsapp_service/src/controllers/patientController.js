const { createPatient, findPatientById } = require('../models/patientModel');

// SECURITY(authz): requires authentication + ownership check. Any caller can create a
// patient record. Once an auth scheme exists, require an authenticated clinician (req.user)
// and associate the new patient with that account.
async function addPatient(req, res, next) {
  try {
    const { name, phone } = req.body;
    const medicalConditions = req.body.medicalConditions || req.body.condition || '';
    if (!name || !phone) {
      return res.status(400).json({ error: 'name and phone are required.' });
    }

    const patient = createPatient({ name, phone, medicalConditions });
    return res.status(201).json({ patient });
  } catch (error) {
    if (error.code === 'SQLITE_CONSTRAINT_UNIQUE') {
      error.statusCode = 409;
      error.message = 'A patient with this phone number already exists.';
    }
    return next(error);
  }
}

// SECURITY(authz): requires authentication + ownership check. Any caller can read any
// patient by guessing/enumerating :id (IDOR). Once an auth scheme exists, require req.user
// and confirm the patient belongs to / is accessible by req.user.
async function getPatient(req, res, next) {
  try {
    const patient = findPatientById(req.params.id);
    if (!patient) {
      return res.status(404).json({ error: 'Patient not found.' });
    }
    return res.json({ patient });
  } catch (error) {
    return next(error);
  }
}

module.exports = { addPatient, getPatient };
