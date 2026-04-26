const { getDatabase } = require('./database');

function createPrescription(prescription) {
  const statement = getDatabase().prepare(`
    INSERT INTO prescriptions (
      patient_id,
      medicine_name,
      dosage,
      frequency,
      duration,
      doctor_name,
      schedule
    )
    VALUES (
      @patientId,
      @medicineName,
      @dosage,
      @frequency,
      @duration,
      @doctorName,
      @schedule
    )
  `);
  const result = statement.run({
    ...prescription,
    schedule: Array.isArray(prescription.schedule) ? prescription.schedule.join(',') : prescription.schedule || '',
  });
  return findPrescriptionById(result.lastInsertRowid);
}

function findPrescriptionById(id) {
  return getDatabase()
    .prepare(`
      SELECT
        id,
        patient_id AS patientId,
        medicine_name AS medicineName,
        dosage,
        frequency,
        duration,
        doctor_name AS doctorName,
        schedule,
        created_at AS createdAt
      FROM prescriptions
      WHERE id = ?
    `)
    .get(id);
}

function listPrescriptionsForPatient(patientId) {
  return getDatabase()
    .prepare(`
      SELECT
        id,
        patient_id AS patientId,
        medicine_name AS medicineName,
        dosage,
        frequency,
        duration,
        doctor_name AS doctorName,
        schedule,
        created_at AS createdAt
      FROM prescriptions
      WHERE patient_id = ?
      ORDER BY created_at DESC
    `)
    .all(patientId);
}

module.exports = { createPrescription, findPrescriptionById, listPrescriptionsForPatient };
