const { getDatabase } = require('../models/database');
const { pingRedis, getRedisStatus } = require('../services/redisService');

async function healthCheck(req, res) {
  const report = {
    status: 'ok',
    api: 'ok',
    database: 'unknown',
    redis: {
      status: 'unknown',
      available: false,
      disabledFeatures: [],
    },
    timestamp: new Date().toISOString(),
  };

  try {
    getDatabase().prepare('SELECT 1').get();
    report.database = 'ok';
  } catch (error) {
    report.status = 'degraded';
    report.database = 'error';
    report.databaseError = error.message;
  }

  try {
    await pingRedis();
    report.redis = getRedisStatus();
  } catch (error) {
    report.redis = {
      ...getRedisStatus(),
      status: 'error',
      available: false,
      lastError: error.message,
    };
  }

  res.status(report.status === 'ok' ? 200 : 503).json(report);
}

module.exports = { healthCheck };
