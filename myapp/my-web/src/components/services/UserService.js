import axios from "axios";

const API_URL = import.meta.env.VITE_SERVER_URL || "http://localhost:5000";

// Register user
export const registerUser = async (fullName, email, password) => {
    const response = await axios.post(`${API_URL}/users/register`, { fullName, email, password });
    console.log(`${response.data}`);
    return response.data;
}

export const loginUser = async (email, password) => {
    const response = await axios.post(`${API_URL}/users/login`, { email, password });
    console.log(`${response.data}`);
    return response.data;
}