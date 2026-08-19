import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { loginRequest, getStoredToken, getStoredUser, clearSession, setSession, bootstrapAuthHeaders } from './auth';
import { apiClient } from './api';

// Mock the API client to prevent any real network calls
vi.mock('./api', () => ({
  apiClient: {
    post: vi.fn(),
    defaults: {
      headers: {
        common: {}
      }
    }
  }
}));

describe('Auth Service', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    apiClient.defaults.headers.common = {};
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('loginRequest', () => {
    it('should successfully log in, set session in localStorage, and update headers', async () => {
      const mockResponse = {
        data: {
          access_token: 'fake-token-123',
          token_type: 'bearer',
          expires_in: 3600,
          user: {
            username: 'testuser',
            role: 'admin',
            display_name: 'Test User'
          }
        }
      };

      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      const result = await loginRequest('testuser', 'password123');

      expect(apiClient.post).toHaveBeenCalledWith(
        '/token',
        expect.any(URLSearchParams),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );

      // Check return value
      expect(result).toEqual(mockResponse.data);

      // Check localStorage
      expect(getStoredToken()).toBe('fake-token-123');
      expect(getStoredUser()).toEqual(mockResponse.data.user);

      // Check headers
      expect(apiClient.defaults.headers.common['Authorization']).toBe('Bearer fake-token-123');
    });

    it('should throw an error on login failure and not set the session', async () => {
      const mockError = new Error('Invalid credentials');
      (apiClient.post as any).mockRejectedValueOnce(mockError);

      await expect(loginRequest('testuser', 'wrongpass')).rejects.toThrow('Invalid credentials');

      // Check session is untouched
      expect(getStoredToken()).toBeNull();
      expect(getStoredUser()).toBeNull();
      expect(apiClient.defaults.headers.common['Authorization']).toBeUndefined();
    });
  });

  describe('clearSession', () => {
    it('should remove token and user from localStorage and delete the authorization header', () => {
      setSession('fake-token', { username: 'a', role: 'b', display_name: 'c' });
      
      expect(getStoredToken()).toBe('fake-token');
      expect(apiClient.defaults.headers.common['Authorization']).toBeDefined();

      clearSession();

      expect(getStoredToken()).toBeNull();
      expect(getStoredUser()).toBeNull();
      expect(apiClient.defaults.headers.common['Authorization']).toBeUndefined();
    });
  });

  describe('getStoredUser', () => {
    it('should safely handle invalid JSON in localStorage', () => {
      localStorage.setItem('fage_user', '{ invalid json ');
      
      const user = getStoredUser();
      
      expect(user).toBeNull();
    });
  });

  describe('bootstrapAuthHeaders', () => {
    it('should set headers if a token exists in localStorage', () => {
      localStorage.setItem('fage_access_token', 'bootstrap-token');
      
      bootstrapAuthHeaders();
      
      expect(apiClient.defaults.headers.common['Authorization']).toBe('Bearer bootstrap-token');
    });

    it('should not set headers if no token exists', () => {
      bootstrapAuthHeaders();
      
      expect(apiClient.defaults.headers.common['Authorization']).toBeUndefined();
    });
  });
});
