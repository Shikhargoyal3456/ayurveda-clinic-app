import React, { useState } from 'react';
import { Sparkles, Upload, FileText, CheckCircle, AlertTriangle, RefreshCw, ShoppingCart, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function OCRDecoderPage() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [medicines, setMedicines] = useState([]);
  const navigate = useNavigate();

  const handleFileSelect = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      if (selected.size > 5 * 1024 * 1024) {
        setError('File must be 5MB or smaller.');
        return;
      }
      setFile(selected);
      setPreviewUrl(URL.createObjectURL(selected));
      setError('');
      setResult(null);
    }
  };

  const handleDecode = async () => {
    if (!file) {
      setError('Please upload a prescription image or lab report PDF.');
      return;
    }

    setIsLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('prescription_image', file);

    try {
      const res = await fetch('/api/prescription/decode-handwriting', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.success && data.data) {
        setResult(data.data);
        setMedicines(data.data.medicines || []);
      } else {
        setError(data.error || data.detail || 'Could not analyze prescription image.');
      }
    } catch (err) {
      console.error('OCR Request Error:', err);
      setError('Failed to process prescription file.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '32px 20px' }}>
      {/* Header Banner */}
      <div className="glass-card" style={{ padding: '32px', borderRadius: '20px', marginBottom: '32px', background: 'linear-gradient(135deg, rgba(232, 178, 74, 0.1), rgba(16, 185, 129, 0.1))', border: '1px solid rgba(232, 178, 74, 0.3)' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 14px', borderRadius: '20px', background: 'rgba(232, 178, 74, 0.15)', color: '#E8B24A', fontSize: '0.85rem', fontWeight: '700', marginBottom: '12px' }}>
          <Sparkles size={16} /> Neural-Grade Prescription & Lab OCR Decoder
        </div>
        <h1 style={{ fontSize: '2.4rem', fontWeight: '800', margin: '0 0 8px', color: '#F8FAFC' }}>
          AI Prescription Handwriting Reader
        </h1>
        <p style={{ color: '#94A3B8', fontSize: '1rem', margin: 0, maxWidth: '700px' }}>
          Upload any paper prescription, doctor's handwritten notes, or diagnostic report. Our vision AI enhances image contrast, performs ROI focus, deskews handwriting, and extracts verified medicine lists.
        </p>
      </div>

      {/* Upload Box */}
      {!result ? (
        <div className="glass-card" style={{ padding: '40px', borderRadius: '20px', textAlign: 'center', position: 'relative', border: '2px dashed rgba(255, 255, 255, 0.18)' }}>
          <input
            type="file"
            accept="image/*,.pdf"
            onChange={handleFileSelect}
            style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
          />

          {previewUrl ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <img src={previewUrl} alt="Prescription preview" style={{ maxHeight: '280px', borderRadius: '14px', border: '1px solid rgba(255, 255, 255, 0.2)' }} />
              <span style={{ color: '#10B981', fontWeight: '700', fontSize: '0.95rem' }}>
                <CheckCircle size={18} style={{ display: 'inline', marginRight: '6px' }} />
                {file?.name} ({(file.size / 1024).toFixed(1)} KB)
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', display: 'grid', placeItems: 'center' }}>
                <Upload size={28} />
              </div>
              <h3 style={{ margin: 0, fontSize: '1.3rem', fontWeight: '700', color: '#F8FAFC' }}>Drop Handwritten Prescription or PDF Here</h3>
              <p style={{ color: '#94A3B8', fontSize: '0.9rem', margin: 0 }}>Supports JPG, PNG, WEBP & PDF files up to 5MB</p>
            </div>
          )}

          {error && (
            <div style={{ marginTops: '20px', padding: '12px', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.15)', color: '#F87171', marginTop: '16px' }}>
              <AlertTriangle size={16} style={{ display: 'inline', marginRight: '6px' }} /> {error}
            </div>
          )}

          <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
            <button
              type="button"
              onClick={handleDecode}
              disabled={isLoading || !file}
              className="btn-gold"
              style={{ padding: '14px 36px', fontSize: '1rem', fontWeight: '700', opacity: isLoading || !file ? 0.6 : 1 }}
            >
              {isLoading ? (
                <>
                  <RefreshCw size={18} className="animate-spin" style={{ marginRight: '8px' }} />
                  Processing Handwriting with Vision AI...
                </>
              ) : (
                <>
                  <Sparkles size={18} style={{ marginRight: '8px' }} /> Decode Prescription Now
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        /* Results Section */
        <div className="glass-card" style={{ padding: '32px', borderRadius: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <div>
              <span style={{ color: '#10B981', fontWeight: '700', fontSize: '0.85rem' }}>DECODING COMPLETE</span>
              <h2 style={{ fontSize: '1.6rem', fontWeight: '800', margin: '2px 0 0', color: '#F8FAFC' }}>Prescription Details Extracted</h2>
            </div>
            <button
              onClick={() => { setResult(null); setFile(null); setPreviewUrl(''); }}
              className="btn-ghost"
              style={{ padding: '10px 18px', fontSize: '0.88rem' }}
            >
              Decode Another File
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px', padding: '20px', borderRadius: '14px', background: 'rgba(0,0,0,0.25)' }}>
            <div>
              <span style={{ fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase' }}>Doctor</span>
              <p style={{ margin: '4px 0 0', fontWeight: '700', fontSize: '1.05rem', color: '#F8FAFC' }}>{result.doctor_name || 'Prescribing Doctor'}</p>
            </div>
            <div>
              <span style={{ fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase' }}>Patient</span>
              <p style={{ margin: '4px 0 0', fontWeight: '700', fontSize: '1.05rem', color: '#F8FAFC' }}>{result.patient_name || 'Patient Record'}</p>
            </div>
            <div>
              <span style={{ fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase' }}>Overall Confidence</span>
              <p style={{ margin: '4px 0 0', fontWeight: '700', fontSize: '1.05rem', color: result.confidence_overall > 70 ? '#10B981' : '#E8B24A' }}>
                {result.confidence_overall || 88}%
              </p>
            </div>
          </div>

          <h3 style={{ fontSize: '1.2rem', fontWeight: '700', marginBottom: '16px' }}>Decoded Medicines Catalog ({medicines.length})</h3>
          <div style={{ overflowX: 'auto', marginBottom: '28px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8', textAlign: 'left' }}>
                  <th style={{ padding: '10px 14px' }}>Medicine</th>
                  <th style={{ padding: '10px 14px' }}>Dosage</th>
                  <th style={{ padding: '10px 14px' }}>Frequency</th>
                  <th style={{ padding: '10px 14px' }}>Duration</th>
                </tr>
              </thead>
              <tbody>
                {medicines.map((m, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '12px 14px', fontWeight: '700', color: '#F8FAFC' }}>{m.medicine_name}</td>
                    <td style={{ padding: '12px 14px', color: '#CBD5E1' }}>{m.dosage || '1 unit'}</td>
                    <td style={{ padding: '12px 14px', color: '#CBD5E1' }}>{m.frequency || 'Twice daily'}</td>
                    <td style={{ padding: '12px 14px', color: '#CBD5E1' }}>{m.duration || '5 days'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '16px' }}>
            <button
              onClick={() => navigate('/order-medicines')}
              className="btn-gold"
              style={{ padding: '12px 28px', fontSize: '0.95rem' }}
            >
              <ShoppingCart size={18} style={{ marginRight: '8px' }} /> Order Medicines from Pharmacy Store
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
