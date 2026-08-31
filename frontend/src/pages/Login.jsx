import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Stethoscope, ShieldCheck, Clock, Key, User, Eye, EyeOff, LogIn, HeartPulse } from 'lucide-react';

export default function Login() {
  const [role, setRole] = useState('doctor');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    const effectiveRole = identifier.toLowerCase().includes('admin') ? 'admin' : role;
    const targetPath = login(effectiveRole, identifier);
    navigate(targetPath);
  };

  return (
    <div style={{ minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '32px 16px' }}>
      <div className="glass-card" style={{ width: '100%', maxWidth: '520px', padding: '40px', display: 'flex', flexDirection: 'column', gap: '22px', position: 'relative' }}>
        
        {/* Top Header */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 16px', borderRadius: '20px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#10B981', fontSize: '0.85rem', fontWeight: '700', marginBottom: '12px' }}>
            <Stethoscope size={16} /> Kash AI Platform
          </div>
          <h1 style={{ fontSize: '2.2rem', fontWeight: '800', color: '#FFFFFF', margin: '0 0 6px' }}>Login to Kash AI</h1>
          <p style={{ color: '#94A3B8', fontSize: '0.95rem' }}>Secure clinical & patient healthcare portal</p>
        </div>

        {/* Security Badge */}
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px', padding: '10px 16px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', fontSize: '0.85rem', color: '#94A3B8' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><ShieldCheck size={14} color="#10B981" /> 256-bit Encryption</span>
          <span>•</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Clock size={14} color="#06B6D4" /> Session: 30 min</span>
        </div>

        {/* Click-wise Role Switcher */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontWeight: '700', fontSize: '0.82rem', color: '#CBD5E1', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Choose Account Workspace</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', background: 'rgba(0, 0, 0, 0.25)', padding: '6px', borderRadius: '14px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
            <button
              type="button"
              onClick={() => setRole('doctor')}
              style={{
                padding: '12px 16px', borderRadius: '10px', border: 'none',
                background: role === 'doctor' ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(6, 182, 212, 0.2))' : 'transparent',
                border: role === 'doctor' ? '1px solid rgba(16, 185, 129, 0.5)' : '1px solid transparent',
                color: role === 'doctor' ? '#FFFFFF' : '#94A3B8',
                fontWeight: '700', fontSize: '0.95rem', cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                transition: 'all 0.2s ease'
              }}
            >
              <Stethoscope size={18} /> Doctor
            </button>
            <button
              type="button"
              onClick={() => setRole('patient')}
              style={{
                padding: '12px 16px', borderRadius: '10px', border: 'none',
                background: role === 'patient' ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(6, 182, 212, 0.2))' : 'transparent',
                border: role === 'patient' ? '1px solid rgba(16, 185, 129, 0.5)' : '1px solid transparent',
                color: role === 'patient' ? '#FFFFFF' : '#94A3B8',
                fontWeight: '700', fontSize: '0.95rem', cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                transition: 'all 0.2s ease'
              }}
            >
              <HeartPulse size={18} /> Patient
            </button>
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontWeight: '600', fontSize: '0.88rem', color: '#E2E8F0', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <User size={14} color="#10B981" /> Email or Username
            </label>
            <input
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder={role === 'doctor' ? 'dr_demo or doctor@kashai.com' : 'patient@gmail.com or phone'}
              required
              style={{
                width: '100%', padding: '14px 16px', borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.12)',
                color: '#FFFFFF', fontSize: '0.95rem', outline: 'none'
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontWeight: '600', fontSize: '0.88rem', color: '#E2E8F0', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Key size={14} color="#10B981" /> Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{
                  width: '100%', padding: '14px 16px', borderRadius: '12px',
                  background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#FFFFFF', fontSize: '0.95rem', outline: 'none'
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{ position: 'absolute', right: '14px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.88rem', color: '#94A3B8' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                style={{ accentColor: '#10B981' }}
              /> Remember me
            </label>
            <a href="#" style={{ color: '#10B981', textDecoration: 'none', fontWeight: '600' }}>Forgot Password?</a>
          </div>

          <button type="submit" className="btn-primary" style={{ padding: '14px', justifyContent: 'center', fontSize: '1rem', marginTop: '4px' }}>
            <LogIn size={18} /> Sign In to {role === 'doctor' ? 'Doctor Workspace' : 'Patient Portal'}
          </button>
        </form>
      </div>
    </div>
  );
}
