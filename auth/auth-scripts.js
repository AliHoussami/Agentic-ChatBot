class AuthHandler {
    constructor() {
        this.isLoginPage = window.location.pathname.includes('login');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.toastContainer = document.getElementById('toastContainer');
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.checkBackendConnection();
        this.initializePasswordToggle();
        
        if (!this.isLoginPage) {
            this.initializePasswordStrength();
            this.initializePasswordMatch();
        }
    }
    
    setupEventListeners() {
        const form = document.getElementById(this.isLoginPage ? 'loginForm' : 'signupForm');
        const button = document.getElementById(this.isLoginPage ? 'loginButton' : 'signupButton');
        
        form.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // Real-time validation for inputs
        const inputs = form.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateInput(input));
            input.addEventListener('input', () => this.clearInputError(input));
        });
        
        // Social login buttons
        const socialButtons = document.querySelectorAll('.social-button');
        socialButtons.forEach(button => {
            button.addEventListener('click', (e) => this.handleSocialLogin(e));
        });
    }
    
    initializePasswordToggle() {
        const toggleButtons = document.querySelectorAll('.password-toggle');
        toggleButtons.forEach(button => {
            button.addEventListener('click', () => {
                const input = button.previousElementSibling;
                const eyeIcon = button.querySelector('.eye-icon');
                const eyeOffIcon = button.querySelector('.eye-off-icon');
                
                if (input.type === 'password') {
                    input.type = 'text';
                    eyeIcon.style.display = 'none';
                    eyeOffIcon.style.display = 'block';
                } else {
                    input.type = 'password';
                    eyeIcon.style.display = 'block';
                    eyeOffIcon.style.display = 'none';
                }
            });
        });
    }
    
    initializePasswordStrength() {
        const passwordInput = document.getElementById('password');
        const strengthIndicator = document.getElementById('passwordStrength');
        const strengthFill = strengthIndicator.querySelector('.strength-fill');
        const strengthText = strengthIndicator.querySelector('.strength-text');
        
        passwordInput.addEventListener('input', () => {
            const password = passwordInput.value;
            const strength = this.calculatePasswordStrength(password);
            
            strengthFill.className = `strength-fill ${strength.level}`;
            strengthText.textContent = strength.text;
            
            if (password.length === 0) {
                strengthFill.className = 'strength-fill';
                strengthText.textContent = 'Password strength';
            }
        });
    }
    
    initializePasswordMatch() {
        const passwordInput = document.getElementById('password');
        const confirmInput = document.getElementById('confirmPassword');
        const matchIndicator = document.getElementById('passwordMatch');
        
        const checkMatch = () => {
            if (confirmInput.value.length === 0) {
                matchIndicator.classList.remove('show', 'error');
                return;
            }
            
            if (passwordInput.value === confirmInput.value) {
                matchIndicator.classList.add('show');
                matchIndicator.classList.remove('error');
            } else {
                matchIndicator.classList.add('show', 'error');
            }
        };
        
        passwordInput.addEventListener('input', checkMatch);
        confirmInput.addEventListener('input', checkMatch);
    }
    
    calculatePasswordStrength(password) {
        if (password.length === 0) return { level: '', text: 'Password strength' };
        
        let score = 0;
        
        // Length check
        if (password.length >= 8) score += 1;
        if (password.length >= 12) score += 1;
        
        // Character variety
        if (/[a-z]/.test(password)) score += 1;
        if (/[A-Z]/.test(password)) score += 1;
        if (/[0-9]/.test(password)) score += 1;
        if (/[^A-Za-z0-9]/.test(password)) score += 1;
        
        // Common patterns penalty
        if (/(.)\1{2,}/.test(password)) score -= 1; // Repeating characters
        if (/123|abc|qwe/i.test(password)) score -= 1; // Common sequences
        
        score = Math.max(0, Math.min(4, score));
        
        const levels = [
            { level: 'weak', text: 'Very weak' },
            { level: 'weak', text: 'Weak' },
            { level: 'fair', text: 'Fair' },
            { level: 'good', text: 'Good' },
            { level: 'strong', text: 'Strong' }
        ];
        
        return levels[score];
    }
    
    validateInput(input) {
        const wrapper = input.closest('.input-wrapper');
        if (!wrapper) return true;
        this.clearInputError(input);
        
        let isValid = true;
        let errorMessage = '';
        
        switch (input.type) {
            case 'email':
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(input.value)) {
                    isValid = false;
                    errorMessage = 'Please enter a valid email address';
                }
                break;
                
            case 'text': // Username
                if (input.id === 'username') {
                    if (input.value.length < 3) {
                        isValid = false;
                        errorMessage = 'Username must be at least 3 characters';
                    } else if (input.value.length > 20) {
                        isValid = false;
                        errorMessage = 'Username must be less than 20 characters';
                    } else if (!/^[a-zA-Z0-9_]+$/.test(input.value)) {
                        isValid = false;
                        errorMessage = 'Username can only contain letters, numbers, and underscores';
                    }
                }
                break;
                
            case 'password':
                if (input.id === 'password') {
                    if (input.value.length < 8) {
                        isValid = false;
                        errorMessage = 'Password must be at least 8 characters';
                    }
                } else if (input.id === 'confirmPassword') {
                    const originalPassword = document.getElementById('password').value;
                    if (input.value !== originalPassword) {
                        isValid = false;
                        errorMessage = 'Passwords do not match';
                    }
                }
                break;
        }
        
        if (!isValid) {
            wrapper.classList.add('error');
            this.showInputError(input, errorMessage);
        } else {
            wrapper.classList.add('success');
        }
        
        return isValid;
    }
    clearInputError(input) {
        const wrapper = input.closest('.input-wrapper');
        if (!wrapper) return;
        wrapper.classList.remove('error', 'success');
        const parentNode = wrapper.parentNode;
        if (!parentNode) return;
        const existingError = parentNode.querySelector('.input-error');
        if (existingError) {
            existingError.remove();
        }
        const existingSuccess = parentNode.querySelector('.input-success');
        if (existingSuccess) {
            existingSuccess.remove();
        }
    }

    showInputError(input, message) {
        const wrapper = input.closest('.input-wrapper');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'input-error';
        errorDiv.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            ${message}
        `;
        wrapper.parentNode.appendChild(errorDiv);
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        console.log('Form submitted!');
        const form = e.target;
        const button = document.getElementById(this.isLoginPage ? 'loginButton' : 'signupButton');
        const buttonText = button.querySelector('.button-text');
        const buttonLoader = button.querySelector('.button-loader');
        
        // Validate all inputs
        const inputs = form.querySelectorAll('input[required]');
        let isFormValid = true;
        
        inputs.forEach(input => {
            if (!this.validateInput(input)) {
                isFormValid = false;
            }
        });
        
        if (!this.isLoginPage) {
            // Additional signup validations
            const agreeTerms = document.getElementById('agreeTerms');
            if (!agreeTerms.checked) {
                this.showToast('Please agree to the Terms of Service and Privacy Policy', 'error');
                isFormValid = false;
            }
        }
        
        if (!isFormValid) {
            this.showToast('Please fix the errors above', 'error');
            return;
        }
        
        // Show loading state
        button.disabled = true;
        buttonText.style.display = 'none';
        buttonLoader.style.display = 'flex';
        
        try {
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            const endpoint = this.isLoginPage ? '/auth/login' : '/auth/signup';
            const response = await fetch(`http://localhost:5000${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showToast(
                    this.isLoginPage ? 'Login successful!' : 'Account created successfully!', 
                    'success'
                );
                
                // Store user info in localStorage
                localStorage.setItem('user', JSON.stringify(result.user));
                
                // Redirect to chat after a short delay
                setTimeout(() => {
                    window.location.href = '/UserInterface/chat.html';
                }, 1500);
                
            } else {
                this.showToast(result.error || 'An error occurred', 'error');
            }
            
        } catch (error) {
            console.error('Auth error:', error);
            this.showToast('Connection error. Please try again.', 'error');
        } finally {
            // Hide loading state
            button.disabled = false;
            buttonText.style.display = 'block';
            buttonLoader.style.display = 'none';
        }
    }
    
    handleSocialLogin(e) {
        e.preventDefault();
        const provider = e.currentTarget.classList.contains('google') ? 'google' : 'unknown';
        
        this.showToast(`${provider} login will be available soon!`, 'warning');
        
        // TODO: Implement actual social login
        // window.location.href = `/auth/${provider}`;
    }
    
    async checkBackendConnection() {
        try {
            const response = await fetch('http://localhost:5000/health', {
                method: 'GET',
                timeout: 3000
            });
            
            if (response.ok) {
                this.updateConnectionStatus(true);
            } else {
                this.updateConnectionStatus(false);
            }
        } catch (error) {
            this.updateConnectionStatus(false);
        }
    }
    
    updateConnectionStatus(connected) {
        if (connected) {
            this.statusIndicator.className = 'status-indicator';
        } else {
            this.statusIndicator.className = 'status-indicator error';
            this.showToast('Cannot connect to server. Please make sure the backend is running.', 'error');
        }
    }
    
    showToast(message, type = 'success') {
        const existingToasts = this.toastContainer.querySelectorAll('.toast');
        if (existingToasts.length >= 3) {
            existingToasts[0].remove();
        }
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = this.getToastIcon(type);
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div>${message}</div>
        `;
        
        this.toastContainer.appendChild(toast);
        
        // Animate in
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
        
        // Click to dismiss
        toast.addEventListener('click', () => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        });
    }
    
    getToastIcon(type) {
        const icons = {
            success: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20,6 9,17 4,12" style="stroke: #10b981;"/>
            </svg>`,
            error: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" style="stroke: #ef4444;"/>
                <line x1="15" y1="9" x2="9" y2="15" style="stroke: #ef4444;"/>
                <line x1="9" y1="9" x2="15" y2="15" style="stroke: #ef4444;"/>
            </svg>`,
            warning: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" style="stroke: #f59e0b;"/>
                <line x1="12" y1="9" x2="12" y2="13" style="stroke: #f59e0b;"/>
                <line x1="12" y1="17" x2="12.01" y2="17" style="stroke: #f59e0b;"/>
            </svg>`
        };
        
        return icons[type] || icons.success;
    }
}

// Dark mode toggle (if you want to add it later)
function toggleDarkMode() {
    const isDark = document.documentElement.hasAttribute('data-theme');
    if (isDark) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('darkMode', 'false');
    } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('darkMode', 'true');
    }
}

// Apply saved theme on load
function applySavedTheme() {
    const savedTheme = localStorage.getItem('darkMode');
    if (savedTheme === 'true') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    applySavedTheme();
    new AuthHandler();
    
    // Add some nice entrance animations
    const card = document.querySelector('.auth-card');
    const shapes = document.querySelectorAll('.floating-shape');
    
    // Stagger shape animations
    shapes.forEach((shape, index) => {
        shape.style.animationDelay = `${-5 * index}s`;
    });
    
    // Check if user is already logged in
    const user = localStorage.getItem('user');
    if (user && (window.location.pathname.includes('login') || window.location.pathname.includes('signup'))) {
        // Redirect to chat if already logged in
        window.location.href = 'chat.html';
    }
});