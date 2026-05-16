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
    const response = await axios.post(`${API_URL}/users/login`, {
        email,
        password: hashedPassword,
    });
    return response.data;
};
