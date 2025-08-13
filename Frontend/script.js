class Chatbot {
    constructor() {
        this.messages = document.getElementById('chatMessages');
        this.input = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.clearButton = document.getElementById('clearChatBtn');
        this.exportButton = document.getElementById('exportBtn');
        this.themeToggle = document.getElementById('themeToggle');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.charCounter = document.getElementById('charCounter');
        
        this.chatHistory = [];
        this.isConnected = true;
        this.isDarkMode = localStorage.getItem('darkMode') === 'true';
        
        this.init();
    }
    
    init() {
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.clearButton.addEventListener('click', () => this.clearChat());
        this.exportButton.addEventListener('click', () => this.exportChat());
        this.themeToggle.addEventListener('click', () => this.toggleTheme());
        
        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        this.input.addEventListener('input', () => {
            this.updateCharCounter();
            this.autoResize();
            this.sendButton.disabled = this.input.value.trim() === '';
        });

        this.input.addEventListener('paste', () => {
            setTimeout(() => {
                this.autoResize();
                this.updateCharCounter();
            }, 0);
        });

        document.getElementById('imageBtn').addEventListener('click', () => {
            document.getElementById('imageInput').click();
        });

        document.getElementById('imageInput').addEventListener('change', (e) => {
            this.handleImageUpload(e);
        });
        
        // Initial state
        this.sendButton.disabled = true;
        this.addWelcomeMessage();
        this.updateCharCounter();
        this.checkConnection();
        this.applyTheme();
    }

    updateCharCounter() {
        const count = this.input.value.length;
        const max = 2000;
        this.charCounter.textContent = `${count}/${max}`;
        
        this.charCounter.className = 'char-counter';
        if (count > max * 0.9) {
            this.charCounter.classList.add('warning');
        }
        if (count >= max) {
            this.charCounter.classList.add('error');
        }
    }

    autoResize() {
        this.input.style.height = 'auto';
        this.input.style.height = Math.min(this.input.scrollHeight, 120) + 'px';
    }

    async checkConnection() {
        try {
            const response = await fetch('http://localhost:5000/health', {
                method: 'GET',
                timeout: 3000
            });
            this.updateConnectionStatus(response.ok);
        } catch (error) {
            this.updateConnectionStatus(false);
        }
    }

    updateConnectionStatus(connected) {
        this.isConnected = connected;
        if (connected) {
            this.statusIndicator.className = 'status-indicator';
        } else {
            this.statusIndicator.className = 'status-indicator error';
        }
    }

    addWelcomeMessage() {
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'welcome-message';
        welcomeDiv.innerHTML = `
            <span class="welcome-message-icon">🤖</span>
            Hello! I'm an enhanced AI Assistant. <br>
            How can I help you today?
        `;
        this.messages.appendChild(welcomeDiv);
    }

    clearChat() {
        if (this.chatHistory.length > 0 && !confirm('Are you sure you want to clear the chat history?')) {
            return;
        }
        this.messages.innerHTML = '';
        this.chatHistory = [];
        this.addWelcomeMessage();
        this.showToast('Chat cleared successfully');
    }

    exportChat() {
        if (this.chatHistory.length === 0) {
            this.showToast('No messages to export', 'error');
            return;
        }

        const chatData = {
            timestamp: new Date().toISOString(),
            messages: this.chatHistory
        };

        const blob = new Blob([JSON.stringify(chatData, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-export-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.showToast('Chat exported successfully');
    }
    
    sendMessage() {
        const messageText = this.input.value.trim();
        if (!messageText) return;
        
        // Remove welcome message if it exists
        const welcome = this.messages.querySelector('.welcome-message');
        if(welcome) welcome.remove();

        this.addMessage(messageText, 'user');
        this.input.value = '';
        this.input.style.height = 'auto';
        this.sendButton.disabled = true;
        this.updateCharCounter();
        
        this.showTypingIndicator();
        
        this.generateResponse(messageText).then(response => {
            this.hideTypingIndicator();
            this.addMessage(response, 'bot');
        }).catch(error => {
            this.hideTypingIndicator();
            this.addMessage("Sorry, I encountered an error. Please try again.", 'bot', true);
            console.error('Error:', error);
            this.updateConnectionStatus(false);
        });
    }
    
    addMessage(text, sender, isError = false) {
        const timestamp = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

        this.chatHistory.push({
            text: text,
            sender: sender,
            timestamp: new Date().toISOString(),
            isError: isError
        });

        const row = document.createElement('div');
        row.className = `message-row ${sender}-row animate__animated animate__fadeInUp`;

        const avatar = document.createElement('div');
        avatar.className = `avatar ${sender}-avatar`;
        avatar.innerHTML = sender === 'bot'
            ? `<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4C14.21,4 16,5.79 16,8C16,10.21 14.21,12 12,12C9.79,12 8,10.21 8,8C8,5.79 9.79,4 12,4M12,14C16.42,14 20,15.79 20,18V20H4V18C4,15.79 7.58,14 12,14Z" /></svg>`
            : `<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12,4A4,4 0 0,1 16,8A4,4 0 0,1 12,12A4,4 0 0,1 8,8A4,4 0 0,1 12,4M12,14C16.41,14 20,15.79 20,18V20H4V18C4,15.79 7.59,14 12,14Z" /></svg>`;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message${isError ? ' error-message' : ''}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = timestamp;

        if (sender === 'bot') {
            // Typewriter effect for bot
            let formatted = this.formatBotMessage(text);
            contentDiv.innerHTML = ""; // Start empty

            let i = 0;
            function typeWriter() {
                // Add next character
                contentDiv.innerHTML = formatted.slice(0, i);
                Prism.highlightAll();
                if (window.MathJax) MathJax.typesetPromise([contentDiv]);
                i++;
                if (i <= formatted.length) {
                    setTimeout(typeWriter, 12); // Adjust speed here (ms per char)
                }
            }
            typeWriter();

            // Message actions (copy button)
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'message-actions';
            const copyBtn = document.createElement('button');
            copyBtn.className = 'action-btn';
            copyBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
            copyBtn.title = 'Copy message';
            copyBtn.onclick = () => this.copyMessage(text);
            actionsDiv.appendChild(copyBtn);
            messageDiv.appendChild(actionsDiv);
        } else {
            contentDiv.textContent = text;
        }

        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);

        row.appendChild(avatar);
        row.appendChild(messageDiv);

        this.messages.appendChild(row);
        this.scrollToBottom();
    }

    copyMessage(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Message copied to clipboard');
        }).catch(() => {
            this.showToast('Failed to copy message', 'error');
        });
    }

    showToast(message, type = 'success') {
        const existingToast = document.querySelector('.toast');
        if (existingToast) {
            existingToast.remove();
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type} animate__animated animate__fadeInDown`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 100);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator animate__animated animate__bounceIn';
        typingDiv.id = 'typingIndicator';
        typingDiv.innerHTML = `
            <div class="avatar bot-avatar">
                <svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4C14.21,4 16,5.79 16,8C16,10.21 14.21,12 12,12C9.79,12 8,10.21 8,8C8,5.79 9.79,4 12,4M12,14C16.42,14 20,15.79 20,18V20H4V18C4,15.79 7.58,14 12,14Z" /></svg>
            </div>
            <div class="typing-dots-container">
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        this.messages.appendChild(typingDiv);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }
    
    async generateResponse(message) {
        try {
            const response = await fetch('http://localhost:5000/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.updateConnectionStatus(true);
            return data.response || "Sorry, I couldn't generate a response.";
            
        } catch (error) {
            console.error('Error calling backend:', error);
            this.updateConnectionStatus(false);
            throw error;
        }
    }
    
    formatBotMessage(content) {
        // STEP 1: Protect code blocks first by replacing them with placeholders
        const codeBlocks = [];
        let codeBlockIndex = 0;
        
        // Extract and preserve code blocks
        content = content.replace(/```(\w*)\s*([\s\S]*?)```/g, function(match, lang, code) {
            const placeholder = `__CODE_BLOCK_${codeBlockIndex}__`;
            codeBlocks.push(`<pre><code class="language-${lang}">${code.trim()}</code></pre>`);
            codeBlockIndex++;
            return placeholder;
        });
        
        // STEP 2: Process inline formatting (but NOT inside code blocks)
        // Inline code: `code`
        content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Bold: **text**
        content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        // Italic: *text*
        content = content.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        
        // STEP 3: Handle paragraphs (but preserve code block placeholders)
        content = content.split('\n\n').map(paragraph => {
            // If this paragraph is just a code block placeholder, return it as-is
            if (paragraph.trim().match(/^__CODE_BLOCK_\d+__$/)) {
                return paragraph;
            }
            // Otherwise, wrap in <p> and convert single newlines to <br>
            return `<p>${paragraph.replace(/\n/g, '<br>')}</p>`;
        }).join('');
        
        // STEP 4: Restore code blocks
        codeBlocks.forEach((block, index) => {
            content = content.replace(`__CODE_BLOCK_${index}__`, block);
        });

        return content;
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;',
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
    
    scrollToBottom() {
        this.messages.scrollTop = this.messages.scrollHeight;
    }

    toggleTheme() {
        this.isDarkMode = !this.isDarkMode;
        localStorage.setItem('darkMode', this.isDarkMode.toString());
        this.applyTheme();
        this.showToast(`Switched to ${this.isDarkMode ? 'dark' : 'light'} mode`);
    }

    applyTheme() {
        const sunIcon = this.themeToggle.querySelector('.sun-icon');
        const moonIcon = this.themeToggle.querySelector('.moon-icon');
        
        if (this.isDarkMode) {
            document.documentElement.setAttribute('data-theme', 'dark');
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        } else {
            document.documentElement.removeAttribute('data-theme');
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
        }
    }

    handleImageUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        if (!file.type.startsWith('image/')) {
            this.showToast('Please select an image file', 'error');
            return;
        }
        
        if (file.size > 10 * 1024 * 1024) { // 10MB limit
            this.showToast('Image too large. Please select an image under 10MB', 'error');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = (e) => {
            this.sendImageMessage(file, e.target.result);
        };
        reader.readAsDataURL(file);
        
        // Clear the input
        event.target.value = '';
    }

    sendImageMessage(file, imageDataUrl) {
        // Remove welcome message
        const welcome = this.messages.querySelector('.welcome-message');
        if(welcome) welcome.remove();
        
        // Add user message with image
        this.addImageMessage(imageDataUrl, 'user');
        
        this.showTypingIndicator();
        
        // Create FormData for upload
        const formData = new FormData();
        formData.append('image', file);
        formData.append('message', 'Analyze this image');
        
        fetch('http://localhost:5000/chat-image', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            this.hideTypingIndicator();
            this.addMessage(data.response || "I couldn't analyze the image.", 'bot');
        })
        .catch(error => {
            this.hideTypingIndicator();
            this.addMessage("Sorry, I couldn't process the image.", 'bot', true);
            console.error('Error:', error);
        });
    }

    addImageMessage(imageSrc, sender) {
        const timestamp = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        
        const row = document.createElement('div');
        row.className = `message-row ${sender}-row animate__animated animate__fadeInUp`;
        
        const avatar = document.createElement('div');
        avatar.className = `avatar ${sender}-avatar`;
        avatar.innerHTML = sender === 'bot' 
            ? `<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4C14.21,4 16,5.79 16,8C16,10.21 14.21,12 12,12C9.79,12 8,10.21 8,8C8,5.79 9.79,4 12,4M12,14C16.42,14 20,15.79 20,18V20H4V18C4,15.79 7.58,14 12,14Z" /></svg>`
            : `<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12,4A4,4 0 0,1 16,8A4,4 0 0,1 12,12A4,4 0 0,1 8,8A4,4 0 0,1 12,4M12,14C16.41,14 20,15.79 20,18V20H4V18C4,15.79 7.59,14 12,14Z" /></svg>`;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const imageContainer = document.createElement('div');
        imageContainer.className = 'image-message';
        
        const img = document.createElement('img');
        img.src = imageSrc;
        img.className = 'image-preview';
        img.alt = 'Uploaded image';
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = timestamp;
        
        imageContainer.appendChild(img);
        messageDiv.appendChild(imageContainer);
        messageDiv.appendChild(timeDiv);
        
        row.appendChild(avatar);
        row.appendChild(messageDiv);
        
        this.messages.appendChild(row);
        this.scrollToBottom();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new Chatbot();
});