const { createReminderQueue, pingRedis, getRedisStatus } = require('../services/redisService');

const scheduleHours = {
  morning: 9,
  afternoon: 13,
  night: 21,
};

function nextRunDelay(scheduleName) {
  const hour = scheduleHours[scheduleName];
  if (hour === undefined) {
    throw new Error(`Unsupported schedule "${scheduleName}". Use morning, afternoon, or night.`);
  }

  const now = new Date();
  const next = new Date(now);
  next.setHours(hour, 0, 0, 0);
  if (next <= now) {
    next.setDate(next.getDate() + 1);
  }
  return next.getTime() - now.getTime();
}

async function scheduleMedicationReminders({ patient, prescription }) {
  const redisAvailable = await pingRedis();
  if (!redisAvailable) {
    const status = getRedisStatus();
    console.warn(`[reminders] Redis unavailable (${status.lastError || status.status}); skipping reminder scheduling for prescription ${prescription.id}.`);
    return {
      queued: false,
      disabled: true,
      reason: 'redis_unavailable',
      redis: status,
    };
  }

  const queue = createReminderQueue();
  const schedules = String(prescription.schedule || '')
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

  for (const scheduleName of schedules) {
    await queue.add(
      'send-medication-reminder',
      {
        scheduleName,
        patientId: patient.id,
        prescriptionId: prescription.id,
      },
      {
        delay: nextRunDelay(scheduleName),
        repeat: { pattern: cronForSchedule(scheduleName) },
        removeOnComplete: 100,
        removeOnFail: 100,
      },
    );
  }

  await queue.close();
  return {
    queued: true,
    disabled: false,
    count: schedules.length,
  };
}

function cronForSchedule(scheduleName) {
  const hour = scheduleHours[scheduleName];
  if (hour === undefined) {
    throw new Error(`Unsupported schedule "${scheduleName}". Use morning, afternoon, or night.`);
  }
  return `0 ${hour} * * *`;
}

module.exports = { scheduleMedicationReminders };
