import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState({
    id: 1,
    employee_id: 'admin',
    full_name: 'System Administrator',
    role: { name: 'Admin' },
  });
  const [loading, setLoading] = useState(false);

  const fetchUser = useCallback(async () => {
    try {
      // Backend auth is bypassed; returning a default admin user directly
      setUser({
        id: 1,
        employee_id: 'admin',
        full_name: 'System Administrator',
        role: { name: 'Admin' },
      });
    } catch (error) {
      console.error('Failed to set mock user:', error);
      setUser({
        id: 1,
        employee_id: 'admin',
        full_name: 'System Administrator',
        role: { name: 'Admin' },
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async () => {};
  const logout = () => {};

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    return {
      user: {
        id: 1,
        employee_id: 'admin',
        full_name: 'System Administrator',
        role: { name: 'Admin' },
      },
      login: async () => {},
      logout: () => {},
      loading: false,
      isAuthenticated: true,
    };
  }
  return context;
};
