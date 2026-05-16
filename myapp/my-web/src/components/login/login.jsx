import React, { useState } from 'react';

const AuthForm = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [hovered, setHovered] = useState(false);

  const toggleMode = () => setIsLogin(!isLogin);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-50 font-sans text-slate-800">

      {/* Background glowing orbs */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-70">
        <div className="absolute top-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-sky-400/30 mix-blend-multiply blur-[120px] filter animate-pulse"></div>
        <div className="absolute bottom-[-20%] right-[-10%] h-[600px] w-[600px] rounded-full bg-cyan-400/30 mix-blend-multiply blur-[120px] filter animate-pulse" style={{ animationDelay: '2s' }}></div>
      </div>

      {/* Main Card */}
      <div className="relative z-10 w-full max-w-md p-8 sm:p-10">

        {/* Glow behind card */}
        <div className="absolute inset-0 z-0 bg-gradient-to-b from-sky-200/50 to-transparent blur-2xl rounded-3xl"></div>

        <div className="relative z-10 rounded-3xl border border-white/60 bg-white/70 p-8 shadow-2xl backdrop-blur-2xl ring-1 ring-slate-900/5">

          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-sky-100 border border-sky-200 shadow-sm">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-sky-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h2 className="bg-gradient-to-br from-slate-900 via-sky-800 to-cyan-700 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
              {isLogin ? 'Welcome back' : 'Create an account'}
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              {isLogin ? 'Enter your credentials to access your account' : 'Sign up to get started with our platform'}
            </p>
          </div>

          <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
            {!isLogin && (
              <div className="space-y-1 text-left">
                <label htmlFor="name" className="text-xs font-medium text-slate-600 pl-1">Full Name</label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                  </div>
                  <input
                    type="text"
                    id="name"
                    placeholder="John Doe"
                    className="block w-full rounded-xl border border-slate-200 bg-white/50 py-3 pl-10 pr-4 text-sm text-slate-900 placeholder-slate-400 shadow-sm transition-all hover:bg-white focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-sky-500/10"
                  />
                </div>
              </div>
            )}

            <div className="space-y-1 text-left">
              <label htmlFor="email" className="text-xs font-medium text-slate-600 pl-1">Email Address</label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" /></svg>
                </div>
                <input
                  type="email"
                  id="email"
                  placeholder="john@example.com"
                  className="block w-full rounded-xl border border-slate-200 bg-white/50 py-3 pl-10 pr-4 text-sm text-slate-900 placeholder-slate-400 shadow-sm transition-all hover:bg-white focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-sky-500/10"
                />
              </div>
            </div>

            <div className="space-y-1 text-left">
              <div className="flex items-center justify-between pl-1 pr-1">
                <label htmlFor="password" className="text-xs font-medium text-slate-600">Password</label>
                {isLogin && <a href="#" className="text-xs font-medium text-sky-600 hover:text-sky-700 transition-colors">Forgot password?</a>}
              </div>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
                </div>
                <input
                  type="password"
                  id="password"
                  placeholder="••••••••"
                  className="block w-full rounded-xl border border-slate-200 bg-white/50 py-3 pl-10 pr-4 text-sm text-slate-900 placeholder-slate-400 shadow-sm transition-all hover:bg-white focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-sky-500/10"
                />
              </div>
            </div>

            <button
              type="submit"
              onMouseEnter={() => setHovered(true)}
              onMouseLeave={() => setHovered(false)}
              className="group relative mt-6 w-full overflow-hidden rounded-xl bg-gradient-to-br from-sky-500 to-cyan-500 px-4 py-3 text-sm font-semibold text-white shadow-md transition-all hover:from-sky-400 hover:to-cyan-400 hover:shadow-lg active:scale-[0.98]"
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
            <p className="text-sm text-slate-500">
              {isLogin ? "Don't have an account?" : "Already have an account?"}
              <button
                type="button"
                className="ml-1.5 font-semibold text-sky-600 hover:text-sky-700 transition-colors underline-offset-4 hover:underline"
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
