class AuthHandler {
    constructor() {
        this.setupInterceptors();
    }

    setupInterceptors() {
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const [resource, config] = args;
            
            // Get token from both localStorage and cookies
            const token = localStorage.getItem('access_token');
            
            // Prepare headers
            const headers = {
                ...(config?.headers || {}),
                'Content-Type': 'application/json',
                ...(token && {'Authorization': `Bearer ${token}`})
            };

            const authConfig = {
                ...config,
                headers,
                credentials: 'include'  // Important: Include cookies in request
            };

            try {
                const response = await originalFetch(resource, authConfig);
                
                if (response.status === 401) {
                    // Redirect to login page if unauthorized
                    window.location.href = '/auth/login';
                    return response;
                }
                
                return response;
            } catch (error) {
                console.error('Request failed:', error);
                throw error;
            }
        };
    }

    static handleLoginResponse(response) {
        const access_token = response?.access_token;
        if (access_token) {
            localStorage.setItem('access_token', access_token);
        }
    }
}

// Initialize auth handler
document.addEventListener('DOMContentLoaded', () => {
    new AuthHandler();
});