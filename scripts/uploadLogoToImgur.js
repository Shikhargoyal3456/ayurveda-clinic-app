const fs = require('fs');
const path = require('path');

const IMGUR_CLIENT_ID = '546c25a59c58ad7';
const rootDir = path.resolve(__dirname, '..');
const logoPath = path.join(rootDir, 'public', 'images', 'kash-ai-logo.png');
const envPath = path.join(rootDir, '.env');

function upsertEnvValue(filePath, key, value) {
  const lines = fs.existsSync(filePath)
    ? fs.readFileSync(filePath, 'utf8').split(/\r?\n/)
    : [];

  let found = false;
  const updated = lines.map((line) => {
    if (line.match(new RegExp(`^\\s*${key}\\s*=`))) {
      found = true;
      return `${key}=${value}`;
    }
    return line;
  });

  if (!found) {
    if (updated.length && updated[updated.length - 1] !== '') {
      updated.push('');
    }
    updated.push('# Permanent public media URL for Kash AI WhatsApp logo');
    updated.push(`${key}=${value}`);
  }

  fs.writeFileSync(filePath, updated.join('\n'), 'utf8');
}

async function uploadLogo() {
  if (!fs.existsSync(logoPath)) {
    throw new Error(`Logo file not found: ${logoPath}`);
  }

  const imageBuffer = fs.readFileSync(logoPath);
  const body = new FormData();
  body.set('image', new Blob([imageBuffer], { type: 'image/png' }), 'kash-ai-logo.png');
  body.set('name', 'kash-ai-logo.png');
  body.set('title', 'Kash AI Logo');

  const response = await fetch('https://api.imgur.com/3/image', {
    method: 'POST',
    headers: {
      Authorization: `Client-ID ${IMGUR_CLIENT_ID}`,
    },
    body,
  });

  const result = await response.json();
  if (!response.ok || !result.success || !result.data?.link) {
    throw new Error(`Imgur upload failed: ${JSON.stringify(result)}`);
  }

  upsertEnvValue(envPath, 'KASH_AI_LOGO_URL', result.data.link);
  console.log(result.data.link);
}

uploadLogo().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
