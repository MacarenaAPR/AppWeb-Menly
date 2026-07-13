import axios from "axios";
import { API } from "../api";

const api = axios.create({
  baseURL: API,
  timeout: 10000,
  withCredentials: true,
  headers: {
    Accept: "application/json",
  },
});

export default api;
