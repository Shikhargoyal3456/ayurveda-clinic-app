require('dotenv').config();

const { Worker } = require('bullmq');
const { createRedisConnection, reminderQueueName } = require('../services/redisService');
const { initDatabase } = require('../models/database');
const { findPatientById } = require('../models/patientModel');
const { findPrescriptionById } = require('../models/prescriptionModel');
const { logMessage } = require('../models/messageLogModel');
const { sendReminder } = require('../services/twilioService');

initDatabase();

const worker = new Worker(
  reminderQueueName,
  async (job) => {
    const { patientId, prescriptionId } = job.data;
    const patient = findPatientById(patientId);
    const prescription = findPrescriptionById(prescriptionId);

    if (!patient || !prescription) {
      throw new Error(`Missing patient or prescription for reminder job ${job.id}`);
    }

    const message = await sendReminder({ patient, prescription });
    logMessage({
      patientId: patient.id,
      prescriptionId: prescription.id,
      direction: 'sent',
      fromNumber: message.from,
      toNumber: message.to,
      body: `Time to take your ${prescription.medicineName} - ${prescription.dosage}`,
      providerMessageId: message.sid,
      status: message.status,
      metadata: { queueJobId: job.id, scheduleName: job.data.scheduleName },
    });
  },
  { connection: createRedisConnection() },
);

worker.on('completed', (job) => {
  console.log(`Reminder job completed: ${job.id}`);
});

worker.on('failed', (job, error) => {
  console.error(`Reminder job failed: ${job?.id}`, error);
});
