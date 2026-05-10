import api from "./axios";

export const loginRequest = async (email, password) => {
  const response = await api.post("/login/", {
    email,
    password,
  });

  return response.data;
};

export const passwordResetRequest = async (email) => {
  const response = await api.post("/password-reset-request/", {
    email,
  });

  return response.data;
};
