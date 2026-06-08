import React, { useEffect, useState } from 'react';

const Profile = () => {
    const [user, setUser] = useState(null);

    useEffect(() => {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
            setUser(JSON.parse(storedUser));
        }
    }, []);

    return (
        <div className="max-w-4xl mx-auto">
            <div className="mb-8 relative inline-block">
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight">My Profile</h1>
                <div className="absolute -bottom-2 left-0 w-1/2 h-1 bg-gradient-to-r from-orange-500 to-transparent rounded-full"></div>
            </div>

            <div className="relative rounded-3xl border border-white/60 bg-white/70 p-8 shadow-2xl backdrop-blur-2xl ring-1 ring-black/5 overflow-hidden">
                {/* Glow behind card content */}
                <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 bg-pink-500/10 blur-[80px] rounded-full pointer-events-none"></div>

                <div className="relative z-10 flex flex-col md:flex-row items-center md:items-start gap-10">
                    <div className="flex-1 w-full space-y-6">
                        <div className="space-y-1">
                            <label className="block text-xs font-medium text-slate-500 pl-1 uppercase tracking-wider">Full Name</label>
                            <div className="relative">
                                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                                </div>
                                <div className="flex items-center w-full rounded-xl border border-slate-300 bg-white/50 py-3.5 pl-12 pr-4 text-sm text-slate-800 shadow-sm transition-all hover:bg-white/80">
                                    {user ? user.name : 'Loading...'}
                                </div>
                            </div>
                        </div>

                        <div className="space-y-1">
                            <label className="block text-xs font-medium text-slate-500 pl-1 uppercase tracking-wider">Email Address</label>
                            <div className="relative">
                                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" /></svg>
                                </div>
                                <div className="flex items-center w-full rounded-xl border border-slate-300 bg-white/50 py-3.5 pl-12 pr-4 text-sm text-slate-800 shadow-sm transition-all hover:bg-white/80">
                                    {user ? user.email : 'Loading...'}
                                </div>
                            </div>
                        </div>

                        <div className="pt-6 flex justify-end">
                            <button className="group relative overflow-hidden rounded-xl bg-gradient-brand px-6 py-3 text-sm font-semibold text-white shadow-md shadow-pink-500/20 transition-all hover:opacity-90 hover:shadow-lg hover:shadow-pink-500/30 active:scale-[0.98]">
                                <span className="relative z-10 flex items-center gap-2">
                                    Save Changes
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 transition-transform group-hover:translate-x-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
                                </span>
                                {/* Shine effect */}
                                <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-700 group-hover:translate-x-full"></div>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Profile;
