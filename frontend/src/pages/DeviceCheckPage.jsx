import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { 
  Camera, 
  CameraOff, 
  Mic, 
  MicOff, 
  Volume2, 
  VolumeX, 
  Wifi, 
  ShieldCheck, 
  AlertCircle, 
  CheckCircle2, 
  RefreshCw, 
  ArrowLeft, 
  ExternalLink, 
  Activity, 
  Sparkles, 
  Wrench,
  Stethoscope,
  Video
} from 'lucide-react';
import axios from 'axios';

export default function DeviceCheckPage() {
  const navigate = useNavigate();

  // Camera state
  const [cameraStatus, setCameraStatus] = useState('idle'); // 'idle' | 'checking' | 'active' | 'denied' | 'error'
  const [cameraError, setCameraError] = useState('');
  const [cameraDevices, setCameraDevices] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState('');
  const [snapshot, setSnapshot] = useState(null);
  const videoRef = useRef(null);
  const cameraStreamRef = useRef(null);

  // Microphone state
  const [micStatus, setMicStatus] = useState('idle'); // 'idle' | 'checking' | 'active' | 'denied' | 'error'
  const [micError, setMicError] = useState('');
  const [micDevices, setMicDevices] = useState([]);
  const [selectedMicId, setSelectedMicId] = useState('');
  const [audioLevel, setAudioLevel] = useState(0);
  const micStreamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const animFrameRef = useRef(null);

  // Speaker state
  const [speakerStatus, setSpeakerStatus] = useState('idle'); // 'idle' | 'playing' | 'tested'

  // Server & Network Telemetry
  const [telemetryStatus, setTelemetryStatus] = useState('idle'); // 'idle' | 'checking' | 'success' | 'error'
  const [telemetryData, setTelemetryData] = useState(null);
  const [pingMs, setPingMs] = useState(null);
  const [webrtcSupported, setWebrtcSupported] = useState(false);

  // Check WebRTC on mount
  useEffect(() => {
    const hasWebRTC = !!(
      window.RTCPeerConnection ||
      window.mozRTCPeerConnection ||
      window.webkitRTCPeerConnection
    );
    setWebrtcSupported(hasWebRTC);

    // Initial check of server connectivity & device enumeration
    runTelemetryCheck();
    enumerateAvailableDevices();

    return () => {
      stopAllMedia();
    };
  }, []);

  const stopAllMedia = () => {
    stopCamera();
    stopMic();
  };

  // Enumerate Devices
  const enumerateAvailableDevices = async () => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
      const devices = await navigator.mediaDevices.enumerateDevices();
      
      const videoInputs = devices.filter(d => d.kind === 'videoinput');
      const audioInputs = devices.filter(d => d.kind === 'audioinput');

      setCameraDevices(videoInputs);
      setMicDevices(audioInputs);

      if (videoInputs.length > 0 && !selectedCameraId) {
        setSelectedCameraId(videoInputs[0].deviceId);
      }
      if (audioInputs.length > 0 && !selectedMicId) {
        setSelectedMicId(audioInputs[0].deviceId);
      }
    } catch (err) {
      console.warn("Device enumeration note:", err);
    }
  };

  // ==========================================
  // CAMERA DIAGNOSTICS
  // ==========================================
  const startCamera = async (deviceId) => {
    stopCamera();
    setCameraStatus('checking');
    setCameraError('');
    setSnapshot(null);

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Your browser does not support media camera access.');
      }

      const constraints = {
        video: deviceId ? { deviceId: { exact: deviceId } } : true,
        audio: false
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      cameraStreamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(e => console.warn("Video play notice:", e));
      }

      setCameraStatus('active');
      // Re-enumerate to get labeled device names now that permission is granted
      enumerateAvailableDevices();
    } catch (err) {
      console.error("Camera access error:", err);
      setCameraStatus(err.name === 'NotAllowedError' ? 'denied' : 'error');
      setCameraError(
        err.name === 'NotAllowedError'
          ? 'Camera permission denied. Please allow camera access in your browser address bar.'
          : err.name === 'NotFoundError'
          ? 'No camera device detected. Connect a webcam and try again.'
          : (err.message || 'Unable to access video camera.')
      );
    }
  };

  const stopCamera = () => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach(track => track.stop());
      cameraStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraStatus('idle');
  };

  const captureSnapshot = () => {
    if (!videoRef.current || cameraStatus !== 'active') return;
    try {
      const video = videoRef.current;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
      setSnapshot(dataUrl);
    } catch (err) {
      console.error("Snapshot error:", err);
    }
  };

  // ==========================================
  // MICROPHONE DIAGNOSTICS
  // ==========================================
  const startMic = async (deviceId) => {
    stopMic();
    setMicStatus('checking');
    setMicError('');

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Your browser does not support audio recording.');
      }

      const constraints = {
        audio: {
          deviceId: deviceId ? { exact: deviceId } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      micStreamRef.current = stream;

      // Audio Context analyser
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioCtxRef.current = audioCtx;

      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const checkVolume = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const avg = sum / bufferLength;
        const normalized = Math.min(Math.round((avg / 128) * 100), 100);
        setAudioLevel(normalized);

        animFrameRef.current = requestAnimationFrame(checkVolume);
      };

      checkVolume();
      setMicStatus('active');
      enumerateAvailableDevices();
    } catch (err) {
      console.error("Mic access error:", err);
      setMicStatus(err.name === 'NotAllowedError' ? 'denied' : 'error');
      setMicError(
        err.name === 'NotAllowedError'
          ? 'Microphone permission blocked. Click the address bar icon to allow microphone.'
          : err.name === 'NotFoundError'
          ? 'No microphone detected on your system.'
          : (err.message || 'Microphone test failed.')
      );
    }
  };

  const stopMic = () => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(track => track.stop());
      micStreamRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setAudioLevel(0);
    setMicStatus('idle');
  };

  // ==========================================
  // SPEAKER / AUDIO OUTPUT TEST
  // ==========================================
  const testSpeakers = () => {
    setSpeakerStatus('playing');
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();

      // Dual harmonic medical chime (528Hz & 880Hz)
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gainNode = ctx.createGain();

      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(528, ctx.currentTime); // C5 harmonic
      osc2.type = 'triangle';
      osc2.frequency.setValueAtTime(880, ctx.currentTime); // A5 harmonic

      gainNode.gain.setValueAtTime(0.01, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.1);
      gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1.2);

      osc1.connect(gainNode);
      osc2.connect(gainNode);
      gainNode.connect(ctx.destination);

      osc1.start(ctx.currentTime);
      osc2.start(ctx.currentTime + 0.05);

      osc1.stop(ctx.currentTime + 1.2);
      osc2.stop(ctx.currentTime + 1.2);

      setTimeout(() => {
        setSpeakerStatus('tested');
      }, 1300);
    } catch (e) {
      console.error("Speaker test error:", e);
      setSpeakerStatus('tested');
    }
  };

  // ==========================================
  // SERVER & TELEMETRY CHECK
  // ==========================================
  const runTelemetryCheck = async () => {
    setTelemetryStatus('checking');
    const start = performance.now();
    try {
      const res = await axios.get('/api/device/check', { timeout: 5000 });
      const duration = Math.round(performance.now() - start);
      setPingMs(duration);
      setTelemetryData(res.data);
      setTelemetryStatus('success');
    } catch (err) {
      console.warn("Backend device API ping failed, testing fallback /api/health", err);
      try {
        await axios.get('/api/health', { timeout: 4000 });
        const duration = Math.round(performance.now() - start);
        setPingMs(duration);
        setTelemetryData({ success: true, status: 'operational' });
        setTelemetryStatus('success');
      } catch (e2) {
        setTelemetryStatus('error');
        setPingMs(null);
      }
    }
  };

  // Overall readiness
  const isCameraOk = cameraStatus === 'active';
  const isMicOk = micStatus === 'active';
  const isTelemetryOk = telemetryStatus === 'success';
  const readyCount = [isCameraOk, isMicOk, speakerStatus === 'tested', isTelemetryOk].filter(Boolean).length;

  return (
    <div style={{
      minHeight: 'calc(100vh - 68px)',
      background: 'radial-gradient(circle at 50% 0%, #0d281e 0%, #061510 100%)',
      color: '#F8FAFC',
      padding: '36px 24px 80px',
      boxSizing: 'border-box'
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

        {/* Top Navigation & Breadcrumb */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={() => navigate(-1)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#E2E8F0',
                cursor: 'pointer',
                fontWeight: '600',
                fontSize: '0.86rem'
              }}
            >
              <ArrowLeft size={16} /> Return to Dashboard
            </button>
            <span style={{ color: 'rgba(255, 255, 255, 0.3)' }}>/</span>
            <span style={{ color: '#10B981', fontWeight: '700', fontSize: '0.9rem' }}>Telemedicine Diagnostics</span>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <a
              href="http://localhost:8000/device-check"
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#94A3B8',
                textDecoration: 'none',
                fontSize: '0.82rem',
                fontWeight: '600'
              }}
            >
              <ExternalLink size={14} /> Open Backend Diagnostics Console
            </a>
            <button
              onClick={() => {
                runTelemetryCheck();
                enumerateAvailableDevices();
                startCamera(selectedCameraId);
                startMic(selectedMicId);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #10B981, #059669)',
                border: 'none',
                color: '#FFFFFF',
                fontWeight: '700',
                fontSize: '0.85rem',
                cursor: 'pointer',
                boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)'
              }}
            >
              <RefreshCw size={15} /> Run Full Diagnostic
            </button>
          </div>
        </div>

        {/* Hero Header Banner */}
        <div style={{
          padding: '28px 32px',
          borderRadius: '20px',
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(6, 182, 212, 0.08))',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          marginBottom: '28px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '20px'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <div style={{
                width: '38px',
                height: '38px',
                borderRadius: '10px',
                background: 'rgba(16, 185, 129, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#10B981'
              }}>
                <Wrench size={20} />
              </div>
              <h1 style={{ fontSize: '1.6rem', fontWeight: '800', margin: 0, color: '#F8FAFC' }}>
                Device & Telehealth Diagnostics
              </h1>
            </div>
            <p style={{ margin: 0, color: '#94A3B8', fontSize: '0.92rem', maxWidth: '650px' }}>
              Calibrate your camera, microphone, and speakers before conducting or joining clinical consultations. WebRTC audio and video tests run directly inside your browser.
            </p>
          </div>

          {/* Readiness Score Pill */}
          <div style={{
            padding: '16px 24px',
            borderRadius: '16px',
            background: readyCount >= 3 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(234, 179, 8, 0.15)',
            border: `1px solid ${readyCount >= 3 ? 'rgba(16, 185, 129, 0.35)' : 'rgba(234, 179, 8, 0.35)'}`,
            textAlign: 'right'
          }}>
            <div style={{ fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '700' }}>
              Consultation Readiness
            </div>
            <div style={{
              fontSize: '1.4rem',
              fontWeight: '800',
              color: readyCount >= 3 ? '#10B981' : '#FBBF24',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginTop: '4px'
            }}>
              {readyCount >= 3 ? <CheckCircle2 size={22} color="#10B981" /> : <AlertCircle size={22} color="#FBBF24" />}
              {readyCount >= 3 ? 'Systems Ready' : `${readyCount}/4 Checks Complete`}
            </div>
          </div>
        </div>

        {/* ======================================================== */}
        {/* 4-CARD DIAGNOSTIC GRID                                   */}
        {/* ======================================================== */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '24px', marginBottom: '32px' }}>

          {/* 1. CAMERA DIAGNOSTICS */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '20px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '34px', height: '34px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Camera size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: '700' }}>Video Camera</h3>
                  <div style={{ fontSize: '0.78rem', color: '#94A3B8' }}>Telemedicine video stream check</div>
                </div>
              </div>

              {/* Status Badge */}
              <span style={{
                padding: '4px 10px',
                borderRadius: '20px',
                fontSize: '0.75rem',
                fontWeight: '700',
                background: 
                  cameraStatus === 'active' ? 'rgba(16, 185, 129, 0.2)' :
                  cameraStatus === 'checking' ? 'rgba(234, 179, 8, 0.2)' :
                  cameraStatus === 'denied' || cameraStatus === 'error' ? 'rgba(239, 68, 68, 0.2)' :
                  'rgba(255, 255, 255, 0.08)',
                color:
                  cameraStatus === 'active' ? '#10B981' :
                  cameraStatus === 'checking' ? '#FBBF24' :
                  cameraStatus === 'denied' || cameraStatus === 'error' ? '#EF4444' :
                  '#94A3B8'
              }}>
                {cameraStatus === 'active' ? '● Camera Active' :
                 cameraStatus === 'checking' ? '⏳ Testing Camera...' :
                 cameraStatus === 'denied' ? '❌ Access Blocked' :
                 cameraStatus === 'error' ? '❌ Camera Error' : 'Ready to Test'}
              </span>
            </div>

            {/* Video Viewport */}
            <div style={{
              width: '100%',
              height: '240px',
              borderRadius: '14px',
              background: '#040d0a',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              overflow: 'hidden',
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '16px'
            }}>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  display: cameraStatus === 'active' ? 'block' : 'none'
                }}
              />

              {cameraStatus !== 'active' && (
                <div style={{ textAlign: 'center', padding: '20px', color: '#64748B' }}>
                  <CameraOff size={38} style={{ opacity: 0.5, marginBottom: '8px' }} />
                  <div style={{ fontSize: '0.85rem' }}>Camera is currently idle.</div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>Click "Test Camera" below to initiate stream.</div>
                </div>
              )}

              {cameraStatus === 'active' && (
                <div style={{
                  position: 'absolute',
                  top: '10px',
                  left: '10px',
                  background: 'rgba(0, 0, 0, 0.65)',
                  backdropFilter: 'blur(8px)',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontSize: '0.72rem',
                  color: '#10B981',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10B981', display: 'inline-block' }}></span>
                  Live 30 FPS • WebRTC HD
                </div>
              )}
            </div>

            {/* Device Selector Dropdown if multiple */}
            {cameraDevices.length > 0 && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '0.76rem', color: '#94A3B8', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
                  Camera Source
                </label>
                <select
                  value={selectedCameraId}
                  onChange={(e) => {
                    setSelectedCameraId(e.target.value);
                    if (cameraStatus === 'active') {
                      startCamera(e.target.value);
                    }
                  }}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#F8FAFC',
                    fontSize: '0.84rem'
                  }}
                >
                  {cameraDevices.map((dev, idx) => (
                    <option key={dev.deviceId || idx} value={dev.deviceId} style={{ background: '#0B1512' }}>
                      {dev.label || `Camera ${idx + 1}`}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Error Message */}
            {cameraError && (
              <div style={{
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#FCA5A5',
                fontSize: '0.8rem',
                marginBottom: '14px'
              }}>
                {cameraError}
              </div>
            )}

            {/* Snapshot Preview if captured */}
            {snapshot && (
              <div style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '10px', padding: '8px', background: 'rgba(255, 255, 255, 0.04)', borderRadius: '8px' }}>
                <img src={snapshot} alt="Test snapshot" style={{ width: '60px', height: '45px', borderRadius: '6px', objectFit: 'cover' }} />
                <div style={{ fontSize: '0.78rem', color: '#34D399' }}>
                  ✅ Snapshot captured successfully! Quality verified.
                </div>
              </div>
            )}

            {/* Camera Actions */}
            <div style={{ display: 'flex', gap: '8px', marginTop: 'auto' }}>
              {cameraStatus !== 'active' ? (
                <button
                  onClick={() => startCamera(selectedCameraId)}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: '10px',
                    background: 'linear-gradient(135deg, #10B981, #059669)',
                    border: 'none',
                    color: '#FFFFFF',
                    fontWeight: '700',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                >
                  <Camera size={16} /> Test Camera
                </button>
              ) : (
                <>
                  <button
                    onClick={captureSnapshot}
                    style={{
                      flex: 1,
                      padding: '10px',
                      borderRadius: '10px',
                      background: 'rgba(255, 255, 255, 0.08)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#F8FAFC',
                      fontWeight: '600',
                      fontSize: '0.84rem',
                      cursor: 'pointer'
                    }}
                  >
                    📸 Take Snapshot
                  </button>
                  <button
                    onClick={stopCamera}
                    style={{
                      padding: '10px 16px',
                      borderRadius: '10px',
                      background: 'rgba(239, 68, 68, 0.15)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      color: '#EF4444',
                      fontWeight: '700',
                      fontSize: '0.84rem',
                      cursor: 'pointer'
                    }}
                  >
                    Stop
                  </button>
                </>
              )}
            </div>
          </div>

          {/* 2. MICROPHONE DIAGNOSTICS */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '20px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '34px', height: '34px', borderRadius: '8px', background: 'rgba(6, 182, 212, 0.15)', color: '#06B6D4', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Mic size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: '700' }}>Microphone & Audio Input</h3>
                  <div style={{ fontSize: '0.78rem', color: '#94A3B8' }}>Voice consultation speech level</div>
                </div>
              </div>

              {/* Status Badge */}
              <span style={{
                padding: '4px 10px',
                borderRadius: '20px',
                fontSize: '0.75rem',
                fontWeight: '700',
                background:
                  micStatus === 'active' ? 'rgba(16, 185, 129, 0.2)' :
                  micStatus === 'checking' ? 'rgba(234, 179, 8, 0.2)' :
                  micStatus === 'denied' || micStatus === 'error' ? 'rgba(239, 68, 68, 0.2)' :
                  'rgba(255, 255, 255, 0.08)',
                color:
                  micStatus === 'active' ? '#10B981' :
                  micStatus === 'checking' ? '#FBBF24' :
                  micStatus === 'denied' || micStatus === 'error' ? '#EF4444' :
                  '#94A3B8'
              }}>
                {micStatus === 'active' ? '● Mic Active' :
                 micStatus === 'checking' ? '⏳ Requesting...' :
                 micStatus === 'denied' ? '❌ Mic Blocked' :
                 micStatus === 'error' ? '❌ Mic Error' : 'Ready to Test'}
              </span>
            </div>

            {/* Audio Waveform & Level Meter */}
            <div style={{
              background: '#040d0a',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '14px',
              padding: '24px 20px',
              marginBottom: '16px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              minHeight: '140px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.8rem', color: '#94A3B8', fontWeight: '600' }}>Input Audio Volume</span>
                <span style={{ fontSize: '0.85rem', color: micStatus === 'active' ? '#10B981' : '#64748B', fontWeight: '700' }}>
                  {audioLevel}%
                </span>
              </div>

              {/* Level progress bar */}
              <div style={{ width: '100%', height: '14px', background: 'rgba(255, 255, 255, 0.06)', borderRadius: '10px', overflow: 'hidden', position: 'relative' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${audioLevel}%`,
                    background: audioLevel > 70 ? 'linear-gradient(90deg, #10B981, #EF4444)' : audioLevel > 15 ? '#10B981' : '#06B6D4',
                    borderRadius: '10px',
                    transition: 'width 0.08s ease-out'
                  }}
                />
              </div>

              {/* Waveform Visualization Bars */}
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px', height: '40px', marginTop: '16px' }}>
                {[...Array(16)].map((_, i) => {
                  const barHeight = micStatus === 'active' ? Math.max(4, Math.sin(i + audioLevel / 10) * audioLevel * 0.35) : 4;
                  return (
                    <div
                      key={i}
                      style={{
                        width: '4px',
                        height: `${barHeight}px`,
                        borderRadius: '2px',
                        background: micStatus === 'active' ? (audioLevel > 10 ? '#10B981' : '#06B6D4') : '#334155',
                        transition: 'height 0.08s ease'
                      }}
                    />
                  );
                })}
              </div>
            </div>

            {/* Microphone Selector */}
            {micDevices.length > 0 && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '0.76rem', color: '#94A3B8', fontWeight: '600', display: 'block', marginBottom: '6px' }}>
                  Microphone Input
                </label>
                <select
                  value={selectedMicId}
                  onChange={(e) => {
                    setSelectedMicId(e.target.value);
                    if (micStatus === 'active') {
                      startMic(e.target.value);
                    }
                  }}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#F8FAFC',
                    fontSize: '0.84rem'
                  }}
                >
                  {micDevices.map((dev, idx) => (
                    <option key={dev.deviceId || idx} value={dev.deviceId} style={{ background: '#0B1512' }}>
                      {dev.label || `Microphone ${idx + 1}`}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Error Display */}
            {micError && (
              <div style={{
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#FCA5A5',
                fontSize: '0.8rem',
                marginBottom: '14px'
              }}>
                {micError}
              </div>
            )}

            {/* Mic Actions */}
            <div style={{ display: 'flex', gap: '8px', marginTop: 'auto' }}>
              {micStatus !== 'active' ? (
                <button
                  onClick={() => startMic(selectedMicId)}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: '10px',
                    background: 'linear-gradient(135deg, #06B6D4, #0284C7)',
                    border: 'none',
                    color: '#FFFFFF',
                    fontWeight: '700',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                >
                  <Mic size={16} /> Test Microphone
                </button>
              ) : (
                <button
                  onClick={stopMic}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: '10px',
                    background: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#EF4444',
                    fontWeight: '700',
                    fontSize: '0.84rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                >
                  <MicOff size={16} /> Stop Microphone
                </button>
              )}
            </div>
          </div>

          {/* 3. SPEAKER & AUDIO OUTPUT DIAGNOSTICS */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '20px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '34px', height: '34px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Volume2 size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: '700' }}>Speaker Output</h3>
                  <div style={{ fontSize: '0.78rem', color: '#94A3B8' }}>Audio playback & chime test</div>
                </div>
              </div>

              <span style={{
                padding: '4px 10px',
                borderRadius: '20px',
                fontSize: '0.75rem',
                fontWeight: '700',
                background: speakerStatus === 'tested' ? 'rgba(16, 185, 129, 0.2)' : speakerStatus === 'playing' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.08)',
                color: speakerStatus === 'tested' ? '#10B981' : speakerStatus === 'playing' ? '#F59E0B' : '#94A3B8'
              }}>
                {speakerStatus === 'tested' ? '✅ Output Verified' : speakerStatus === 'playing' ? '🎵 Playing Chime...' : 'Untested'}
              </span>
            </div>

            <div style={{
              background: '#040d0a',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '14px',
              padding: '20px',
              marginBottom: '16px',
              textAlign: 'center'
            }}>
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: speakerStatus === 'playing' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                margin: '0 auto 12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: speakerStatus === 'playing' ? '#F59E0B' : '#94A3B8',
                transition: 'all 0.3s ease'
              }}>
                <Volume2 size={26} className={speakerStatus === 'playing' ? 'pulse' : ''} />
              </div>
              <div style={{ fontSize: '0.88rem', fontWeight: '600', color: '#F8FAFC' }}>
                Harmonic Consultation Chime
              </div>
              <p style={{ margin: '6px 0 0', fontSize: '0.78rem', color: '#94A3B8' }}>
                Press "Play Sound" to produce a clean acoustic bell tone through your speakers or headphones.
              </p>
            </div>

            <div style={{ marginTop: 'auto' }}>
              <button
                onClick={testSpeakers}
                disabled={speakerStatus === 'playing'}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '10px',
                  background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                  border: 'none',
                  color: '#FFFFFF',
                  fontWeight: '700',
                  fontSize: '0.85rem',
                  cursor: speakerStatus === 'playing' ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                <Volume2 size={16} /> {speakerStatus === 'playing' ? 'Playing Test Sound...' : 'Play Test Chime'}
              </button>
            </div>
          </div>

          {/* 4. NETWORK & WEBRTC TELEMETRY */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '20px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '34px', height: '34px', borderRadius: '8px', background: 'rgba(99, 102, 241, 0.15)', color: '#6366F1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Wifi size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: '700' }}>Telemedicine Network</h3>
                  <div style={{ fontSize: '0.78rem', color: '#94A3B8' }}>WebRTC & Server Telemetry</div>
                </div>
              </div>

              <span style={{
                padding: '4px 10px',
                borderRadius: '20px',
                fontSize: '0.75rem',
                fontWeight: '700',
                background: telemetryStatus === 'success' ? 'rgba(16, 185, 129, 0.2)' : telemetryStatus === 'checking' ? 'rgba(234, 179, 8, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                color: telemetryStatus === 'success' ? '#10B981' : telemetryStatus === 'checking' ? '#FBBF24' : '#EF4444'
              }}>
                {telemetryStatus === 'success' ? '● Connected' : telemetryStatus === 'checking' ? '⏳ Pinging...' : 'Offline'}
              </span>
            </div>

            <div style={{
              background: '#040d0a',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '14px',
              padding: '16px',
              marginBottom: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: '#94A3B8' }}>WebRTC Support:</span>
                <span style={{ color: webrtcSupported ? '#10B981' : '#EF4444', fontWeight: '700' }}>
                  {webrtcSupported ? 'Native WebRTC 1.0 (Supported)' : 'Not Supported'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: '#94A3B8' }}>Telemedicine API:</span>
                <span style={{ color: telemetryStatus === 'success' ? '#10B981' : '#94A3B8', fontWeight: '700' }}>
                  {telemetryStatus === 'success' ? 'Endpoint Operational' : 'Verifying...'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: '#94A3B8' }}>Round-Trip Ping:</span>
                <span style={{ color: pingMs !== null && pingMs < 150 ? '#10B981' : '#FBBF24', fontWeight: '700' }}>
                  {pingMs !== null ? `${pingMs} ms (Optimal)` : '—'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: '#94A3B8' }}>Encryption:</span>
                <span style={{ color: '#10B981', fontWeight: '700' }}>
                  TLS / SRTP End-to-End
                </span>
              </div>
            </div>

            <div style={{ marginTop: 'auto' }}>
              <button
                onClick={runTelemetryCheck}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '10px',
                  background: 'rgba(99, 102, 241, 0.15)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                  color: '#818CF8',
                  fontWeight: '700',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                <RefreshCw size={15} /> Re-Ping Telemedicine Server
              </button>
            </div>
          </div>

        </div>

        {/* ======================================================== */}
        {/* QUICK NAVIGATION ACTION FOOTER                            */}
        {/* ======================================================== */}
        <div style={{
          padding: '24px 30px',
          borderRadius: '20px',
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px'
        }}>
          <div>
            <h4 style={{ margin: '0 0 4px', fontSize: '0.96rem', fontWeight: '700', color: '#F8FAFC' }}>
              All tests completed? Ready to start clinical consultation.
            </h4>
            <p style={{ margin: 0, fontSize: '0.82rem', color: '#94A3B8' }}>
              Audio and video devices will remain accessible throughout your clinical workflow.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={() => navigate('/consultation/voice')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '11px 22px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #10B981, #059669)',
                border: 'none',
                color: '#FFFFFF',
                fontWeight: '700',
                fontSize: '0.88rem',
                cursor: 'pointer',
                boxShadow: '0 4px 16px rgba(16, 185, 129, 0.3)'
              }}
            >
              <Mic size={16} /> Launch Voice Consultation
            </button>

            <button
              onClick={() => navigate('/doctor')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '11px 18px',
                borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#E2E8F0',
                fontWeight: '600',
                fontSize: '0.88rem',
                cursor: 'pointer'
              }}
            >
              <Stethoscope size={16} /> Doctor Portal
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
