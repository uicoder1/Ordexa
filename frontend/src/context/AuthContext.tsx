import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';
import type { User, Organization } from '../types';

interface AuthContextType {
  user: User | null;
  organizations: Organization[];
  activeOrg: Organization | null;
  token: string | null;
  isLoading: boolean;
  login: (token: string, user: User, activeOrgId?: string) => Promise<void>;
  signup: (token: string, user: User, activeOrgId?: string) => Promise<void>;
  logout: () => void;
  switchOrganization: (orgId: string) => void;
  refreshOrganizations: () => Promise<void>;
  seedDemoData: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [activeOrg, setActiveOrg] = useState<Organization | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('profitpilot_token'));
  const [isLoading, setIsLoading] = useState(true);

  const fetchUserAndOrgs = async () => {
    setIsLoading(true);
    try {
      if (!token) {
        setIsLoading(false);
        return;
      }
      const userRes = await api.get('/auth/me');
      setUser(userRes.data);

      const orgsRes = await api.get('/organizations');
      const orgsList: Organization[] = orgsRes.data;
      setOrganizations(orgsList);

      const savedOrgId = localStorage.getItem('profitpilot_active_org_id');
      const foundOrg = orgsList.find((o) => o.id === savedOrgId) || orgsList[0] || null;

      setActiveOrg(foundOrg);
      if (foundOrg) {
        localStorage.setItem('profitpilot_active_org_id', foundOrg.id);
      }
    } catch (error) {
      console.error('Auth verification failed', error);
      logout();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUserAndOrgs();
  }, [token]);

  const login = async (newToken: string, newUser: User, activeOrgId?: string) => {
    localStorage.setItem('profitpilot_token', newToken);
    if (activeOrgId) {
      localStorage.setItem('profitpilot_active_org_id', activeOrgId);
    }
    setToken(newToken);
    setUser(newUser);
    try {
      const orgsRes = await api.get('/organizations', {
        headers: { Authorization: `Bearer ${newToken}` }
      });
      const orgsList: Organization[] = orgsRes.data;
      setOrganizations(orgsList);
      const targetOrg = (activeOrgId ? orgsList.find(o => o.id === activeOrgId) : null) || orgsList[0] || null;
      setActiveOrg(targetOrg);
      if (targetOrg) {
        localStorage.setItem('profitpilot_active_org_id', targetOrg.id);
      }
    } catch (e) {
      console.error('Failed to prefetch organizations', e);
    }
  };

  const signup = async (newToken: string, newUser: User, activeOrgId?: string) => {
    await login(newToken, newUser, activeOrgId);
  };

  const logout = () => {
    localStorage.removeItem('profitpilot_token');
    localStorage.removeItem('profitpilot_active_org_id');
    setToken(null);
    setUser(null);
    setOrganizations([]);
    setActiveOrg(null);
    setIsLoading(false);
  };

  const switchOrganization = (orgId: string) => {
    const target = organizations.find((o) => o.id === orgId);
    if (target) {
      setActiveOrg(target);
      localStorage.setItem('profitpilot_active_org_id', target.id);
    }
  };

  const refreshOrganizations = async () => {
    const orgsRes = await api.get('/organizations');
    setOrganizations(orgsRes.data);
  };

  const seedDemoData = async () => {
    if (!activeOrg) return;
    await api.post('/organizations/seed-demo');
    window.location.reload();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        organizations,
        activeOrg,
        token,
        isLoading,
        login,
        signup,
        logout,
        switchOrganization,
        refreshOrganizations,
        seedDemoData,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
