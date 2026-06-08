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

export const generateProject = async (oplId, userId, filename, onProgress) => {
    const response = await axios.get(`${API_URL}/agent/generate`, {
        params: {
            opl_id: oplId,
            user_id: userId,
            filename: filename || "generated_project.zip",
        },
        responseType: "blob",
        timeout: 600000,
        onDownloadProgress: (event) => {
            if (onProgress && event.total) {
                onProgress(Math.round((event.loaded / event.total) * 100));
            }
        },
    });
    return response;
};
