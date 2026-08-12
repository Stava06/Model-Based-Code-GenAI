import React, { useState } from "react";
import { isLocalhost } from "../utils/isLocalhost";

const OpenInVscodeButton = ({
    launch,
    disabled = false,
    className = "rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-200/40 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60",
    showMessages = true,
}) => {
    const [isLaunching, setIsLaunching] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    if (!isLocalhost()) {
        return null;
    }

    const handleClick = async () => {
        if (disabled || isLaunching) return;

        setIsLaunching(true);
        setError("");
        setMessage("");

        try {
            const result = await launch();

            if (!result?.success) {
                setError(result?.message || "Failed to open project in VS Code");
                return;
            }

            const extractPath = result.data?.extract_path;
            setMessage(
                extractPath
                    ? "Opened in VS Code. Starting servers."
                    : "Opened in VS Code."
            );
        } catch (err) {
            setError(err.message || "Failed to open project in VS Code");
        } finally {
            setIsLaunching(false);
        }
    };

    return (
        <>
            <button
                type="button"
                onClick={handleClick}
                disabled={disabled || isLaunching}
                className={className}
            >
                {isLaunching ? "Opening..." : "Open in VS Code"}
            </button>

            {showMessages && error && (
                <p className="w-full basis-full text-right text-xs text-rose-600">{error}</p>
            )}

            {showMessages && message && (
                <p className="w-full basis-full text-right text-xs text-emerald-600">{message}</p>
            )}
        </>
    );
};

export default OpenInVscodeButton;
