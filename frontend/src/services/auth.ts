import { apiClient } from './api';

const USER_KEY = 'fage_user';

export interface AuthUser {
  username: string;
  role: string;
  display_name: string;
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setSessionUser(user: AuthUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export async function clearSession() {
  localStorage.removeItem(USER_KEY);
  try {
    await apiClient.post('/logout');
  } catch (e) {
    // Ignore logout errors
  }
}

export async function loginRequest(username: string, password: string) {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  const response = await apiClient.post<{
    access_token: string;
    token_type: string;
    expires_in: number;
    user: AuthUser;
  }>('/token', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  setSessionUser(response.data.user);
  return response.data;
}
