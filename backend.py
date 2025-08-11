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
from dataclasses import dataclass

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

@dataclass
class Task:
    id: str
    description: str
    status: str
    result: str = ""

class AgentTools:
    @staticmethod
    def search_files(directory, pattern):
        """Search for files matching pattern"""
        import glob
        try:
            matches = glob.glob(os.path.join(directory, pattern))
            if matches:
                file_list = "\n".join([f"• {os.path.basename(match)}" for match in matches])
                return f"Found {len(matches)} files:\n{file_list}"
            else:
                return "No files found matching the pattern"
        except Exception as e:
            return f"Error searching files: {str(e)}"
    
    @staticmethod
    def read_file(filepath):
        """Read file contents safely"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return "Error reading file"
    
    @staticmethod
    def calculate(expression):
        """Safe mathematical calculations"""
        try:
            # Only allow safe operations
            allowed = "0123456789+-*/.() "
            if all(c in allowed for c in expression):
                return str(eval(expression))
            return "Invalid expression"
        except:
            return "Calculation error"
        
    @staticmethod  # <-- Add this line and everything below
    def search_files_in_path(directory, pattern="*.*"):
        """Search for files in a specific directory path"""
        import glob
        import os
        try:
            if not os.path.exists(directory):
                return f"Directory '{directory}' does not exist"
            
            search_path = os.path.join(directory, pattern)
            matches = glob.glob(search_path)
            
            if matches:
                limited_matches = matches[:20]
                file_list = "\n".join([f"• {match}" for match in limited_matches])
                return f"Found {len(matches)} files:\n{file_list}"
            else:
                return f"No files found in '{directory}'"
                
        except Exception as e:
            return f"Error: {str(e)}"
        
    @staticmethod
    def discover_system_info():
        """Dynamically discover what the system can do"""
        import platform
        import psutil
        import subprocess

        capabilities = {
            "system": platform.system(),
            "python_version": platform.python_version(),
            "available_drives": [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")],
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "cpu_cores": psutil.cpu_count(),
            "gpu_info": subprocess.check_output("wmic path win32_VideoController get name", shell=True, text=True).strip().split('\n')[1:] if platform.system() == "Windows" else "GPU detection not available on this OS",
            "installed_modules": []
        }

        modules_to_check = ['requests', 'pandas', 'numpy', 'opencv-cv2', 'pillow', 'matplotlib', 'selenium', 'beautifulsoup4']
        for module in modules_to_check:
            try:
                __import__(module)
                capabilities["installed_modules"].append(module)
            except ImportError:
                pass

        return capabilities
    
    @staticmethod
    def execute_python_code(code):
        """Execute Python code safely and return output"""
        import sys
        from io import StringIO
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        captured_output = StringIO()
        captured_error = StringIO()
        try:
            
            sys.stdout = captured_output
            sys.stderr = captured_error

            exec(code)

            output = captured_output.getvalue()
            error = captured_error.getvalue()


            if error:
                return f"Error: {error}"
            return output if output else "Code executed successfully (no output)"
        except Exception as e:
            return f"Execution Error: {str(e)}"
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

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
        """Enhanced response with agentic capabilities"""
        try:
            logger.info(f"Received message: '{user_message}'")
            if self.is_agentic_request(user_message):
                logger.info("Routing to agentic response")
                return self.get_agentic_response(user_message)
            else:
                logger.info("Routing to regular LLM response")
                return self.get_llm_response(user_message)
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return "An error occurred. Please try again."
            
            

    def get_llm_response(self, user_message):
        """Original LLM response method"""
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
        
    def is_agentic_request(self, message):
        """Check if request needs agentic behavior"""
        agentic_keywords = ['search for', 'find files', 'read file', 'calculate', 'help me with', 'can you', 'what can you do', 'system info', 'capabilities', 'execute', 'run this']
        is_agentic = any(keyword in message.lower() for keyword in agentic_keywords)
        print(f"DEBUG: Message='{message[:50]}...' | Is_Agentic={is_agentic}")
        logger.info(f"Checking if agentic: '{message}' -> {is_agentic}")
        return is_agentic
    
    
    
    def plan_tasks(self, user_request):
        """Break down request into tasks"""
        # Simple task planning
        if 'execute' in user_request.lower() or 'run this' in user_request.lower() or '```python' in user_request:
            return [Task("1", f"Execute code: {user_request}", "pending")]
        elif 'what can you do' in user_request.lower() or 'capabilities' in user_request.lower():
            return [Task("1", f"Discover system capabilities", "pending")]
        elif 'search' in user_request.lower():
            return [Task("1", f"Search based on: {user_request}", "pending")]
        elif 'file' in user_request.lower():
            return [Task("1", f"File operation: {user_request}", "pending")]
        elif 'calculate' in user_request.lower():
            return [Task("1", f"Calculate: {user_request}", "pending")]
        else:
            return [Task("1", f"General task: {user_request}", "pending")]
        
    
    def execute_task(self, task):
        """Execute a single task"""
        task.status = "in_progress"
        
        if 'search' in task.description.lower():
            import re
            path_match = re.search(r'[C-Z]:[\\\/][^\s]*', task.description)
            if path_match:
                directory = path_match.group()
                task.result = AgentTools.search_files_in_path(directory, "*.py")
            else:
                task.result = AgentTools.search_files(".", "*.*")
            if not task.result or "Error" in task.result:
                task.result = AgentTools.search_files(".", "*.*")
        elif 'file' in task.description.lower():
            task.result = AgentTools.read_file("example.txt")
        elif 'calculate' in task.description.lower():
            # Extract math expression
            import re
            math_match = re.search(r'[\d+\-*/\.\(\) ]+', task.description)
            if math_match:
                task.result = AgentTools.calculate(math_match.group())
            else:
                task.result = "No calculation found"
        elif 'capabilities' in task.description.lower() or 'discover system' in task.description.lower():
            system_info = AgentTools.discover_system_info()
            task.result = f"""System Information:
            - OS: {system_info['system']}
            - Python: {system_info['python_version']}
            - Memory: {system_info['memory_gb']} GB
            - CPU Cores: {system_info['cpu_cores']}
            - Available Drives: {', '.join(system_info['available_drives'])}
            - GPU: {system_info['gpu_info'] if isinstance(system_info['gpu_info'], str) else ', '.join([gpu.strip() for gpu in system_info['gpu_info'] if gpu.strip()])}
            - Installed Modules: {', '.join(system_info['installed_modules']) if system_info['installed_modules'] else 'None detected'}"""  
        elif 'execute' in task.description.lower() or 'run code' in task.description.lower():
            print(f"DEBUG: Executing task: {task.description}")
            import re 
            if '```python' in task.description:
                code_start = task.description.find('```python') + len('```python')
                code_part = task.description[code_start:].strip()

                if '```' in code_part:
                    code_part = code_part[:code_part.find('```')]

                code_part = code_part.strip()
                print(f"DEBUG: Found code: {repr(code_part)}")
                task.result = AgentTools.execute_python_code(code_part)
                print(f"DEBUG: Execution result: {repr(task.result)}")
            else:
                print(f"DEBUG: No ```python found")
                task.result = "No Python code block found. Use ```python ... ``` format"            
        else:
            task.result = "Task completed"
        
        task.status = "completed"
        return task
    
    def get_agentic_response(self, user_message):
        """Handle agentic requests"""
        try:
            tasks = self.plan_tasks(user_message)
            results = []
            for task in tasks:
                executed_task = self.execute_task(task)
                results.append(executed_task.result)

            if 'execute' in user_message.lower():
                return results[0]
            
            context = "\n".join(results)
            enhanced_prompt = f"The user asked: {user_message}\n\nResults: {context}\n\nProvide a helpful response."
            return self.get_llm_response(enhanced_prompt)
          
        except Exception as e:
            logger.error(f"Agentic error: {str(e)}")
            return "I encountered an error processing your request."
    
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
        ai_response = chatbot.get_agentic_response(user_message)
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

@app.route('/agent/status', methods=['GET'])
def agent_status():
    """Get agent capabilities"""
    return jsonify({
        "tools": ["search_files", "read_file", "calculate"],
        "agentic_mode": True,
        "available_actions": ["file_operations", "calculations", "searches"]
    })


if __name__ == '__main__':
    print(f"🚀 Starting Flask server...")
    print(f"📡 Ollama URL: {OLLAMA_BASE_URL}")
    print(f"🤖 Model: {MODEL_NAME}")
    print(f"🌐 Visit: http://localhost:5000")
    print("⚠️  Make sure Ollama is running!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)