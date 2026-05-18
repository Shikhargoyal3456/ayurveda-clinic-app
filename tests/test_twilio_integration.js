const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');

function loadWithMocks(modulePath, mocks) {
  const resolvedPath = require.resolve(modulePath);
  const originalLoad = Module._load;
  delete require.cache[resolvedPath];

  Module._load = function patchedLoad(request, parent, isMain) {
    if (Object.prototype.hasOwnProperty.call(mocks, request)) {
      return mocks[request];
    }
    return originalLoad(request, parent, isMain);
  };

  try {
    return require(resolvedPath);
  } finally {
    Module._load = originalLoad;
  }
}

function buildTwilioMock({ createImpl, webhookImpl } = {}) {
  const messages = {
    create: createImpl || (async (payload) => ({
      sid: process.env.TWILIO_TEST_MESSAGE_SID || 'SM_TEST',
      status: 'queued',
      from: payload.from,
      to: payload.to,
      body: payload.body,
    })),
  };

  const factory = () => ({ messages });
  factory.webhook = webhookImpl || (() => (req, res, next) => next());
  return factory;
}

function buildConfigMock(overrides = {}) {
  return {
    config: {
      twilioAccountSid: process.env.TWILIO_TEST_ACCOUNT_SID || 'AC_TEST',
      twilioAuthToken: process.env.TWILIO_TEST_AUTH_TOKEN || 'test-auth-token',
      twilioWhatsappNumber: process.env.TWILIO_TEST_WHATSAPP_NUMBER || 'whatsapp:+14155238886',
      twilioPrescriptionContentSid: process.env.TWILIO_TEST_CONTENT_SID || '',
      kashAiLogoUrl: '',
      publicUrl: '',
      logoMediaPath: '/static/images/kash-ai-logo.png',
      ...overrides,
    },
  };
}

test('normalizeWhatsappNumber normalizes supported Indian formats', () => {
  const service = loadWithMocks(path.resolve(__dirname, '../src/services/twilioService.js'), {
    twilio: buildTwilioMock(),
    '../config': buildConfigMock(),
  });

  assert.equal(service.normalizeWhatsappNumber('9350397175'), 'whatsapp:+919350397175');
  assert.equal(service.normalizeWhatsappNumber('919350397175'), 'whatsapp:+919350397175');
  assert.equal(service.normalizeWhatsappNumber('+919350397175'), 'whatsapp:+919350397175');
});

test('sendWhatsAppChunks returns partial failure results without throwing', async () => {
  const attempts = [];
  const service = loadWithMocks(path.resolve(__dirname, '../src/services/twilioService.js'), {
    twilio: buildTwilioMock({
      createImpl: async (payload) => {
        attempts.push(payload.body);
        if (payload.body.includes('Second chunk')) {
          throw new Error('Chunk rejected');
        }
        return {
          sid: `SM_${attempts.length}`,
          status: 'sent',
          from: payload.from,
          to: payload.to,
          body: payload.body,
        };
      },
    }),
    '../config': buildConfigMock(),
  });

  const body = 'First chunk text.\n\nSecond chunk text that fails.\n\nThird chunk text.';
  const results = await service.sendWhatsAppChunks({ to: '9350397175', body, maxLength: 25 });

  assert.equal(results.length, 3);
  assert.equal(results[0].success, true);
  assert.equal(results[1].success, false);
  assert.match(results[1].error, /Chunk rejected/);
  assert.equal(results[2].success, true);
});

test('webhook signature validation accepts valid signatures and rejects invalid ones', async () => {
  process.env.TWILIO_AUTH_TOKEN = process.env.TWILIO_TEST_AUTH_TOKEN || 'test-auth-token';

  let receivedToken = null;
  const validMiddlewareFactory = (token) => {
    receivedToken = token;
    return (req, res, next) => next();
  };

  const routeModule = loadWithMocks(path.resolve(__dirname, '../src/routes/webhookRoutes.js'), {
    twilio: Object.assign(() => ({}), { webhook: validMiddlewareFactory }),
    '../controllers/webhookController': { handleWhatsAppWebhook: (req, res) => res.status(200).json({ ok: true }) },
  });

  const validMiddleware = routeModule.createTwilioWebhookValidationMiddleware();
  await new Promise((resolve, reject) => {
    validMiddleware({}, {}, (error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
  assert.equal(receivedToken, process.env.TWILIO_AUTH_TOKEN);

  const invalidRouteModule = loadWithMocks(path.resolve(__dirname, '../src/routes/webhookRoutes.js'), {
    twilio: Object.assign(() => ({}), {
      webhook: () => (req, res, next) => next(new Error('Invalid signature')),
    }),
    '../controllers/webhookController': { handleWhatsAppWebhook: () => null },
  });

  const invalidMiddleware = invalidRouteModule.createTwilioWebhookValidationMiddleware();
  const response = {
    statusCode: null,
    payload: null,
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(body) {
      this.payload = body;
      return this;
    },
  };

  await new Promise((resolve) => {
    invalidMiddleware({}, response, () => resolve());
    setImmediate(resolve);
  });

  assert.equal(response.statusCode, 403);
  assert.deepEqual(response.payload, { error: 'Invalid Twilio signature.' });
});

test('sendWhatsAppText forms the outbound WhatsApp payload correctly', async () => {
  let capturedPayload = null;
  const service = loadWithMocks(path.resolve(__dirname, '../src/services/twilioService.js'), {
    twilio: buildTwilioMock({
      createImpl: async (payload) => {
        capturedPayload = payload;
        return {
          sid: 'SM_PAYLOAD',
          status: 'queued',
          from: payload.from,
          to: payload.to,
          body: payload.body,
        };
      },
    }),
    '../config': buildConfigMock({
      twilioWhatsappNumber: process.env.TWILIO_TEST_WHATSAPP_NUMBER || 'whatsapp:+14155238886',
    }),
  });

  await service.sendWhatsAppText({ to: '9350397175', body: 'hello' });

  assert.deepEqual(capturedPayload, {
    from: process.env.TWILIO_TEST_WHATSAPP_NUMBER || 'whatsapp:+14155238886',
    to: 'whatsapp:+919350397175',
    body: 'hello',
  });
});
