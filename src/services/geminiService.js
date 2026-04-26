const { GoogleGenerativeAI } = require('@google/generative-ai');
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

let genAI;

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
Please consult your doctor or a qualified healthcare professional 
before making any changes to your medication or treatment plan. 
Your health is important to us! 🌿 - Kash AI Team"`;

function getGeminiClient() {
  if (!config.geminiApiKey) {
    throw new Error('GEMINI_API_KEY is not configured.');
  }
  if (!genAI) {
    genAI = new GoogleGenerativeAI(config.geminiApiKey);
  }
  return genAI;
}

async function tryGeminiWithFallback(contents) {
  const client = getGeminiClient();

  for (const modelName of GEMINI_MODELS) {
    try {
      const model = client.getGenerativeModel({ model: modelName });
      const result = await model.generateContent(contents);
      console.log(`✅ Gemini responded using: ${modelName}`);
      return result.response.text();
    } catch (err) {
      console.warn(`⚠️ Model ${modelName} failed: ${err.message}`);
      continue;
    }
  }

  throw new Error('All Gemini models unavailable. Please try again later.');
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
  const text = await tryGeminiWithFallback(contents);
  return text.trim();
}

async function analyzePrescriptionImage(imageBase64, mimeType) {
  if (!imageBase64) {
    throw new Error('Prescription image is required.');
  }

  const text = await tryGeminiWithFallback([
    PRESCRIPTION_IMAGE_PROMPT,
    {
      inlineData: {
        data: imageBase64,
        mimeType: mimeType || 'image/jpeg',
      },
    },
  ]);

  return text.trim();
}

module.exports = {
  GEMINI_MODELS,
  analyzePrescriptionImage,
  answerPatientQuery,
  generateAIReply,
  tryGeminiWithFallback,
};
