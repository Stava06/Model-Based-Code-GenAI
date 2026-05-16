import React, { useState } from 'react';
import { registerUser, loginUser } from '../services/UserService';

const AuthForm = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [hovered, setHovered] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [message, setMessage] = useState('');

  const toggleMode = () => setIsLogin(!isLogin);

  const handleRegister = async (e) => {
    e.preventDefault();
    try {
      const response = await registerUser(fullName, email, password);
      setMessage(response.message || "Registration successful!");
    } catch (error) {
      setMessage(error.response?.data?.message || error.message || "An error occurred");
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const response = await loginUser(email, password);
      setMessage(response.message || "Login successful!");
    } catch (error) {
      setMessage(error.response?.data?.message || error.message || "An error occurred");
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 font-sans text-slate-200">

      {/* Background glowing orbs */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-70">
        <div className="absolute top-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-red-600/30 mix-blend-screen blur-[120px] filter animate-pulse"></div>
        <div className="absolute bottom-[-20%] right-[-10%] h-[600px] w-[600px] rounded-full bg-blue-600/30 mix-blend-screen blur-[120px] filter animate-pulse" style={{ animationDelay: '2s' }}></div>
        <div className="absolute top-[20%] right-[20%] h-[400px] w-[400px] rounded-full bg-purple-600/30 mix-blend-screen blur-[100px] filter animate-pulse" style={{ animationDelay: '4s' }}></div>
      </div>

      {/* Main Card */}
      <div className="relative z-10 w-full max-w-md p-8 sm:p-10">

        {/* Glow behind card */}
        <div className="absolute inset-0 z-0 bg-gradient-to-br from-red-500/20 via-purple-500/20 to-blue-500/20 blur-2xl rounded-3xl"></div>

        <div className="relative z-10 rounded-3xl border border-slate-700/60 bg-slate-800/70 p-8 shadow-2xl backdrop-blur-2xl ring-1 ring-white/5">

          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 border border-slate-700 shadow-sm">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h2 className="bg-gradient-to-br from-red-400 via-purple-400 to-blue-400 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
              {isLogin ? 'Welcome back' : 'Create an account'}
            </h2>
            <p className="mt-2 text-sm text-slate-400">
              {isLogin ? 'Enter your credentials to access your account' : 'Sign up to get started with our platform'}
            </p>
          </div>

          {message && (
            <div className={`mb-6 rounded-xl p-3 text-sm text-center ${message.toLowerCase().includes('success') ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
              {message}
            </div>
          )}

          <form className="space-y-4" onSubmit={(e) => { isLogin ? handleLogin(e) : handleRegister(e) }}>
            {!isLogin && (
              <div className="space-y-1 text-left">
                <label htmlFor="name" className="text-xs font-medium text-slate-300 pl-1">Full Name</label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                  </div>
                  <input
                    type="text"
                    id="name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="John Doe"
                    className="block w-full rounded-xl border border-slate-700 bg-slate-900/50 py-3 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 shadow-sm transition-all hover:bg-slate-800/50 focus:border-purple-500 focus:bg-slate-900/50 focus:outline-none focus:ring-4 focus:ring-purple-500/20"
                  />
                </div>
              </div>
            )}

            <div className="space-y-1 text-left">
              <label htmlFor="email" className="text-xs font-medium text-slate-300 pl-1">Email Address</label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" /></svg>
                </div>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="john@example.com"
                  className="block w-full rounded-xl border border-slate-700 bg-slate-900/50 py-3 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 shadow-sm transition-all hover:bg-slate-800/50 focus:border-purple-500 focus:bg-slate-900/50 focus:outline-none focus:ring-4 focus:ring-purple-500/20"
                />
              </div>
            </div>

            <div className="space-y-1 text-left">
              <div className="flex items-center justify-between pl-1 pr-1">
                <label htmlFor="password" className="text-xs font-medium text-slate-300">Password</label>
                {isLogin && <a href="#" className="text-xs font-medium text-purple-400 hover:text-purple-300 transition-colors">Forgot password?</a>}
              </div>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
                </div>
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="block w-full rounded-xl border border-slate-700 bg-slate-900/50 py-3 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 shadow-sm transition-all hover:bg-slate-800/50 focus:border-purple-500 focus:bg-slate-900/50 focus:outline-none focus:ring-4 focus:ring-purple-500/20"
                />
              </div>
            </div>

            <button
              type="submit"
              onMouseEnter={() => setHovered(true)}
              onMouseLeave={() => setHovered(false)}
              className="group relative mt-6 w-full overflow-hidden rounded-xl bg-gradient-to-r from-red-500 via-purple-500 to-blue-500 px-4 py-3 text-sm font-semibold text-white shadow-md transition-all hover:from-red-400 hover:via-purple-400 hover:to-blue-400 hover:shadow-lg active:scale-[0.98]"
            >
              <span className="relative z-10 flex items-center justify-center gap-2">
                {isLogin ? 'Sign In' : 'Create Account'}
                <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform duration-300 ${hovered ? 'translate-x-1' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
              </span>
              {/* Shine effect */}
              <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-1000 group-hover:translate-x-full"></div>
            </button>
          </form>



          <div className="mt-8 text-center">
            <p className="text-sm text-slate-400">
              {isLogin ? "Don't have an account?" : "Already have an account?"}
              <button
                type="button"
                className="ml-1.5 font-semibold text-purple-400 hover:text-purple-300 transition-colors underline-offset-4 hover:underline"
                onClick={toggleMode}
              >
                {isLogin ? 'Sign up' : 'Log in'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthForm;
