class AdminHandler {
    constructor() {
        this.setupCreateUserForm();
    }

    setupCreateUserForm() {
        const form = document.getElementById('createUserForm');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.disabled = true;

            try {
                // Convert form data to JSON format
                const formData = new FormData(form);
                const jsonData = {};
                formData.forEach((value, key) => {
                    jsonData[key] = value;
                });

                const response = await fetch('/admin/users/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    },
                    body: JSON.stringify(jsonData)
                });

                if (response.status === 401) {
                    window.location.href = '/auth/login';
                    return;
                }

                if (response.redirected) {
                    window.location.href = response.url;
                    return;
                }

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.message || 'Failed to create user');
                }

                // Successful creation - redirect to dashboard
                window.location.href = '/admin/dashboard';

            } catch (error) {
                console.error('Error creating user:', error);
                const flashMessage = document.createElement('div');
                flashMessage.className = 'alert alert-error mb-4 p-4 rounded-lg bg-red-100 text-red-700';
                flashMessage.textContent = error.message || 'An unexpected error occurred. Please try again.';
                form.insertBefore(flashMessage, form.firstChild);
            } finally {
                submitButton.disabled = false;
            }
        });
    }
}

// Initialize admin handler
document.addEventListener('DOMContentLoaded', () => {
    new AdminHandler();
});