import axios from "axios";
import { hashPassword } from "../utils/passwordHash";

const API_URL = import.meta.env.VITE_SERVER_URL || "http://localhost:5000";

export const registerUser = async (fullName, email, password) => {
    const hashedPassword = await hashPassword(password);
    const response = await axios.post(`${API_URL}/users/register`, {
        name: fullName,
        email,
        password: hashedPassword,
    });
    return response.data;
};

export const loginUser = async (email, password) => {
    const hashedPassword = await hashPassword(password);
    const response = await axios.get(`${API_URL}/users/login`, {
        params: {
            email,
            password: hashedPassword,
        },
    });
    return response.data;
};

export const updateUserProfile = async (userId, name) => {
    if (!userId) {
        return { success: false, message: "User ID is required" };
    }
    if (!name?.trim()) {
        return { success: false, message: "Name is required" };
    }
    try {
        const response = await axios.patch(`${API_URL}/users/profile`, {
            user_id: userId,
            name: name.trim(),
        });
        if (response.data.success) {
            return response.data;
        }
    } catch (error) {
        return {
            success: false,
            message: error.response?.data?.message || error.message || "Failed to update profile",
        };
    }
    return { success: false, message: "Failed to update profile" };
};

export const saveOplFile = async (oplFile, userId, fileName = "") => {
    const response = await axios.post(`${API_URL}/file/save`, {
        opl: oplFile,
        user_id: userId,
        file_name: fileName,
    });

    if (response.data.success) {
        return response.data;
    }

    return { success: false, message: response.data.message || "Failed to save OPL file" };
};

export const getOplEvaluation = async (oplId) => {
    const response = await axios.get(`${API_URL}/file/evaluation/${oplId}`);
    return response.data;
};

export const streamGenerateProject = async (
    oplId,
    userId,
    filename,
    { onProgress, onDone, onError, signal } = {}
) => {
    const params = new URLSearchParams({
        opl_id: oplId,
        user_id: userId,
        filename: filename || "generated_project.zip",
    });

    const response = await fetch(`${API_URL}/agent/generate?${params}`, {
        headers: { Accept: "text/event-stream" },
        signal,
    });

    if (!response.ok || !response.body) {
        throw new Error(`Generation stream failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let donePayload = null;

    const parseEventLine = (rawEvent) => {
        const dataLine = rawEvent
            .split("\n")
            .find((line) => line.startsWith("data:"));
        if (!dataLine) return;

        try {
            const payload = JSON.parse(dataLine.slice(5).trim());
            if (payload.type === "done") {
                donePayload = payload;
                return;
            }
            if (payload.type === "error") {
                onError?.(payload);
                return;
            }
            onProgress?.(payload);
        } catch {
            /* ignore malformed event lines */
        }
    };

    const flushBuffer = (final = false) => {
        let delimiter;
        while ((delimiter = buffer.indexOf("\n\n")) !== -1) {
            const rawEvent = buffer.slice(0, delimiter);
            buffer = buffer.slice(delimiter + 2);
            parseEventLine(rawEvent);
            if (donePayload) return;
        }

        if (final && buffer.trim()) {
            parseEventLine(buffer);
            buffer = "";
        }
    };

    const stopStream = async () => {
        try {
            await reader.cancel();
        } catch {
            /* stream may already be closed */
        }
    };

    // Parse the SSE stream. Stop as soon as the done event arrives — do not wait
    // for the server to close the connection (keep-alive can hang reader.read()).
    while (true) {
        const { done, value } = await reader.read();

        if (value) {
            buffer += decoder.decode(value, { stream: true });
            flushBuffer();
            if (donePayload) {
                await stopStream();
                break;
            }
        }

        if (done) {
            buffer += decoder.decode(undefined, { stream: true });
            flushBuffer(true);
            break;
        }
    }

    if (donePayload) {
        await onDone?.(donePayload);
    }
};

export const getMyProjects = async (userId, { skip = 0, limit = 20 } = {}) => {
    if (!userId) {
        return { success: false, message: "User ID is required" };
    }
    try {
        const response = await axios.get(`${API_URL}/file/myprojects/${userId}`, {
            params: { skip, limit },
        });
        if (response.data.success) {
            return response.data;
        }
    } catch (error) {
        return { success: false, message: error.response?.data?.message || error.message || "Failed to get my projects" };
    }
    return { success: false, message: "Failed to get my projects" };
};

export const getProjectOpl = async (oplId, userId) => {
    if (!oplId || !userId) {
        return { success: false, message: "Project ID and user ID are required" };
    }
    try {
        const response = await axios.get(`${API_URL}/file/opl/${oplId}`, {
            params: { user_id: userId },
        });
        if (response.data.success) {
            return response.data;
        }
    } catch (error) {
        return { success: false, message: error.response?.data?.message || error.message || "Failed to load OPL content" };
    }
    return { success: false, message: "Failed to load OPL content" };
};

export const downloadStoredProject = async (oplId, userId, filename, { signal } = {}) => {
    const params = new URLSearchParams({ user_id: userId });

    const response = await fetch(`${API_URL}/file/download/${oplId}?${params}`, {
        signal,
    });

    if (!response.ok) {
        let message = `Download failed (${response.status})`;
        try {
            const payload = await response.json();
            message = payload.message || message;
        } catch {
            /* keep default message */
        }
        throw new Error(message);
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
        const payload = await response.json();
        throw new Error(payload.message || "Download failed");
    }

    const blob = await response.blob();
    return { blob, filename: filename || "generated_project.zip" };
};

export const launchProjectInVscode = async (downloadId, userId) => {
    if (!downloadId || !userId) {
        return { success: false, message: "Download ID and user ID are required" };
    }
    try {
        const response = await axios.post(`${API_URL}/agent/launch`, {
            download_id: downloadId,
            user_id: userId,
        });
        if (response.data.success) {
            return response.data;
        }
    } catch (error) {
        return {
            success: false,
            message: error.response?.data?.message || error.message || "Failed to open project in VS Code",
        };
    }
    return { success: false, message: "Failed to open project in VS Code" };
};

export const downloadGeneratedProject = async (downloadId, userId, filename, { signal } = {}) => {
    const params = new URLSearchParams({
        download_id: downloadId,
        user_id: userId,
    });

    const response = await fetch(`${API_URL}/agent/generate/download?${params}`, {
        signal,
    });

    if (!response.ok) {
        let message = `Download failed (${response.status})`;
        try {
            const payload = await response.json();
            message = payload.message || message;
        } catch {
            /* keep default message */
        }
        throw new Error(message);
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
        const payload = await response.json();
        throw new Error(payload.message || "Download failed");
    }

    const blob = await response.blob();
    return { blob, filename: filename || "generated_project.zip" };
};
