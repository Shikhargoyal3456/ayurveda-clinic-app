const { getDatabase } = require('./database');

function logMessage({
  patientId = null,
  prescriptionId = null,
  direction,
  fromNumber = '',
  toNumber = '',
  body,
  providerMessageId = '',
  status = 'created',
  metadata = {},
}) {
  const statement = getDatabase().prepare(`
    INSERT INTO message_logs (
      patient_id,
      prescription_id,
      direction,
      from_number,
      to_number,
      body,
      provider_message_id,
      status,
      metadata
    )
    VALUES (
      @patientId,
      @prescriptionId,
      @direction,
      @fromNumber,
      @toNumber,
      @body,
      @providerMessageId,
      @status,
      @metadata
    )
  `);

  const result = statement.run({
    patientId,
    prescriptionId,
    direction,
    fromNumber,
    toNumber,
    body,
    providerMessageId,
    status,
    metadata: JSON.stringify(metadata),
  });

  return result.lastInsertRowid;
}

module.exports = { logMessage };
