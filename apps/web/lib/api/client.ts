import axios, { AxiosError } from "axios";

const baseURL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL,
  withCredentials: true, // send the session httpOnly cookie
  headers: { "Content-Type": "application/json" },
});

/** On 401 to anything except /auth/login itself, redirect to /login.
 *  Lives in the client so every API call gets it for free. */
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status;
    const url = error.config?.url ?? "";
    if (
      status === 401 &&
      !url.includes("/auth/login") &&
      typeof window !== "undefined" &&
      window.location.pathname !== "/login"
    ) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
