import axios from "axios";
import { API } from "../api";

const api = axios.create({
  baseURL: API,
  timeout: 10000,
  headers: {
    Accept: "application/json",
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");

  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export default api;
