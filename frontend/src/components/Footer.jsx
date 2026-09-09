import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function Footer() {
  const location = useLocation();
  if (['/doctor', '/admin'].includes(location.pathname)) {
    return null;
  }
  return (
    <footer style={{
      borderTop: '1px solid rgba(255, 255, 255, 0.08)',
      background: '#070E0B',
      padding: '50px 32px 28px',
      color: 'rgba(244, 238, 225, 0.65)',
      fontSize: '0.9rem'
    }}>
      <div style={{ maxWidth: '1180px', margin: '0 auto', display: 'grid', gridTemplateColumns: '1.5fr repeat(3, 1fr)', gap: '40px', marginBottom: '40px' }}>
        
        {/* Brand Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ fontSize: '1.3rem', fontWeight: '800', color: '#F4EEE1', letterSpacing: '-0.02em' }}>Kash AI</div>
          <p style={{ color: 'rgba(244, 238, 225, 0.6)', fontSize: '0.9rem', margin: 0, maxWidth: '280px', lineHeight: '1.5' }}>
            AI-powered healthcare intelligence for modern India.
          </p>
        </div>

        {/* Platform Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h4 style={{ color: '#F4EEE1', fontSize: '0.9rem', fontWeight: '700', margin: '0 0 6px' }}>Platform</h4>
          <Link to="/" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Features</Link>
          <Link to="/doctor" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Consult Doctors</Link>
          <Link to="/order-medicines" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Lab Tests</Link>
        </div>

        {/* Company Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h4 style={{ color: '#F4EEE1', fontSize: '0.9rem', fontWeight: '700', margin: '0 0 6px' }}>Company</h4>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Business Hub</a>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Trust Center</a>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Community</a>
        </div>

        {/* Support Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h4 style={{ color: '#F4EEE1', fontSize: '0.9rem', fontWeight: '700', margin: '0 0 6px' }}>Support</h4>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Help Center</a>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Privacy Policy</a>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.65)', textDecoration: 'none', fontSize: '0.88rem' }}>Pricing</a>
        </div>

      </div>

      {/* Bottom Copyright Row */}
      <div style={{ maxWidth: '1180px', margin: '0 auto', paddingTop: '20px', borderTop: '1px solid rgba(255, 255, 255, 0.05)', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '16px', fontSize: '0.85rem', color: 'rgba(244, 238, 225, 0.5)' }}>
        <div>© 2026 KASH AI. All rights reserved.</div>
        <div style={{ display: 'flex', gap: '20px' }}>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.5)', textDecoration: 'none' }}>Terms & Conditions</a>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.5)', textDecoration: 'none' }}>Privacy Policy</a>
          <a href="#" style={{ color: 'rgba(244, 238, 225, 0.5)', textDecoration: 'none' }}>Contact</a>
        </div>
      </div>
    </footer>
  );
}
