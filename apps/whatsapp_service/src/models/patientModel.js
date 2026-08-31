const { getDatabase } = require('./database');

function createPatient({ name, phone, medicalConditions = '' }) {
  const statement = getDatabase().prepare(`
    INSERT INTO patients (name, phone, medical_conditions)
    VALUES (@name, @phone, @medicalConditions)
  `);
  const result = statement.run({ name, phone, medicalConditions });
  return findPatientById(result.lastInsertRowid);
}

function findPatientById(id) {
  return getDatabase()
    .prepare('SELECT id, name, phone, medical_conditions AS medicalConditions, created_at AS createdAt FROM patients WHERE id = ?')
    .get(id);
}

function findPatientByPhone(phone) {
  return getDatabase()
    .prepare('SELECT id, name, phone, medical_conditions AS medicalConditions, created_at AS createdAt FROM patients WHERE phone = ?')
    .get(phone);
}

function findPatientByName(name) {
  return getDatabase()
    .prepare('SELECT id, name, phone, medical_conditions AS medicalConditions, created_at AS createdAt FROM patients WHERE lower(name) = lower(?) ORDER BY id DESC LIMIT 1')
    .get(name);
}

module.exports = { createPatient, findPatientById, findPatientByPhone, findPatientByName };
