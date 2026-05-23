import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    PlusIcon,
    ProfileIcon,
    LogoutIcon,
} from "../../assets/Icons";

const NavBar = ({ currentView, setCurrentView }) => {
    const navigate = useNavigate();

    const [user, setUser] = useState({
        name: "Guest",
        email: "",
    });

    useEffect(() => {
        const storedUser = localStorage.getItem("user");

        if (storedUser) {
            try {
                setUser(JSON.parse(storedUser));
            } catch {
                localStorage.removeItem("user");
            }
        }
    }, []);

    const handleLogout = () => {
        localStorage.removeItem("user");
        navigate("/login");
    };

    const navItems = [
        {
            id: "newProject",
            label: "New Project",
            icon: PlusIcon,
            path: "/newproject",
        },
        {
            id: "profile",
            label: "Profile",
            icon: ProfileIcon,
            path: "/profile",
        },
    ];

    return (
        <aside className="flex h-screen w-72 flex-col border-r border-violet-100 bg-gradient-to-b from-[#f7f4ff] via-[#fcfbff] to-[#eef4ff] px-6 py-8 shadow-sm">

            {/* Logo */}
            <div className="mb-10">
                <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-orange-400 via-pink-500 to-purple-600 shadow-lg shadow-pink-200/40">
                        <span className="text-lg font-black tracking-tight text-white">
                            AI
                        </span>
                    </div>

                    <div>
                        <h2 className="text-2xl font-black tracking-tight text-slate-800">
                            CodeGen
                        </h2>

                        <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                            Workspace
                        </p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1">
                <p className="mb-4 px-4 text-xs font-bold uppercase tracking-[0.18em] text-slate-400">
                    Menu
                </p>

                <div className="space-y-2">
                    {navItems.map((item) => {
                        const isActive = currentView === item.id;
                        const Icon = item.icon;

                        return (
                            <button
                                key={item.id}
                                type="button"
                                onClick={() => {
                                    setCurrentView(item.id);
                                    navigate(item.path);
                                }}
                                className={`group relative flex w-full items-center gap-4 rounded-2xl px-4 py-3.5 text-sm font-semibold transition-all duration-200 ${isActive
                                    ? "bg-white/90 text-violet-700 shadow-md shadow-violet-100 ring-1 ring-violet-100"
                                    : "text-slate-600 hover:bg-white/60 hover:text-violet-700"
                                    }`}
                            >
                                {/* Active glow */}
                                {isActive && (
                                    <div className="absolute inset-y-2 left-0 w-1 rounded-full bg-gradient-to-b from-violet-400 to-fuchsia-400" />
                                )}

                                <Icon
                                    className={`h-5 w-5 transition-colors duration-200 ${isActive
                                        ? "text-violet-500"
                                        : "text-slate-400 group-hover:text-violet-400"
                                        }`}
                                />

                                <span>{item.label}</span>
                            </button>
                        );
                    })}
                </div>
            </nav>
            {/* User Card */}
            <div className="flex items-center justify-between rounded-[1.5rem] border border-white/60 bg-white/70 px-4 py-3 shadow-lg shadow-violet-100/30 backdrop-blur-xl">

                <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-pink-100 to-violet-100 text-xs font-bold text-violet-600">
                        {user?.name?.charAt(0)?.toUpperCase() || "G"}
                    </div>

                    <div className="min-w-0">
                        <h4 className="truncate text-sm font-semibold text-slate-700">
                            {user?.name || "Guest"}
                        </h4>

                        <p className="truncate text-xs text-slate-400">
                            {user?.email || ""}
                        </p>
                    </div>
                </div>

                {/* Small Sign Out */}
                <button
                    type="button"
                    onClick={handleLogout}
                    className="group flex shrink-0 items-center gap-1 rounded-xl px-2.5 py-2 text-xs font-medium text-slate-400 transition-all duration-200 hover:bg-rose-50 hover:text-rose-500"
                >
                    <LogoutIcon className="h-4 w-4 transition-colors duration-200 group-hover:text-rose-500" />
                </button>
            </div>
        </aside>
    );
};

export default NavBar;