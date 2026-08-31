import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('kash_user');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem('kash_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('kash_user');
    }
  }, [user]);

  const login = (role, username = '') => {
    const newUser = {
      username: username || (role === 'admin' ? 'admin' : role === 'doctor' ? 'dr_demo' : 'patient_demo'),
      role: role || 'doctor',
      name: role === 'admin' ? 'System Administrator' : role === 'doctor' ? 'Dr. Ananya Sharma' : 'Patient'
    };
    setUser(newUser);
    return getDashboardPath(newUser.role);
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('kash_user');
  };

  const getDashboardPath = (userRole = user?.role) => {
    switch (userRole) {
      case 'admin':
        return '/admin';
      case 'doctor':
        return '/doctor';
      case 'patient':
        return '/patient';
      default:
        return '/doctor';
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoggedIn: !!user, login, logout, getDashboardPath }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used within an <AuthProvider>. Wrap your app in <AuthProvider>.');
  }
  return context;
}
