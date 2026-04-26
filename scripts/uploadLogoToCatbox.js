const fs = require('fs');
const path = require('path');

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
  body.set('reqtype', 'fileupload');
  body.set('fileToUpload', new Blob([imageBuffer], { type: 'image/png' }), 'kash-ai-logo.png');

  const response = await fetch('https://catbox.moe/user/api.php', {
    method: 'POST',
    body,
  });
  const text = (await response.text()).trim();

  if (!response.ok || !text.startsWith('https://')) {
    throw new Error(`Catbox upload failed: ${text}`);
  }

  upsertEnvValue(envPath, 'KASH_AI_LOGO_URL', text);
  console.log(text);
}

uploadLogo().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
