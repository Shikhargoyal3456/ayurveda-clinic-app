import React from 'react';
import { Link } from 'react-router-dom';
import { Mic, Brain, MessageSquare, ShieldAlert } from 'lucide-react';

export default function Home() {
  return (
    <div className="landing-wrapper" style={{ maxWidth: '1180px', margin: '0 auto', padding: '20px 24px 60px' }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,500;1,9..144,600&family=Space+Grotesk:wght@500;600;700&display=swap');

        /* ── HERO ── */
        .landing-hero {
          display: grid;
          grid-template-columns: 1.05fr 0.95fr;
          align-items: center;
          gap: 40px;
          padding: 40px 0 32px;
          margin-bottom: 24px;
        }
        .hero-eyebrow {
          display: inline-block;
          margin-bottom: 20px;
          font-family: 'Space Grotesk', sans-serif;
          font-size: 0.78rem;
          font-weight: 600;
          letter-spacing: 0.22em;
          text-transform: uppercase;
          color: #E8B24A;
        }
        .hero-copy h1 {
          margin: 0 0 20px;
          font-family: 'Fraunces', serif;
          font-size: clamp(2.6rem, 5.4vw, 4.2rem);
          line-height: 1.02;
          font-weight: 600;
          letter-spacing: -0.02em;
          color: #F4EEE1;
        }
        .hero-copy h1 em {
          font-style: italic;
          color: #E8B24A;
        }
        .hero-lead {
          max-width: 30em;
          margin: 0 0 30px;
          font-size: 1.12rem;
          line-height: 1.68;
          color: rgba(244, 238, 225, 0.66);
        }
        .hero-actions {
          display: flex;
          gap: 14px;
          flex-wrap: wrap;
          margin-bottom: 34px;
        }
        .hero-trust {
          display: flex;
          align-items: center;
          gap: 16px;
          flex-wrap: wrap;
          font-size: 0.95rem;
          color: rgba(244, 238, 225, 0.66);
        }
        .hero-trust strong { color: #F4EEE1; font-weight: 700; }
        .hero-trust .dot {
          width: 5px; height: 5px; border-radius: 50%;
          background: #2FC98A;
        }

        /* ── BUTTONS ── */
        .btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 50px;
          padding: 14px 30px;
          border-radius: 999px;
          font-family: 'Space Grotesk', sans-serif;
          font-size: 0.98rem;
          font-weight: 600;
          letter-spacing: 0.01em;
          text-decoration: none;
          transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease;
        }
        .btn-gold {
          background: linear-gradient(135deg, #E8B24A, #C6871B);
          color: #17201C;
          box-shadow: 0 14px 34px rgba(232, 178, 74, 0.28);
        }
        .btn-gold:hover {
          transform: translateY(-2px);
          box-shadow: 0 18px 44px rgba(232, 178, 74, 0.38);
        }
        .btn-ghost {
          background: rgba(244, 238, 225, 0.05);
          border: 1px solid rgba(138, 168, 148, 0.28);
          color: #F4EEE1;
        }
        .btn-ghost:hover {
          transform: translateY(-2px);
          border-color: #2FC98A;
          background: rgba(47, 201, 138, 0.10);
        }

        /* ── DOSHA ORB ── */
        .hero-stage {
          position: relative;
          display: grid;
          place-items: center;
          min-height: 440px;
        }
        .orb {
          position: relative;
          width: min(400px, 78vw);
          aspect-ratio: 1;
          border-radius: 50%;
          background:
            radial-gradient(circle at 34% 30%, rgba(232, 178, 74, 0.95), rgba(232, 178, 74, 0) 46%),
            radial-gradient(circle at 70% 74%, rgba(47, 201, 138, 0.85), rgba(47, 201, 138, 0) 52%),
            radial-gradient(circle at 60% 40%, rgba(180, 99, 58, 0.55), rgba(180, 99, 58, 0) 40%),
            radial-gradient(circle at 50% 50%, #16332680, #0B1512 80%);
          box-shadow: inset 0 0 90px rgba(0, 0, 0, 0.55), 0 30px 90px rgba(0, 0, 0, 0.5);
          animation: orbBreathe 7s ease-in-out infinite;
        }
        .orb::before {
          content: "";
          position: absolute;
          inset: -13%;
          border-radius: 50%;
          background: conic-gradient(from 0deg,
            rgba(232, 178, 74, 0), rgba(232, 178, 74, 0.55),
            rgba(47, 201, 138, 0.5), rgba(180, 99, 58, 0.3),
            rgba(232, 178, 74, 0));
          filter: blur(16px);
          opacity: 0.6;
          animation: orbSpin 20s linear infinite;
        }
        .orb::after {
          content: "";
          position: absolute;
          inset: 7%;
          border-radius: 50%;
          background:
            repeating-linear-gradient(0deg, transparent 0 15px, rgba(244, 238, 225, 0.05) 15px 16px),
            repeating-linear-gradient(90deg, transparent 0 15px, rgba(244, 238, 225, 0.04) 15px 16px);
          -webkit-mask: radial-gradient(circle, #000 58%, transparent 72%);
          mask: radial-gradient(circle, #000 58%, transparent 72%);
          animation: orbSpin 30s linear infinite reverse;
        }
        .orb-orbit {
          position: absolute;
          inset: -6%;
          animation: orbSpin 24s linear infinite;
        }
        .orb-orbit i {
          position: absolute;
          width: 10px; height: 10px;
          border-radius: 50%;
          background: #E8B24A;
          box-shadow: 0 0 14px rgba(232, 178, 74, 0.8);
        }
        .orb-orbit i:nth-child(1) { top: 2%; left: 50%; }
        .orb-orbit i:nth-child(2) { top: 50%; left: 97%; background: #2FC98A; box-shadow: 0 0 14px rgba(47, 201, 138, 0.8); }
        .orb-orbit i:nth-child(3) { top: 88%; left: 14%; background: #B4633A; box-shadow: 0 0 14px rgba(180, 99, 58, 0.7); }

        /* Telemetry Glass Panel */
        .telemetry {
          position: absolute;
          bottom: 6%;
          left: -2%;
          width: 240px;
          padding: 16px 18px;
          border-radius: 16px;
          background: rgba(11, 21, 18, 0.75);
          border: 1px solid rgba(138, 168, 148, 0.25);
          box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
          backdrop-filter: blur(16px);
        }
        .tel-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 5px 0;
          font-size: 0.82rem;
          color: rgba(244, 238, 225, 0.66);
        }
        .tel-head {
          margin-bottom: 4px;
          font-family: 'Space Grotesk', sans-serif;
          font-size: 0.74rem;
          font-weight: 600;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: #F4EEE1;
        }
        .tel-dot {
          display: inline-block;
          width: 7px; height: 7px; margin-right: 6px;
          border-radius: 50%;
          background: #2FC98A;
          box-shadow: 0 0 8px rgba(47, 201, 138, 0.9);
          animation: telPulse 2.4s ease-in-out infinite;
        }
        .mono { font-family: ui-monospace, monospace; font-size: 0.8rem; }
        .tel-green { color: #2FC98A; }
        .tel-bar {
          margin-top: 8px;
          height: 5px;
          border-radius: 999px;
          background: rgba(244, 238, 225, 0.10);
          overflow: hidden;
        }
        .tel-bar i {
          display: block;
          height: 100%;
          border-radius: 999px;
          background: linear-gradient(90deg, #E8B24A, #2FC98A);
        }

        /* Nadi Divider */
        .nadi { margin: 16px 0 60px; opacity: 0.9; }
        .nadi svg { display: block; width: 100%; height: 40px; }

        /* Section Shell */
        .section-eyebrow {
          display: block;
          text-align: center;
          margin-bottom: 10px;
          font-family: 'Space Grotesk', sans-serif;
          font-size: 0.74rem;
          font-weight: 600;
          letter-spacing: 0.22em;
          text-transform: uppercase;
          color: #E8B24A;
        }
        .landing-section-title {
          margin: 0 0 44px;
          text-align: center;
          font-family: 'Fraunces', serif;
          font-size: clamp(2rem, 3.8vw, 2.8rem);
          line-height: 1.14;
          font-weight: 600;
          color: #F4EEE1;
        }

        /* Feature Cards */
        .landing-features-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: 20px;
          margin-bottom: 70px;
        }
        .landing-feature-card {
          min-height: 200px;
          padding: 30px 22px;
          border-radius: 18px;
          background: rgba(19, 34, 28, 0.55);
          border: 1px solid rgba(138, 168, 148, 0.16);
          box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
          backdrop-filter: blur(14px);
          transition: transform 200ms ease, border-color 200ms ease;
        }
        .landing-feature-card:hover {
          transform: translateY(-5px);
          background: rgba(47, 201, 138, 0.06);
          border-color: rgba(47, 201, 138, 0.34);
        }
        .landing-feature-card h3 {
          margin: 12px 0 8px;
          font-size: 1.1rem;
          color: #F4EEE1;
        }
        .landing-feature-card p {
          margin: 0;
          color: rgba(244, 238, 225, 0.66);
          font-size: 0.94rem;
          line-height: 1.55;
        }

        /* Steps Grid */
        .landing-steps-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 24px;
          margin-bottom: 70px;
        }
        .landing-step-card {
          padding: 34px 28px;
          border-radius: 20px;
          background: rgba(19, 34, 28, 0.55);
          border: 1px solid rgba(138, 168, 148, 0.18);
          backdrop-filter: blur(14px);
        }
        .step-num {
          font-family: 'Space Grotesk', sans-serif;
          font-size: 1.1rem;
          font-weight: 700;
          color: #2FC98A;
          margin-bottom: 12px;
          display: block;
        }
        .landing-step-card h3 {
          font-family: 'Fraunces', serif;
          font-size: 1.5rem;
          font-weight: 600;
          color: #F4EEE1;
          margin: 0 0 10px;
        }
        .landing-step-card p {
          color: rgba(244, 238, 225, 0.66);
          font-size: 0.96rem;
          line-height: 1.6;
          margin: 0;
        }

        /* Roles Grid */
        .landing-roles-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 24px;
          margin-bottom: 70px;
        }
        .landing-role-card {
          padding: 38px 32px;
          border-radius: 22px;
          background: rgba(19, 34, 28, 0.55);
          border: 1px solid rgba(138, 168, 148, 0.18);
          backdrop-filter: blur(14px);
        }
        .landing-role-card h2 {
          font-family: 'Fraunces', serif;
          font-size: 1.8rem;
          font-weight: 600;
          color: #F4EEE1;
          margin: 0 0 4px;
        }
        .landing-role-subtitle {
          color: #E8B24A;
          font-size: 0.95rem;
          font-weight: 600;
          margin-bottom: 24px;
        }
        .role-list {
          list-style: none;
          padding: 0;
          margin: 0;
          display: flex;
          flex-direction: column;
          gap: 14px;
        }
        .role-list li {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          color: rgba(244, 238, 225, 0.82);
          font-size: 0.96rem;
          line-height: 1.5;
        }
        .role-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #2FC98A;
          margin-top: 7px;
          flex-shrink: 0;
        }

        /* Banner CTA Card */
        .banner-cta-card {
          padding: 56px 32px;
          border-radius: 28px;
          background: rgba(19, 34, 28, 0.65);
          border: 1px solid rgba(138, 168, 148, 0.22);
          text-align: center;
          backdrop-filter: blur(16px);
          box-shadow: 0 30px 80px rgba(0, 0, 0, 0.4);
          margin-bottom: 40px;
        }
        .banner-cta-card h2 {
          font-family: 'Fraunces', serif;
          font-size: clamp(2rem, 4vw, 3rem);
          font-weight: 600;
          color: #F4EEE1;
          margin: 0 0 10px;
        }
        .banner-cta-card p {
          color: rgba(244, 238, 225, 0.66);
          font-size: 1.05rem;
          margin: 0 0 28px;
        }

        /* Animations */
        @keyframes orbBreathe {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.03); }
        }
        @keyframes orbSpin {
          to { transform: rotate(360deg); }
        }
        @keyframes telPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.85); }
        }

        @media (max-width: 860px) {
          .landing-hero { grid-template-columns: 1fr; text-align: center; }
          .hero-lead { margin-left: auto; margin-right: auto; }
          .hero-actions, .hero-trust { justify-content: center; }
          .telemetry { left: 50%; transform: translateX(-50%); bottom: -20px; }
        }
      `}</style>

      {/* HERO SECTION */}
      <section className="landing-hero">
        <div className="hero-copy">
          <span className="hero-eyebrow">AYURVEDA × ARTIFICIAL INTELLIGENCE</span>
          <h1>Care that reads the<br /><em>whole</em> you.</h1>
          <p className="hero-lead">
            Kash AI listens in Hindi or English, reads the pulse of a consultation,
            and turns ancient diagnostic wisdom into a calm, computed clinical workflow.
          </p>
          <div className="hero-actions">
            <Link to="/login" className="btn btn-gold">Start free trial</Link>
            <Link to="/doctor" className="btn btn-ghost">See the AI doctor →</Link>
          </div>
          <div className="hero-trust">
            <span><strong>2+ hrs</strong> saved daily</span>
            <span className="dot"></span>
            <span><strong>70%</strong> less typing</span>
            <span className="dot"></span>
            <span><strong>800k+</strong> doctors scale-ready</span>
          </div>
        </div>

        <div className="hero-stage" aria-hidden="true">
          <div className="orb">
            <div className="orb-orbit"><i></i><i></i><i></i></div>
          </div>
          <div className="telemetry">
            <div className="tel-row tel-head">
              <span className="tel-dot"></span> DOSHA TELEMETRY
            </div>
            <div className="tel-row"><span>Nadi pulse</span><b className="mono">72 bpm</b></div>
            <div className="tel-row"><span>Vata · Pitta · Kapha</span><b className="mono">balanced</b></div>
            <div className="tel-row"><span>Model confidence</span><b className="mono tel-green">98.2%</b></div>
            <div className="tel-bar"><i style={{ width: '82%' }}></i></div>
          </div>
        </div>
      </section>

      {/* NADI PULSE DIVIDER */}
      <div className="nadi" aria-hidden="true">
        <svg viewBox="0 0 1200 40" preserveAspectRatio="none">
          <path d="M0 20 H420 l18 -13 22 26 16 -30 20 34 14 -17 H700 l22 -22 20 22 H1200"
                fill="none" stroke="url(#ng)" strokeWidth="2" />
          <defs>
            <linearGradient id="ng" x1="0" x2="1">
              <stop offset="0" stopColor="#E8B24A" stopOpacity="0"/>
              <stop offset="0.5" stopColor="#E8B24A"/>
              <stop offset="1" stopColor="#2FC98A" stopOpacity="0"/>
            </linearGradient>
          </defs>
        </svg>
      </div>

      {/* FEATURES SECTION */}
      <section style={{ marginTop: '20px' }}>
        <span className="section-eyebrow">WHAT IT DOES</span>
        <h2 className="landing-section-title">Intelligence, grounded in tradition</h2>
        
        <div className="landing-features-grid">
          <div className="landing-feature-card">
            <div style={{ color: '#2FC98A' }}><Mic size={28} /></div>
            <h3>Voice-first intake</h3>
            <p>Dictate the consultation in Hindi or English — Kash AI writes the clinical note.</p>
          </div>

          <div className="landing-feature-card">
            <div style={{ color: '#E8B24A' }}><Brain size={28} /></div>
            <h3>Dosha-aware support</h3>
            <p>Suggestions framed around Vata, Pitta and Kapha balance, not generic templates.</p>
          </div>

          <div className="landing-feature-card">
            <div style={{ color: '#06B6D4' }}><MessageSquare size={28} /></div>
            <h3>WhatsApp-ready journeys</h3>
            <p>Share prescriptions and care plans instantly through familiar channels.</p>
          </div>

          <div className="landing-feature-card">
            <div style={{ color: '#F43F5E' }}><ShieldAlert size={28} /></div>
            <h3>Emergency detection</h3>
            <p>Critical symptoms are surfaced and escalated to the doctor in real time.</p>
          </div>
        </div>
      </section>

      {/* THREE UNHURRIED STEPS SECTION */}
      <section style={{ marginTop: '20px' }}>
        <span className="section-eyebrow">HOW IT WORKS</span>
        <h2 className="landing-section-title">Three unhurried steps</h2>

        <div className="landing-steps-grid">
          <div className="landing-step-card">
            <span className="step-num">01</span>
            <h3>Consult</h3>
            <p>Speak naturally. Kash AI captures the symptoms, history and pulse of the visit.</p>
          </div>
          <div className="landing-step-card">
            <span className="step-num">02</span>
            <h3>Analyse</h3>
            <p>The model reads dosha signals and drafts a structured, editable clinical note.</p>
          </div>
          <div className="landing-step-card">
            <span className="step-num">03</span>
            <h3>Heal</h3>
            <p>Send the plan to the patient and track follow-ups — all in one calm workspace.</p>
          </div>
        </div>
      </section>

      {/* FOR DOCTORS & FOR PATIENTS ROLES SECTION */}
      <section style={{ marginTop: '20px' }}>
        <div className="landing-roles-grid">
          <div className="landing-role-card">
            <h2>For doctors</h2>
            <div className="landing-role-subtitle">Built for clinical speed</div>
            <ul className="role-list">
              <li><span className="role-dot"></span> Dictate notes in Hindi or English and save hours.</li>
              <li><span className="role-dot"></span> Generate cases, prescriptions and follow-ups faster.</li>
              <li><span className="role-dot"></span> Keep patient context organised in one secure workspace.</li>
              <li><span className="role-dot"></span> Share care plans instantly through WhatsApp-ready flows.</li>
            </ul>
          </div>

          <div className="landing-role-card">
            <h2>For patients</h2>
            <div className="landing-role-subtitle">Simple, calm care access</div>
            <ul className="role-list">
              <li><span className="role-dot"></span> Book appointments without calling the clinic.</li>
              <li><span className="role-dot"></span> View prescriptions and care plans anytime.</li>
              <li><span className="role-dot"></span> Ask AI health questions in a friendly chat.</li>
              <li><span className="role-dot"></span> Track health history and follow-ups in one place.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* BANNER CTA CARD */}
      <section className="banner-cta-card">
        <h2>Bring ancient intelligence into your clinic.</h2>
        <p>Start in minutes. No card required.</p>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '14px', flexWrap: 'wrap' }}>
          <Link to="/login" className="btn btn-gold">Create account</Link>
          <Link to="/login" className="btn btn-ghost">Login</Link>
          <Link to="/doctor" className="btn btn-ghost">Try AI doctor</Link>
        </div>
      </section>
    </div>
  );
}
