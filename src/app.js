const path = require('path');
const express = require('express');
const cors = require('cors');
const morgan = require('morgan');

const { config } = require('./config');
const { initDatabase } = require('./models/database');
const patientRoutes = require('./routes/patientRoutes');
const prescriptionRoutes = require('./routes/prescriptionRoutes');
const reminderRoutes = require('./routes/reminderRoutes');
const webhookRoutes = require('./routes/webhookRoutes');
const healthRoutes = require('./routes/healthRoutes');
const { errorHandler, notFoundHandler } = require('./middleware/errorHandler');

initDatabase();

const app = express();

app.use(cors());
app.use(morgan(config.nodeEnv === 'production' ? 'combined' : 'dev'));
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false }));
app.use('/static', express.static(path.join(__dirname, '..', 'public')));
app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(config.publicDir, 'dashboard.html'));
});

app.use('/patients', patientRoutes);
app.use('/prescriptions', prescriptionRoutes);
app.use('/reminders', reminderRoutes);
app.use('/webhook', webhookRoutes);
app.use('/health', healthRoutes);

app.use(notFoundHandler);
app.use(errorHandler);

if (require.main === module) {
  app.listen(config.port, () => {
    console.log(`WhatsApp notification service listening on port ${config.port}`);
  });
}

module.exports = app;
