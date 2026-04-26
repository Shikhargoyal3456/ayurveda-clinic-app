const express = require('express');
const fs = require('fs');
const {
  createPrescriptionAndNotify,
  scanPrescriptionImage,
} = require('../controllers/prescriptionController');
const { config } = require('../config');

const router = express.Router();
let upload;

try {
  const multer = require('multer');
  const storage = config.testMode
    ? multer.diskStorage({
      destination: (req, file, callback) => {
        fs.mkdirSync(config.testUploadsDir, { recursive: true });
        callback(null, config.testUploadsDir);
      },
      filename: (req, file, callback) => {
        const safeName = `${Date.now()}-${String(file.originalname || 'upload').replace(/[^a-zA-Z0-9._-]/g, '_')}`;
        callback(null, safeName);
      },
    })
    : multer.memoryStorage();
  upload = multer({
    storage,
    limits: { fileSize: 12 * 1024 * 1024 },
    fileFilter: (req, file, callback) => {
      const allowed = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
      const allowedExtensions = /\.(jpe?g|png|webp|pdf)$/i;
      if (!allowed.includes(file.mimetype) && !allowedExtensions.test(file.originalname || '')) {
        return callback(new Error('Only jpg, png, webp, and pdf prescription files are supported.'));
      }
      return callback(null, true);
    },
  });
} catch (error) {
  upload = null;
}

router.post('/', createPrescriptionAndNotify);
router.post('/scan', (req, res, next) => {
  if (!upload) {
    return res.status(503).json({ error: 'File upload support is unavailable. Please install multer and restart the server.' });
  }
  return upload.single('image')(req, res, next);
}, scanPrescriptionImage);

module.exports = router;
