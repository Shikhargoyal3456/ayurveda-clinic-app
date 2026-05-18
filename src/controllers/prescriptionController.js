const {
  createPatient,
  findPatientById,
  findPatientByName,
  findPatientByPhone,
} = require('../models/patientModel');
const fs = require('fs');
const { createPrescription, findPrescriptionById, listPrescriptionsForPatient } = require('../models/prescriptionModel');
const { logMessage } = require('../models/messageLogModel');
const { analyzePrescriptionBuffer, GEMINI_UNAVAILABLE_MESSAGE, inferMimeType } = require('../services/prescriptionImageService');
const { buildPrescriptionMessage, formatDoctorName, sendPrescriptionNotification, sendWhatsAppChunks } = require('../services/twilioService');
const { scheduleMedicationReminders } = require('../queues/reminderQueue');

async function createPrescriptionAndNotify(req, res, next) {
  try {
    const patientId = req.body.patientId;
    const patientName = req.body.patientName;
    const patientPhone = req.body.patientPhone || req.body.phone;
    const medicalConditions = req.body.medicalConditions || req.body.condition || '';
    const medicineName = req.body.medicineName || req.body.medicine;
    const dosage = req.body.dosage;
    const frequency = req.body.frequency;
    const duration = req.body.duration;
    const doctorName = req.body.doctorName || req.body.doctor;
    const schedule = req.body.schedule || [];

    if ((!patientId && !patientName) || !medicineName || !dosage || !frequency || !duration || !doctorName) {
      return res.status(400).json({
        error: 'patientId or patientName, plus medicineName/medicine, dosage, frequency, duration, and doctorName/doctor are required.',
      });
    }

    let patient = null;
    if (patientId) {
      patient = findPatientById(patientId);
    } else if (patientPhone) {
      patient = findPatientByPhone(patientPhone);
      if (!patient && patientName) {
        patient = createPatient({ name: patientName, phone: patientPhone, medicalConditions });
      }
    } else {
      patient = findPatientByName(patientName);
    }
    if (!patient) {
      return res.status(404).json({ error: 'Patient not found.' });
    }

    const prescription = createPrescription({
      patientId: patient.id,
      medicineName,
      dosage,
      frequency,
      duration,
      doctorName,
      schedule,
    });

    const twilioMessage = await sendPrescriptionNotification({ patient, prescription });
    logMessage({
      patientId: patient.id,
      prescriptionId: prescription.id,
      direction: 'sent',
      fromNumber: twilioMessage.from,
      toNumber: twilioMessage.to,
      body: buildPrescriptionMessage({
        prescription: {
          patientName: patient.name,
          medicineName,
          dosage,
          frequency,
          duration,
        },
        doctorName: formatDoctorName(doctorName),
      }),
      providerMessageId: twilioMessage.sid,
      status: twilioMessage.status,
      metadata: { messageType: 'prescription' },
    });

    if (schedule.length || String(schedule).trim()) {
      const reminderResult = await scheduleMedicationReminders({ patient, prescription });
      if (reminderResult?.disabled) {
        logMessage({
          patientId: patient.id,
          prescriptionId: prescription.id,
          direction: 'sent',
          fromNumber: twilioMessage.from,
          toNumber: twilioMessage.to,
          body: 'Medication reminders were not scheduled because Redis is unavailable.',
          providerMessageId: '',
          status: 'skipped',
          metadata: { messageType: 'reminder_schedule_skipped', reason: reminderResult.reason, redis: reminderResult.redis },
        });
      }
    }

    return res.status(201).json({
      prescription,
      notification: {
        provider: 'twilio',
        messageSid: twilioMessage.sid,
        status: twilioMessage.status,
      },
    });
  } catch (error) {
    return next(error);
  }
}

async function listPatientPrescriptions(req, res, next) {
  try {
    const patient = findPatientById(req.params.id);
    if (!patient) {
      return res.status(404).json({ error: 'Patient not found.' });
    }
    const prescriptions = listPrescriptionsForPatient(patient.id);
    return res.json({ patient, prescriptions });
  } catch (error) {
    return next(error);
  }
}

async function scheduleReminderForPrescription(req, res, next) {
  try {
    const prescriptionId = req.body.prescriptionId;
    const patientId = req.body.patientId;
    const schedules = req.body.schedule || req.body.schedules || ['morning', 'night'];

    let prescription;
    if (prescriptionId) {
      prescription = findPrescriptionById(prescriptionId);
    } else if (patientId) {
      prescription = listPrescriptionsForPatient(patientId)[0];
    }

    if (!prescription) {
      return res.status(404).json({ error: 'Prescription not found. Provide prescriptionId or patientId.' });
    }

    const patient = findPatientById(prescription.patientId);
    if (!patient) {
      return res.status(404).json({ error: 'Patient not found for prescription.' });
    }

    const scheduledPrescription = {
      ...prescription,
      schedule: Array.isArray(schedules) ? schedules.join(',') : schedules,
    };
    const reminderResult = await scheduleMedicationReminders({ patient, prescription: scheduledPrescription });
    if (reminderResult?.disabled) {
      return res.status(202).json({
        queued: false,
        disabled: true,
        reason: reminderResult.reason,
        redis: reminderResult.redis,
      });
    }

    return res.status(201).json({
      queued: true,
      patientId: patient.id,
      prescriptionId: prescription.id,
      schedules: Array.isArray(schedules) ? schedules : String(schedules).split(',').map((item) => item.trim()).filter(Boolean),
    });
  } catch (error) {
    return next(error);
  }
}

async function scanPrescriptionImage(req, res, next) {
  try {
    const file = req.file;
    const phone = req.body.phone || req.body.patientPhone || '';

    if (!file) {
      return res.status(400).json({ error: 'Prescription image file is required.' });
    }
    const fileBuffer = file.buffer || (file.path ? fs.readFileSync(file.path) : null);
    if (!fileBuffer) {
      return res.status(400).json({ error: 'Prescription image file could not be read.' });
    }

    const result = await analyzePrescriptionBuffer({
      buffer: fileBuffer,
      mimeType: file.mimetype === 'application/octet-stream'
        ? inferMimeType(file.originalname)
        : file.mimetype,
    });

    let whatsapp = null;
    if (phone) {
      const patient = findPatientByPhone(phone) || findPatientByPhone(`whatsapp:${phone}`);
      const messages = await sendWhatsAppChunks({ to: phone, body: result.analysis });
      const successfulMessages = messages.filter((message) => message.success);
      successfulMessages.forEach((message) => {
        logMessage({
          patientId: patient?.id || null,
          direction: 'sent',
          fromNumber: message.from,
          toNumber: message.to,
          body: result.analysis,
          providerMessageId: message.sid,
          status: message.status,
          metadata: {
            provider: 'twilio',
            messageType: 'dashboard_prescription_analysis',
            chunkIndex: message.chunkIndex,
            chunkCount: messages.length,
            detected: result.detected,
            sourceFile: file.originalname,
          },
        });
      });
      whatsapp = {
        sent: successfulMessages.length > 0,
        chunks: successfulMessages.length,
        failedChunks: messages.filter((message) => !message.success).length,
        messageSids: successfulMessages.map((message) => message.sid),
      };
    }

    return res.json({
      detected: result.detected,
      analysis: result.analysis,
      mimeType: result.mimeType,
      bytesAnalyzed: result.bytes,
      whatsapp,
    });
  } catch (error) {
    if (req.file) {
      return res.status(503).json({ error: GEMINI_UNAVAILABLE_MESSAGE });
    }
    return next(error);
  }
}

module.exports = {
  createPrescriptionAndNotify,
  listPatientPrescriptions,
  scanPrescriptionImage,
  scheduleReminderForPrescription,
};
