import React, { useState } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Radar, ArrowRight, Loader2, Info, Building2, User as UserIcon, Mail, Lock, CheckCircle2, Eye, EyeOff } from 'lucide-react';

export const AuthModal: React.FC = () => {
  const { login, signup } = useAuth();
  const [isSignUp, setIsSignUp] = useState(false);

  // Sign In fields
  const [signInEmail, setSignInEmail] = useState('');
  const [signInPassword, setSignInPassword] = useState('');
  const [showSignInPassword, setShowSignInPassword] = useState(false);

  // Create Account fields (never preloaded)
  const [companyName, setCompanyName] = useState('');
  const [name, setName] = useState('');
  const [signUpEmail, setSignUpEmail] = useState('');
  const [signUpPassword, setSignUpPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showSignUpPassword, setShowSignUpPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // UI state
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSubmitted, setForgotSubmitted] = useState(false);

  const validateForm = (): boolean => {
    if (isSignUp) {
      if (!companyName.trim()) {
        setError('Company name is required.');
        return false;
      }
      if (!name.trim()) {
        setError('Full name is required.');
        return false;
      }
      if (!signUpEmail.trim() || !signUpEmail.includes('@') || !signUpEmail.includes('.')) {
        setError('Please enter a valid email address.');
        return false;
      }
      if (!signUpPassword) {
        setError('Password is required.');
        return false;
      }
      if (signUpPassword.length < 6) {
        setError('Password must be at least 6 characters.');
        return false;
      }
      if (signUpPassword !== confirmPassword) {
        setError('Passwords do not match.');
        return false;
      }
    } else {
      if (!signInEmail.trim() || !signInEmail.includes('@')) {
        setError('Please enter a valid email address.');
        return false;
      }
      if (!signInPassword) {
        setError('Password is required.');
        return false;
      }
    }
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    if (!validateForm()) return;

    setLoading(true);
    try {
      if (isSignUp) {
        const payload = {
          email: signUpEmail.trim().toLowerCase(),
          password: signUpPassword,
          name: name.trim(),
          company_name: companyName.trim(),
        };
        const r = await api.post('/auth/signup', payload);
        await signup(r.data.access_token, r.data.user, r.data.active_organization_id);
      } else {
        const payload = {
          email: signInEmail.trim().toLowerCase(),
          password: signInPassword,
        };
        const r = await api.post('/auth/login', payload);
        await login(r.data.access_token, r.data.user, r.data.active_organization_id);
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        setError(detail[0].msg);
      } else {
        setError('Authentication failed. Please check your credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (!forgotEmail.trim() || !forgotEmail.includes('@')) {
      return;
    }
    setForgotSubmitted(true);
  };

  return (
    <div className="min-h-screen flex" style={{ background: '#f8fafc' }}>
      {/* ─── Left Brand Panel ─────────────────────────────────────────── */}
      <div
        className="hidden lg:flex flex-col justify-between w-2/5 p-12 relative overflow-hidden"
        style={{ background: 'linear-gradient(160deg,#4f46e5 0%,#7c3aed 60%,#6366f1 100%)' }}
      >
        <div className="flex items-center gap-3 relative z-10">
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
            <Radar className="w-5 h-5 text-white" />
          </div>
          <span className="text-white font-bold text-xl tracking-tight">Ordexa</span>
        </div>

        <div className="space-y-8 relative z-10">
          <div>
            <h2 className="text-4xl font-bold text-white leading-snug">
              Return Intelligence<br />for modern e-commerce.
            </h2>
            <p className="text-indigo-200 mt-4 text-[15px] leading-relaxed">
              Automated reconciliation, reverse logistics visibility, and sale-linked return metrics across Flipkart, Amazon, Meesho, Shopify, and more.
            </p>
          </div>

          <div className="space-y-3">
            {[
              'Automated ingestion of marketplace sales & return reports',
              'Exact sale-linked return rate & revenue ledger tracking',
              'Descriptive SKU frequency ranking & customer state patterns',
              'Enterprise multi-tenant isolation with individual company workspaces',
            ].map(f => (
              <div key={f} className="flex items-center gap-3 text-[14px] text-indigo-100">
                <div className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center shrink-0">
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                {f}
              </div>
            ))}
          </div>
        </div>

        <p className="text-indigo-300 text-[12px] relative z-10">
          Supports Flipkart · Amazon · Meesho · Shopify · and custom Excel/CSV layouts
        </p>
      </div>

      {/* ─── Right Auth Form Panel ────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile branding */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg,#4f46e5,#7c3aed)' }}
            >
              <Radar className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-[16px] text-gray-900">Ordexa</span>
          </div>

          {/* Heading */}
          <h1 className="text-2xl font-bold text-gray-900 mb-1">
            {isSignUp ? 'Create your Ordexa account' : 'Welcome back'}
          </h1>
          <p className="text-[14px] text-gray-500 mb-6">
            {isSignUp ? 'Start analyzing returns with your own company workspace.' : 'Sign in to your Ordexa workspace.'}
          </p>

          {/* Tabs */}
          <div className="flex bg-gray-100 p-1 rounded-xl mb-6">
            <button
              type="button"
              onClick={() => { setIsSignUp(false); setError(null); }}
              className={`flex-1 py-2 text-[13px] font-semibold rounded-lg transition-all ${
                !isSignUp ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setIsSignUp(true); setError(null); }}
              className={`flex-1 py-2 text-[13px] font-semibold rounded-lg transition-all ${
                isSignUp ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mb-4 p-3.5 rounded-xl text-[13px] font-medium bg-rose-50 text-rose-700 border border-rose-100 flex items-start gap-2.5 animate-fadeIn">
              <Info className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Success Banner */}
          {successMsg && (
            <div className="mb-4 p-3.5 rounded-xl text-[13px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-100 flex items-start gap-2.5 animate-fadeIn">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Auth Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignUp ? (
              /* Create Account Fields */
              <>
                <div>
                  <label htmlFor="signup-company" className="block text-[13px] font-semibold text-gray-700 mb-1.5">
                    Company Name <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Building2 className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="signup-company"
                      name="organization"
                      type="text"
                      required
                      autoComplete="organization"
                      placeholder="e.g. Apex Retail Enterprises"
                      value={companyName}
                      onChange={e => setCompanyName(e.target.value)}
                      className="input pl-10 text-[13px]"
                      style={{ paddingLeft: '38px' }}
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="signup-name" className="block text-[13px] font-semibold text-gray-700 mb-1.5">
                    Full Name <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <UserIcon className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="signup-name"
                      name="name"
                      type="text"
                      required
                      autoComplete="name"
                      placeholder="e.g. Alex Sharma"
                      value={name}
                      onChange={e => setName(e.target.value)}
                      className="input pl-10 text-[13px]"
                      style={{ paddingLeft: '38px' }}
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="signup-email" className="block text-[13px] font-semibold text-gray-700 mb-1.5">
                    Email <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="signup-email"
                      name="email"
                      type="email"
                      required
                      autoComplete="email"
                      placeholder="you@company.com"
                      value={signUpEmail}
                      onChange={e => setSignUpEmail(e.target.value)}
                      className="input pl-10 text-[13px]"
                      style={{ paddingLeft: '38px' }}
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="signup-password" className="block text-[13px] font-semibold text-gray-700 mb-1.5">
                    Password <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="signup-password"
                      name="new-password"
                      type={showSignUpPassword ? "text" : "password"}
                      required
                      autoComplete="new-password"
                      placeholder="••••••••"
                      value={signUpPassword}
                      onChange={e => setSignUpPassword(e.target.value)}
                      className="input pl-10 pr-10 text-[13px]"
                      style={{ paddingLeft: '38px', paddingRight: '38px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowSignUpPassword(!showSignUpPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none transition-colors"
                      aria-label={showSignUpPassword ? "Hide password" : "Show password"}
                      tabIndex={-1}
                    >
                      {showSignUpPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="signup-confirm-password" className="block text-[13px] font-semibold text-gray-700 mb-1.5">
                    Confirm Password <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="signup-confirm-password"
                      name="confirm-password"
                      type={showConfirmPassword ? "text" : "password"}
                      required
                      autoComplete="new-password"
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={e => setConfirmPassword(e.target.value)}
                      className="input pl-10 pr-10 text-[13px]"
                      style={{ paddingLeft: '38px', paddingRight: '38px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none transition-colors"
                      aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                      tabIndex={-1}
                    >
                      {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full justify-center py-2.5 mt-3 text-[13px]"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>Create Account</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </>
            ) : (
              /* Sign In Fields */
              <>
                <div>
                  <label htmlFor="signin-email" className="block text-[13px] font-semibold text-gray-700 mb-1.5">
                    Email
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="signin-email"
                      name="email"
                      type="email"
                      required
                      autoComplete="email"
                      placeholder="seller@example.com"
                      value={signInEmail}
                      onChange={e => setSignInEmail(e.target.value)}
                      className="input pl-10 text-[13px]"
                      style={{ paddingLeft: '38px' }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label htmlFor="signin-password" className="block text-[13px] font-semibold text-gray-700">
                      Password
                    </label>
                    <button
                      type="button"
                      onClick={() => { setShowForgotModal(true); setForgotSubmitted(false); }}
                      className="text-[12px] font-semibold text-indigo-600 hover:text-indigo-800 hover:underline"
                    >
                      Forgot password?
                    </button>
                  </div>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="signin-password"
                      name="password"
                      type={showSignInPassword ? "text" : "password"}
                      required
                      autoComplete="current-password"
                      placeholder="••••••••"
                      value={signInPassword}
                      onChange={e => setSignInPassword(e.target.value)}
                      className="input pl-10 pr-10 text-[13px]"
                      style={{ paddingLeft: '38px', paddingRight: '38px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowSignInPassword(!showSignInPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none transition-colors"
                      aria-label={showSignInPassword ? "Hide password" : "Show password"}
                      tabIndex={-1}
                    >
                      {showSignInPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full justify-center py-2.5 mt-2 text-[13px]"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>Sign In</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </>
            )}
          </form>
        </div>
      </div>

      {/* ─── Forgot Password Modal ────────────────────────────────────── */}
      {showForgotModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-200 max-w-sm w-full p-6 space-y-4 animate-scaleUp">
            <h3 className="text-base font-bold text-gray-900">Reset your password</h3>
            {forgotSubmitted ? (
              <div className="space-y-3">
                <div className="p-3 bg-emerald-50 border border-emerald-100 rounded-xl text-[13px] text-emerald-800">
                  Password reset link has been dispatched to <strong>{forgotEmail}</strong> if an account exists.
                </div>
                <button
                  onClick={() => setShowForgotModal(false)}
                  className="btn-primary w-full justify-center text-[12px]"
                >
                  Back to Sign In
                </button>
              </div>
            ) : (
              <form onSubmit={handleForgotPassword} className="space-y-3">
                <p className="text-[13px] text-gray-500">
                  Enter your registered email address and we'll send you instructions to reset your password.
                </p>
                <div>
                  <input
                    type="email"
                    required
                    placeholder="name@company.com"
                    value={forgotEmail}
                    onChange={e => setForgotEmail(e.target.value)}
                    className="input text-[13px]"
                  />
                </div>
                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowForgotModal(false)}
                    className="btn-secondary text-[12px]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn-primary text-[12px]"
                  >
                    Send Instructions
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
