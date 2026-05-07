import axios from "axios";
import { API } from "../api";

const api = axios.create({
  baseURL: API,
});

export default api;
