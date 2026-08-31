const { Queue } = require('bullmq');
const IORedis = require('ioredis');
const { config } = require('../config');

const reminderQueueName = 'medication-reminders';
const redisState = {
  status: 'unknown',
  available: false,
  disabledFeatures: [],
  lastError: '',
  lastCheckedAt: null,
  reconnectAttempts: 0,
};

function setRedisState(update) {
  Object.assign(redisState, update, { lastCheckedAt: new Date().toISOString() });
  redisState.disabledFeatures = redisState.available ? [] : ['medication_reminders'];
}

function redisRetryStrategy(times) {
  const delay = Math.min(30000, Math.max(250, 2 ** Math.min(times, 8) * 100));
  redisState.reconnectAttempts = times;
  console.warn(`[redis] unavailable; retrying in ${delay}ms (attempt ${times}). Queue-dependent features are disabled until Redis reconnects.`);
  return delay;
}

function createRedisConnection() {
  const connection = new IORedis(config.redisUrl, {
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
    retryStrategy: redisRetryStrategy,
  });
  connection.on('connect', () => {
    setRedisState({ status: 'connecting', available: false, lastError: '' });
  });
  connection.on('ready', () => {
    setRedisState({ status: 'ok', available: true, lastError: '' });
    console.info('[redis] connected. Queue-dependent features enabled.');
  });
  connection.on('error', (error) => {
    setRedisState({ status: 'error', available: false, lastError: error.message });
    console.warn(`[redis] connection error: ${error.message}. Queue-dependent features are disabled.`);
  });
  connection.on('end', () => {
    setRedisState({ status: 'disconnected', available: false });
    console.warn('[redis] connection ended. Queue-dependent features are disabled.');
  });
  return connection;
}

function createHealthRedisConnection() {
  return new IORedis(config.redisUrl, {
    connectTimeout: 3000,
    commandTimeout: 3000,
    lazyConnect: true,
    maxRetriesPerRequest: 1,
    enableReadyCheck: false,
    retryStrategy: () => null,
  });
}

function createReminderQueue() {
  return new Queue(reminderQueueName, {
    connection: createRedisConnection(),
  });
}

async function pingRedis() {
  const connection = createHealthRedisConnection();
  connection.on('error', () => {
    // The catch block records the health-check failure; this prevents ioredis from
    // emitting an unhandled error event while Redis is intentionally optional.
  });
  try {
    await connection.connect();
    const result = await connection.ping();
    const available = result === 'PONG';
    setRedisState({
      status: available ? 'ok' : 'error',
      available,
      lastError: available ? '' : `Unexpected ping result: ${result}`,
      reconnectAttempts: available ? 0 : redisState.reconnectAttempts,
    });
    return available;
  } catch (error) {
    setRedisState({ status: 'error', available: false, lastError: error.message });
    console.warn(`[redis] health check failed: ${error.message}. Queue-dependent features are disabled.`);
    return false;
  } finally {
    connection.disconnect();
  }
}

function getRedisStatus() {
  return { ...redisState, url: config.redisUrl.replace(/:\/\/[^@]*@/, '://***@') };
}

module.exports = {
  createRedisConnection,
  createReminderQueue,
  getRedisStatus,
  pingRedis,
  reminderQueueName,
};
