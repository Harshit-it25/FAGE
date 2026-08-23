import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { loginRequest, getStoredUser, clearSession, setSessionUser } from './auth';
import { apiClient } from './api';

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
    it('should successfully log in, set user session in localStorage', async () => {
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

      expect(result).toEqual(mockResponse.data);
      expect(getStoredUser()).toEqual(mockResponse.data.user);
    });

    it('should throw an error on login failure and not set the session', async () => {
      const mockError = new Error('Invalid credentials');
      (apiClient.post as any).mockRejectedValueOnce(mockError);

      await expect(loginRequest('testuser', 'wrongpass')).rejects.toThrow('Invalid credentials');
      expect(getStoredUser()).toBeNull();
    });
  });

  describe('clearSession', () => {
    it('should remove user from localStorage and call logout endpoint', async () => {
      setSessionUser({ username: 'a', role: 'b', display_name: 'c' });
      expect(getStoredUser()).toBeDefined();

      (apiClient.post as any).mockResolvedValueOnce({});
      
      await clearSession();

      expect(getStoredUser()).toBeNull();
      expect(apiClient.post).toHaveBeenCalledWith('/logout');
    });

    it('should swallow logout errors gracefully', async () => {
      setSessionUser({ username: 'a', role: 'b', display_name: 'c' });
      
      (apiClient.post as any).mockRejectedValueOnce(new Error('Logout failed'));
      
      await clearSession();
      
      // Should not throw, and user should still be removed
      expect(getStoredUser()).toBeNull();
    });
  });

  describe('getStoredUser', () => {
    it('should safely handle invalid JSON in localStorage', () => {
      localStorage.setItem('fage_user', '{ invalid json ');
      const user = getStoredUser();
      expect(user).toBeNull();
    });
  });
});
