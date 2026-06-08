const fs = require('fs');
const path = require('path');
const { GoogleGenAI } = require('@google/genai');
const { config } = require('../config');

const GEMINI_MODELS = [
  'gemini-2.5-flash',
  'gemini-flash-latest',
  'gemini-2.0-flash-001',
  'gemini-2.0-flash',
  'gemini-2.0-flash-lite-001',
  'gemini-2.0-flash-lite',
  'gemini-1.5-flash',
  'gemini-1.5-flash-8b',
];

const spendLedgerPath = path.join(__dirname, '..', '..', 'logs', 'node_ai_spend_guard.json');
let genAIClient;

const PRESCRIPTION_IMAGE_PROMPT = `You are Kash AI, a medical assistant for Kash AI Smart Clinic Platform.
Analyze this prescription image and provide:

1. 📋 MEDICINES DETECTED
   - List every medicine name found in the prescription
   - Include dosage if visible

2. 💊 MEDICINE DETAILS
   For each medicine provide:
   - What it is used for
   - Common dosage instructions
   - How it works (simple explanation)

3. ⚠️ SIDE EFFECTS
   For each medicine list:
   - Common side effects
   - Serious side effects to watch for
   - What to do if side effects occur

4. ✅ BENEFITS
   For each medicine:
   - Primary benefits
   - Expected improvement timeline
   - Best practices for taking it

5. 🥗 HEALTHY ADVICE
   - Diet recommendations while on these medicines
   - Lifestyle tips
   - Foods to avoid
   - Exercise recommendations if applicable

6. 💧 DRUG INTERACTIONS
   - Any known interactions between the detected medicines
   - Foods that interact with these medicines

Format the response in clean WhatsApp-friendly text with emojis.

IMPORTANT: Always end with this disclaimer:
"⚕️ IMPORTANT DISCLAIMER: This is AI-generated health information 
provided by Kash AI Smart Clinic Platform for educational purposes only. 
This is NOT a substitute for professional medical advice. 
Please review this with a qualified healthcare professional 
before making any changes to your medication or treatment plan. 
Your health is important to us! 🌿 - Kash AI Team"`;

function enforceAiBudget() {
  const budget = Math.max(0, Number(config.aiDailyBudgetUsd || 0));
  const callCost = Math.max(0, Number(config.aiMaxCostPerCallUsd || 0));
  if (!budget) return;

  const today = new Date().toISOString().slice(0, 10);
  let state = { date: today, estimated_spend_usd: 0, calls: 0 };

  if (fs.existsSync(spendLedgerPath)) {
    try {
      state = JSON.parse(fs.readFileSync(spendLedgerPath, 'utf8'));
    } catch (_err) {
      state = { date: today, estimated_spend_usd: 0, calls: 0 };
    }
  }

  if (state.date !== today) {
    state = { date: today, estimated_spend_usd: 0, calls: 0 };
  }

  const projectedSpend = Number(state.estimated_spend_usd || 0) + callCost;
  if (projectedSpend > budget) {
    throw new Error('AI daily spend cap reached. Please try again later.');
  }

  state.estimated_spend_usd = Number(projectedSpend.toFixed(4));
  state.calls = Number(state.calls || 0) + 1;
  fs.mkdirSync(path.dirname(spendLedgerPath), { recursive: true });
  fs.writeFileSync(spendLedgerPath, JSON.stringify(state, null, 2));
}

function isVertexAiConfigured() {
  return Boolean(config.vertexAiProject);
}

function getGenAIClient() {
  if (!isVertexAiConfigured()) {
    throw new Error('VERTEX_AI_PROJECT is not configured.');
  }

  if (!genAIClient) {
    genAIClient = new GoogleGenAI({
      vertexai: true,
      project: config.vertexAiProject,
      location: config.vertexAiLocation,
    });
  }

  return genAIClient;
}

function buildPart(item) {
  if (typeof item === 'string') {
    return item;
  }

  if (item && typeof item === 'object' && item.inlineData) {
    return {
      inlineData: {
        mimeType: item.inlineData.mimeType || 'image/jpeg',
        data: item.inlineData.data,
      },
    };
  }

  if (item && typeof item === 'object' && item.text) {
    return String(item.text);
  }

  return item;
}

function buildContents(input) {
  if (typeof input === 'string') {
    return input;
  }

  if (Array.isArray(input)) {
    return input.map(buildPart);
  }

  if (input && typeof input === 'object' && Array.isArray(input.contents)) {
    return input.contents;
  }

  return input;
}

function buildRequest(contents, options = {}) {
  return {
    model: options.model || config.geminiModel,
    contents: buildContents(contents),
  };
}

function extractTextFromResponse(response) {
  if (!response) {
    return '';
  }

  if (typeof response.text === 'string' && response.text.trim()) {
    return response.text.trim();
  }

  const candidates = Array.isArray(response.candidates) ? response.candidates : [];
  const parts = [];

  for (const candidate of candidates) {
    const contentParts = Array.isArray(candidate?.content?.parts) ? candidate.content.parts : [];
    for (const part of contentParts) {
      if (part?.text) {
        parts.push(String(part.text));
      }
    }
  }

  return parts.join('\n').trim();
}

async function generateContent(contents, options = {}) {
  enforceAiBudget();
  const client = getGenAIClient();
  const response = await client.models.generateContent(buildRequest(contents, options));
  return response;
}

function createAggregateResponse(chunks) {
  const text = chunks
    .map((chunk) => extractTextFromResponse(chunk))
    .filter(Boolean)
    .join('')
    .trim();

  return {
    text,
    candidates: chunks.flatMap((chunk) => (Array.isArray(chunk?.candidates) ? chunk.candidates : [])),
    chunks,
  };
}

async function streamContent(contents, options = {}) {
  enforceAiBudget();
  const client = getGenAIClient();
  const rawStream = await client.models.generateContentStream(buildRequest(contents, options));
  const seenChunks = [];
  let resolveResponse;
  let rejectResponse;

  const response = new Promise((resolve, reject) => {
    resolveResponse = resolve;
    rejectResponse = reject;
  });

  async function* wrappedStream() {
    try {
      for await (const chunk of rawStream) {
        seenChunks.push(chunk);
        yield chunk;
      }
      resolveResponse(createAggregateResponse(seenChunks));
    } catch (error) {
      rejectResponse(error);
      throw error;
    }
  }

  return {
    stream: wrappedStream(),
    response,
  };
}

async function tryGeminiWithFallback(contents, options = {}) {
  if (!isVertexAiConfigured()) {
    throw new Error('VERTEX_AI_PROJECT is not configured.');
  }

  let lastError;
  const modelNames = [
    options.model,
    config.geminiModel,
    config.geminiVisionModel,
    config.geminiVisionFallbackModel,
    ...GEMINI_MODELS,
  ].filter((value, index, array) => value && array.indexOf(value) === index);

  for (const modelName of modelNames) {
    try {
      const response = await generateContent(contents, { ...options, model: modelName });
      const text = extractTextFromResponse(response);
      if (!text) {
        throw new Error(`Empty response from model ${modelName}`);
      }
      console.log(`Vertex AI Gemini responded using model ${modelName}`);
      return text;
    } catch (err) {
      lastError = err;
      console.warn(`Model ${modelName} failed: ${err.message}`);
    }
  }

  throw new Error(`All Gemini models unavailable. ${lastError ? lastError.message : 'Please try again later.'}`);
}

async function answerPatientQuery({ patient, message }) {
  const prompt = `
You are a careful health assistant for a clinic. Answer in clear, simple language.
Do not diagnose. Do not change prescriptions. Encourage the patient to contact their doctor for urgent symptoms or medication changes.

Patient name: ${patient?.name || 'Unknown'}
Known medical conditions: ${patient?.medicalConditions || 'Not provided'}

Patient message:
${message}
`;

  return generateAIReply(prompt);
}

async function generateAIReply(contents) {
  const text = await tryGeminiWithFallback(contents, {
    model: config.geminiModel,
  });
  return text.trim();
}

async function analyzePrescriptionImage(imageBase64, mimeType) {
  if (!imageBase64) {
    throw new Error('Prescription image is required.');
  }

  const text = await tryGeminiWithFallback(
    [
      PRESCRIPTION_IMAGE_PROMPT,
      {
        inlineData: {
          data: imageBase64,
          mimeType: mimeType || 'image/jpeg',
        },
      },
    ],
    {
      model: config.geminiVisionModel || config.geminiModel,
    },
  );

  return text.trim();
}

module.exports = {
  GEMINI_MODELS,
  analyzePrescriptionImage,
  answerPatientQuery,
  extractTextFromResponse,
  generateAIReply,
  generateContent,
  isVertexAiConfigured,
  streamContent,
  tryGeminiWithFallback,
};
