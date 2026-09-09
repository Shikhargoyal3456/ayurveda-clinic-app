import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Home from './pages/Home';
import Login from './pages/Login';
import DoctorDashboard from './pages/DoctorDashboard';
import AdminDashboard from './pages/AdminDashboard';
import PatientDashboard from './pages/PatientDashboard';
import OrderMedicines from './pages/OrderMedicines';
import OCRDecoderPage from './pages/OCRDecoderPage';
import VoiceConsultationPage from './pages/VoiceConsultationPage';
import DeviceCheckPage from './pages/DeviceCheckPage';
import AddPatientPage from './pages/AddPatientPage';
import DoctorAICopilot from './components/DoctorAICopilot';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
          <Navbar />
          <main style={{ flex: 1 }}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/doctor" element={<DoctorDashboard />} />
              <Route path="/admin" element={<AdminDashboard />} />
              <Route path="/patient" element={<PatientDashboard />} />
              <Route path="/order-medicines" element={<OrderMedicines />} />
              <Route path="/ocr-decoder" element={<OCRDecoderPage />} />
              <Route path="/consultation/voice" element={<VoiceConsultationPage />} />
              <Route path="/device-check" element={<DeviceCheckPage />} />
              <Route path="/new/patients/add" element={<AddPatientPage />} />
              <Route path="/patients/add" element={<AddPatientPage />} />
            </Routes>
          </main>
          <Footer />
          <DoctorAICopilot />
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

