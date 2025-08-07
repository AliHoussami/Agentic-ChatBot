from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import requests
import json
import logging
from datetime import datetime
import re
from time import perf_counter
import base64
import os
from PIL import Image
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "deepseek-r1:1.5b"
MAX_TOKENS = 2000
TEMPERATURE = 0.7

class SimpleChatBot:
    def __init__(self):
        self.conversation_history = []
        self.max_history = 6  # Keep last 6 messages

    def clean_response(self, response):
        """Minimal response cleaning - preserve formatting"""
        if not response or not response.strip():
            return "I couldn't generate a response."
        
        # Remove thinking tags if present
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)
        response = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL | re.IGNORECASE)
        
        # Clean up excessive newlines (max 2 consecutive)
        response = re.sub(r'\n\s*\n\s*\n+', '\n\n', response)
        
        # Remove trailing spaces at end of lines
        response = re.sub(r'[ \t]+\n', '\n', response)
        
        # Remove header markdown
        response = re.sub(r'^#{1,3}\s*', '', response, flags=re.MULTILINE)
        
        return response.strip()

    def add_to_history(self, role, content):
        """Add message to conversation history"""
        self.conversation_history.append({"role": role, "content": content})
        # Keep only recent history
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

    def get_response(self, user_message):
        """Get response from Ollama"""
        try:
            self.add_to_history("user", user_message)
            
            system_prompt = """You are a helpful programming assistant.

CRITICAL: When providing code examples:
- ALWAYS use proper line breaks and indentation
- NEVER put multiple statements on one line  
- Use markdown code blocks with language tags
- Format with 4-space indentation
- Each statement on its own line

FOR MATH:
- Wrap inline math in \\( ... \\)
- Wrap block math in $$ ... $$
- Use proper LaTeX syntax

Example format:
```csharp
// Declare and initialize an integer array
int[] numbers = { 10, 20, 30, 40, 50 };

// Loop through the array using a for loop
for (int i = 0; i < numbers.Length; i++)
{
    Console.WriteLine("Number: " + numbers[i]);
}
```

Be clear and concise in explanations."""

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self.conversation_history)
            
            payload = {
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Lower for more consistent formatting
                    "num_predict": MAX_TOKENS,
                    "top_p": 0.9,
                    "top_k": 40
                }
            }
            
            logger.info(f"Sending request: {user_message[:50]}...")
            
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get("message", {}).get("content", "")
                
                if not ai_response.strip():
                    ai_response = "I couldn't generate a response. Please try again."
                
                ai_response = self.clean_response(ai_response)
                self.add_to_history("assistant", ai_response)
                logger.info(f"Response received: {ai_response[:50]}...")
                
                return ai_response
            else:
                logger.error(f"Ollama error: {response.status_code}")
                return "I'm having trouble connecting to the AI model. Please try again."
                
        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            return "Request timed out. Please try again."
        except requests.exceptions.ConnectionError:
            logger.error("Connection error")
            return "Cannot connect to Ollama. Make sure it's running."
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return "An error occurred. Please try again."

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []

# Initialize chatbot
chatbot = SimpleChatBot()

@app.route('/')
def index():
    """Serve the chatbot interface"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Simple AI Chatbot</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container { 
                max-width: 800px; margin: 0 auto; 
                background: white; border-radius: 15px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 20px; text-align: center;
            }
            .header h1 { margin: 0; font-size: 24px; }
            .messages { 
                height: 500px; overflow-y: auto; 
                padding: 20px; background: #f8f9fa;
            }
            .message { 
                margin: 15px 0; padding: 12px 16px; 
                border-radius: 18px; max-width: 80%;
                word-wrap: break-word;
            }
            .user { 
                background: #007bff; color: white; 
                margin-left: auto; border-bottom-right-radius: 4px;
            }
            .bot { 
                background: white; color: #333; 
                border: 1px solid #e1e5e9;
                border-bottom-left-radius: 4px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }
            .bot pre {
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                overflow-x: auto;
                margin: 15px 0;
                font-family: 'Courier New', monospace;
                font-size: 14px;
                line-height: 1.4;
            }
            .bot code {
                background: #f1f3f4;
                padding: 3px 6px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                color: #d73a49;
                border: 1px solid #e1e4e8;
            }
            .bot h2 {
                color: #2c3e50;
                font-size: 18px;
                margin: 20px 0 10px 0;
                border-bottom: 2px solid #3498db;
                padding-bottom: 5px;
            }
            .bot h3 {
                color: #34495e;
                font-size: 16px;
                margin: 15px 0 8px 0;
            }
            .bot ul, .bot ol {
                margin: 10px 0;
                padding-left: 20px;
            }
            .bot li {
                margin: 5px 0;
                line-height: 1.5;
            }
            .bot strong {
                color: #2c3e50;
                font-weight: 600;
            }
            .bot p {
                margin: 10px 0;
                line-height: 1.6;
            }
            .input-container { 
                display: flex; padding: 20px; 
                background: white; border-top: 1px solid #e1e5e9;
            }
            input { 
                flex: 1; padding: 12px 16px; 
                border: 1px solid #ddd; border-radius: 25px;
                font-size: 14px; outline: none;
            }
            input:focus { border-color: #007bff; }
            button { 
                padding: 12px 20px; margin-left: 10px;
                background: #007bff; color: white; 
                border: none; border-radius: 25px; 
                cursor: pointer; font-size: 14px;
                transition: background 0.3s;
            }
            button:hover { background: #0056b3; }
            .clear-btn { background: #6c757d; }
            .clear-btn:hover { background: #545b62; }
            .loading { 
                color: #666; font-style: italic; 
                animation: pulse 1.5s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 AI Chatbot</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Powered by Deepseek via Ollama</p>
            </div>
            <div id="messages" class="messages"></div>
            <div class="input-container">
                <input type="text" id="messageInput" placeholder="Ask me anything about programming..." />
                <button onclick="sendMessage()">Send</button>
                <button class="clear-btn" onclick="clearChat()">Clear</button>
            </div>
        </div>
        
        <script>
            const messagesDiv = document.getElementById('messages');
            const messageInput = document.getElementById('messageInput');
            
            function formatMessage(content) {
                // First handle code blocks BEFORE converting newlines
                content = content.replace(/```(\w*)\s*([\s\S]*?)```/g, function(match, lang, code) {
                    return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
                });
                
                // Handle inline code
                content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
                
                // Handle bold text
                content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
                
                // Split by double newlines to create paragraphs
                let paragraphs = content.split('\n\n');
                
                paragraphs = paragraphs.map(paragraph => {
                    // Skip if it's a code block
                    if (paragraph.includes('<pre>')) {
                        return paragraph;
                    }
                    
                    // Handle headers
                    if (paragraph.startsWith('###')) {
                        return '<h3>' + paragraph.replace(/^###\s*/, '') + '</h3>';
                    }
                    if (paragraph.startsWith('##')) {
                        return '<h2>' + paragraph.replace(/^##\s*/, '') + '</h2>';
                    }
                    
                    // Handle numbered lists
                    if (/^\d+\./.test(paragraph)) {
                        let items = paragraph.split('\n').filter(line => line.trim());
                        let listItems = items.map(item => {
                            return '<li>' + item.replace(/^\d+\.\s*/, '') + '</li>';
                        }).join('');
                        return '<ol>' + listItems + '</ol>';
                    }
                    
                    // Handle bullet points
                    if (/^[-*]/.test(paragraph)) {
                        let items = paragraph.split('\n').filter(line => line.trim());
                        let listItems = items.map(item => {
                            return '<li>' + item.replace(/^[-*]\s*/, '') + '</li>';
                        }).join('');
                        return '<ul>' + listItems + '</ul>';
                    }
                    
                    // Regular paragraph - convert single newlines to <br>
                    return '<p>' + paragraph.replace(/\n/g, '<br>') + '</p>';
                });
                
                return paragraphs.join('');
            }
            
            function addMessage(content, isUser) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
                
                if (isUser) {
                    messageDiv.textContent = content;
                } else {
                    messageDiv.innerHTML = formatMessage(content);
                }
                
                messagesDiv.appendChild(messageDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function showLoading() {
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'message bot loading';
                loadingDiv.textContent = '🤔 AI is thinking...';
                loadingDiv.id = 'loading';
                messagesDiv.appendChild(loadingDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function hideLoading() {
                const loading = document.getElementById('loading');
                if (loading) loading.remove();
            }
            
            async function sendMessage() {
                const message = messageInput.value.trim();
                if (!message) return;
                
                addMessage(message, true);
                messageInput.value = '';
                showLoading();
                
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: message })
                    });
                    
                    const data = await response.json();
                    hideLoading();
                    
                    if (data.response) {
                        addMessage(data.response, false);
                    } else {
                        addMessage('Sorry, I encountered an error.', false);
                    }
                } catch (error) {
                    hideLoading();
                    addMessage('Connection error. Please try again.', false);
                }
            }
            
            async function clearChat() {
                try {
                    await fetch('/clear', { method: 'POST' });
                    messagesDiv.innerHTML = '';
                    addMessage('Chat history cleared! How can I help you?', false);
                } catch (error) {
                    addMessage('Error clearing chat.', false);
                }
            }
            
            messageInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendMessage();
            });
            
            // Welcome message
            addMessage('Hello! I\\'m your AI programming assistant. Ask me anything about coding!', false);
        </script>
    </body>
    </html>
    """
    return render_template_string(html_content)

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        start = perf_counter()
        ai_response = chatbot.get_response(user_message)
        end = perf_counter()
        response_time = round(end - start, 2)

        return jsonify({
            "response": ai_response,
            "response_time": response_time
        })
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/clear', methods=['POST'])
def clear_chat():
    """Clear conversation history"""
    try:
        chatbot.clear_history()
        return jsonify({"message": "Chat cleared"})
    except Exception as e:
        logger.error(f"Clear error: {str(e)}")
        return jsonify({"error": "Error clearing chat"}), 500

@app.route('/chat-image', methods=['POST'])
def chat_image():
    """Handle chat with image"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400
            
        image_file = request.files['image']
        message = request.form.get('message', 'Analyze this image')
        
        if image_file.filename == '':
            return jsonify({"error": "No image selected"}), 400
        
        # Read and process image
        image_data = image_file.read()

        # Validate image format
        try:
            Image.open(io.BytesIO(image_data)).verify()
        except Exception:
            return jsonify({"error": "Invalid image format"}), 400
        
        # Convert to base64 for Ollama
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Use vision model
        payload = {
            "model": "llava:7b",
            "messages": [
                {
                    "role": "user", 
                    "content": message,
                    "images": [image_base64]
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": MAX_TOKENS
            }
        }
        
        logger.info(f"Sending image analysis request...")
        
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result.get("message", {}).get("content", "")
            
            if not ai_response.strip():
                ai_response = "I couldn't analyze the image. Please try again."
            
            ai_response = chatbot.clean_response(ai_response)
            logger.info(f"Image analysis completed")
            
            return jsonify({"response": ai_response})
        else:
            logger.error(f"Ollama error: {response.status_code}")
            return jsonify({"error": "Error processing image"}), 500
            
    except Exception as e:
        logger.error(f"Image chat error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=5)
        ollama_status = "connected" if response.status_code == 200 else "disconnected"
    except:
        ollama_status = "disconnected"
    
    return jsonify({
        "status": "healthy",
        "ollama": ollama_status,
        "model": MODEL_NAME
    })

if __name__ == '__main__':
    print(f"🚀 Starting Flask server...")
    print(f"📡 Ollama URL: {OLLAMA_BASE_URL}")
    print(f"🤖 Model: {MODEL_NAME}")
    print(f"🌐 Visit: http://localhost:5000")
    print("⚠️  Make sure Ollama is running!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)