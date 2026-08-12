import React, { useEffect, useState } from "react";
import { updateUserProfile } from "../../services/UserService";

const Profile = () => {
    const [user, setUser] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editedName, setEditedName] = useState("");
    const [isSaving, setIsSaving] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

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

    const handleEdit = () => {
        if (!user) return;
        setEditedName(user.name || "");
        setIsEditing(true);
        setMessage("");
        setError("");
    };

    const handleSave = async () => {
        if (!user?.id) {
            setError("User ID not found. Please log in again");
            return;
        }

        const trimmedName = editedName.trim();
        if (!trimmedName) {
            setError("Name cannot be empty");
            return;
        }

        setIsSaving(true);
        setError("");
        setMessage("");

        const result = await updateUserProfile(user.id, trimmedName);

        if (!result.success) {
            setError(result.message || "Failed to update profile");
            setIsSaving(false);
            return;
        }

        const updatedUser = {
            ...user,
            name: result.data?.name || trimmedName,
        };

        setUser(updatedUser);
        localStorage.setItem("user", JSON.stringify(updatedUser));
        window.dispatchEvent(new CustomEvent("user-updated", { detail: updatedUser }));
        setIsEditing(false);
        setMessage("Profile saved successfully");
        setIsSaving(false);
    };

    const handleButtonClick = () => {
        if (isEditing) {
            handleSave();
        } else {
            handleEdit();
        }
    };

    return (
        <div className="relative min-h-screen w-full overflow-hidden">
            <div className="absolute inset-0 -z-10 bg-gradient-to-br from-[#faf7ff] via-[#fcfbff] to-[#f3f6ff]" />
            <div className="absolute top-[-10rem] right-[-5rem] h-[28rem] w-[28rem] rounded-full bg-pink-200/20 blur-3xl" />
            <div className="absolute bottom-[-8rem] left-[-6rem] h-[24rem] w-[24rem] rounded-full bg-violet-200/20 blur-3xl" />

            <div className="flex min-h-screen flex-col px-10 py-10 lg:px-16">
                <div className="mb-10">
                    <h1 className="text-4xl font-bold tracking-tight text-slate-800">
                        My Profile
                    </h1>
                    <p className="mt-3 text-base text-slate-500">
                        Your account details and workspace identity.
                    </p>
                </div>

                <div className="max-w-2xl rounded-[2.5rem] border border-violet-100 bg-white/70 p-10 shadow-2xl shadow-violet-100/30 backdrop-blur-xl">
                    {error && (
                        <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-3 text-sm text-rose-700">
                            {error}
                        </div>
                    )}

                    {message && (
                        <div className="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-3 text-sm text-emerald-700">
                            {message}
                        </div>
                    )}

                    <div className="mb-8 flex items-center gap-4">
                        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-400 to-fuchsia-400 text-2xl font-bold text-white shadow-lg shadow-violet-200/40">
                            {(isEditing ? editedName : user?.name)?.charAt(0)?.toUpperCase() || "?"}
                        </div>
                        <div>
                            <p className="text-lg font-semibold text-slate-800">
                                {isEditing ? editedName || "..." : user?.name || "Guest"}
                            </p>
                            <p className="text-sm text-slate-500">
                                {user?.email || "Not signed in"}
                            </p>
                        </div>
                    </div>

                    <div className="space-y-6">
                        <div>
                            <label
                                htmlFor="profile-name"
                                className="mb-2 block text-xs font-medium uppercase tracking-wide text-violet-500"
                            >
                                Full name
                            </label>
                            {isEditing ? (
                                <input
                                    id="profile-name"
                                    type="text"
                                    value={editedName}
                                    onChange={(e) => setEditedName(e.target.value)}
                                    className="w-full rounded-2xl border border-violet-100 bg-white/80 px-4 py-3 text-sm text-slate-700 outline-none focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
                                />
                            ) : (
                                <div className="w-full rounded-2xl border border-violet-100 bg-white/80 px-4 py-3 text-sm text-slate-700">
                                    {user ? user.name : "Loading..."}
                                </div>
                            )}
                        </div>

                        <div>
                            <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-violet-500">
                                Email address
                            </label>
                            <div className="w-full rounded-2xl border border-violet-100 bg-white/80 px-4 py-3 text-sm text-slate-700">
                                {user ? user.email : "Loading..."}
                            </div>
                        </div>

                        <div className="flex justify-end pt-2">
                            <button
                                type="button"
                                onClick={handleButtonClick}
                                disabled={isSaving || !user}
                                className="rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-200/40 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {isSaving ? "Saving..." : isEditing ? "Save" : "Edit"}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Profile;
