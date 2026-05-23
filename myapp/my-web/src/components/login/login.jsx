import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { registerUser, loginUser } from '../../services/UserService';

const AuthForm = () => {
  const navigate = useNavigate();
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
      localStorage.setItem('user', JSON.stringify({ name: fullName, email: email }));
      setMessage(response.message || "Registration successful!");
      setTimeout(() => navigate('/newproject'), 1000);
    } catch (error) {
      setMessage(error.response?.data?.message || error.message || "An error occurred");
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const response = await loginUser(email, password);
      localStorage.setItem('user', JSON.stringify({ name: response.name || email.split('@')[0], email: email }));
      setMessage(response.message || "Login successful!");
      setTimeout(() => navigate('/newproject'), 1000);
    } catch (error) {
      setMessage(error.response?.data?.message || error.message || "An error occurred");
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#f7f4ff] px-4">

      {/* Soft background gradients */}
      <div className="absolute -top-40 -left-32 h-[32rem] w-[32rem] rounded-full bg-pink-200/20 blur-3xl" />
      <div className="absolute bottom-0 right-0 h-[28rem] w-[28rem] rounded-full bg-violet-200/20 blur-3xl" />
      <div className="absolute top-1/3 right-1/4 h-72 w-72 rounded-full bg-sky-200/10 blur-3xl" />

      <div className="relative z-10 w-full max-w-md">

        {/* Title */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-slate-800">
            {isLogin ? "Welcome back" : "Create account"}
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            {isLogin
              ? "Sign in to continue your journey"
              : "Create your account and get started"}
          </p>
        </div>

        {/* Card */}
        <div className="rounded-[2rem] border border-white/50 bg-white/75 p-8 shadow-2xl shadow-violet-100/30 backdrop-blur-2xl">

          {message && (
            <div
              className={`mb-5 rounded-2xl px-4 py-3 text-sm ${message.toLowerCase().includes("success")
                ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border border-rose-200 bg-rose-50 text-rose-700"
                }`}
            >
              {message}
            </div>
          )}

          <form
            className="space-y-4"
            onSubmit={(e) => (isLogin ? handleLogin(e) : handleRegister(e))}
          >
            {!isLogin && (
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Full name"
                className="w-full rounded-2xl border border-slate-200/70 bg-white/80 px-4 py-3 text-sm text-slate-700 placeholder:text-slate-400 outline-none transition-all focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
              />
            )}

            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email address"
              className="w-full rounded-2xl border border-slate-200/70 bg-white/80 px-4 py-3 text-sm text-slate-700 placeholder:text-slate-400 outline-none transition-all focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
            />

            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full rounded-2xl border border-slate-200/70 bg-white/80 px-4 py-3 text-sm text-slate-700 placeholder:text-slate-400 outline-none transition-all focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
            />

            <button
              type="submit"
              className="mt-3 w-full rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-200/40 transition-all duration-300 hover:scale-[1.01] hover:shadow-xl"
            >
              {isLogin ? "Sign in" : "Create account"}
            </button>
          </form>

          <div className="mt-7 text-center">
            <p className="text-sm text-slate-500">
              {isLogin
                ? "Don't have an account?"
                : "Already have an account?"}

              <button
                type="button"
                onClick={toggleMode}
                className="ml-1.5 font-medium text-violet-500 transition hover:text-fuchsia-500"
              >
                {isLogin ? "Sign up" : "Log in"}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}; export default AuthForm;
