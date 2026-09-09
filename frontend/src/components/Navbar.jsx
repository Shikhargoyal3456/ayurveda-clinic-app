import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LayoutDashboard, ShieldCheck, HeartPulse, LogOut, Pill, Bot, Sparkles } from 'lucide-react';

export default function Navbar() {
  const { user, isLoggedIn, logout, getDashboardPath } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const dashboardPath = getDashboardPath();

  const getDashboardIcon = () => {
    if (!user) return <LayoutDashboard size={15} />;
    if (user.role === 'admin') return <ShieldCheck size={15} />;
    if (user.role === 'patient') return <HeartPulse size={15} />;
    return <LayoutDashboard size={15} />;
  };

  const getDashboardLabel = () => {
    if (!user) return 'Dashboard';
    if (user.role === 'admin') return 'Admin Console';
    if (user.role === 'patient') return 'Patient Hub';
    return 'Doctor Portal';
  };

  return (
    <>
      <header style={{ 
        height: '68px',
        width: '100%',
        boxSizing: 'border-box',
        padding: '0 32px', 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        background: 'rgba(11, 21, 18, 0.98)', 
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(16, 185, 129, 0.22)', 
        position: 'fixed', 
        top: 0, 
        left: 0,
        right: 0,
        zIndex: 1000,
        boxShadow: '0 4px 24px rgba(0, 0, 0, 0.45)'
      }}>
      {/* Brand Logo & Subtitle */}
      <Link to="/" style={{ display: 'flex', alignItems: 'baseline', gap: '8px', textDecoration: 'none' }}>
        <span style={{ fontSize: '1.4rem', fontWeight: '800', color: '#F4EEE1', letterSpacing: '-0.02em' }}>Kash AI</span>
        <span style={{ fontSize: '0.85rem', color: 'rgba(244, 238, 225, 0.5)', fontWeight: '500' }}>Healthcare intelligence</span>
      </Link>

      {/* Public Navigation Menus (NO Dashboard links for guests) */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <Link 
          to="/" 
          style={{ 
            fontSize: '0.9rem', fontWeight: '600', textDecoration: 'none',
            color: location.pathname === '/' ? '#E8B24A' : 'rgba(244, 238, 225, 0.75)'
          }}
        >
          Features
        </Link>
        <Link 
          to="/doctor" 
          style={{ 
            display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.9rem', fontWeight: '600', textDecoration: 'none',
            color: location.pathname === '/doctor' ? '#E8B24A' : 'rgba(244, 238, 225, 0.75)'
          }}
        >
          <Bot size={15} color="#2FC98A" /> AI Doctor
        </Link>
        <Link 
          to="/order-medicines" 
          style={{ 
            display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.9rem', fontWeight: '600', textDecoration: 'none',
            color: location.pathname === '/order-medicines' ? '#E8B24A' : 'rgba(244, 238, 225, 0.75)'
          }}
        >
          <Pill size={15} color="#06B6D4" /> Order Medicines
        </Link>
        <Link 
          to="/ocr-decoder" 
          style={{ 
            display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.9rem', fontWeight: '600', textDecoration: 'none',
            color: location.pathname === '/ocr-decoder' ? '#E8B24A' : 'rgba(244, 238, 225, 0.75)'
          }}
        >
          <Sparkles size={15} color="#E8B24A" /> AI OCR Reader
        </Link>
      </nav>

      {/* Auth Action Buttons (Updates on Login / Logout) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {isLoggedIn ? (
          <>
            {/* Automatic Dashboard Link Based on User Role */}
            <Link 
              to={dashboardPath}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '9px 18px', borderRadius: '999px',
                background: 'rgba(47, 201, 138, 0.12)', border: '1px solid rgba(47, 201, 138, 0.4)',
                color: '#2FC98A', textDecoration: 'none', fontWeight: '700', fontSize: '0.88rem'
              }}
            >
              {getDashboardIcon()} {getDashboardLabel()}
            </Link>

            {/* Logout Button */}
            <button
              type="button"
              onClick={handleLogout}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '9px 16px', borderRadius: '999px',
                background: 'rgba(244, 63, 94, 0.12)', border: '1px solid rgba(244, 63, 94, 0.3)',
                color: '#F43F5E', fontWeight: '700', fontSize: '0.88rem', cursor: 'pointer'
              }}
            >
              <LogOut size={15} /> Logout
            </button>
          </>
        ) : (
          <>
            <Link to="/login" style={{ color: 'rgba(244, 238, 225, 0.85)', textDecoration: 'none', fontWeight: '600', fontSize: '0.92rem' }}>
              Login
            </Link>
            <Link 
              to="/login" 
              style={{ 
                padding: '10px 22px', borderRadius: '999px', background: 'linear-gradient(135deg, #E8B24A, #C6871B)', 
                color: '#17201C', textDecoration: 'none', fontWeight: '700', fontSize: '0.92rem',
                boxShadow: '0 8px 20px rgba(232, 178, 74, 0.25)'
              }}
            >
              Sign Up
            </Link>
          </>
        )}
      </div>
    </header>
    {/* Static header spacer: locks document flow so content sticks flush below fixed header */}
    <div style={{ height: '68px', width: '100%', flexShrink: 0 }} aria-hidden="true" />
    </>
  );
}
