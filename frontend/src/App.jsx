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
            </Routes>
          </main>
          <Footer />
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

