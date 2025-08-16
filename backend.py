from flask import Flask, request, jsonify
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
import collections
from typing import Dict, List, Set, Tuple
import bcrypt
import mysql.connector
from mysql.connector import Error
import jwt
from functools import wraps
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)
CORS(app, supports_credentials=True, origins=['*'])

# Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "deepseek-r1:1.5b"
MAX_TOKENS = 2000
TEMPERATURE = 0.7

DB_CONFIG = {
    'host': 'localhost',
    'database': 'model_code',
    'user': 'root',
    'password': 'Alinx123@'
}
JWT_SECRET = 'sk-auth-2024-xyz789-secure-jwt-token-abcd1234-random-key'
# Add this after your DB_CONFIG
def test_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        print("✅ Database connected successfully!")
        connection.close()
        return True
    except Error as e:
        print(f"❌ Database connection failed: {e}")
        return False

# Add this before app.run()
test_db_connection()

def get_db_connection():
    """Get database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        logger.error(f"Database connection error: {e}")
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

@app.route('/auth/signup', methods=['POST'])
def signup():
    """User registration"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM Users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            return jsonify({'error': 'Username or email already exists'}), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert user
        cursor.execute(
            "INSERT INTO Users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        connection.commit()
        
        user_id = cursor.lastrowid
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(days=30)
        }, JWT_SECRET, algorithm='HS256')
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'message': 'User created successfully',
            'token': token,
            'user': {
                'id': user_id,
                'username': username,
                'email': email
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Get user
        cursor.execute(
            "SELECT id, username, email, password_hash FROM Users WHERE username = %s",
            (username,)
        )
        user = cursor.fetchone()
        
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Update last login
        cursor.execute(
            "UPDATE Users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
            (user[0],)
        )
        connection.commit()
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user[0],
            'exp': datetime.utcnow() + timedelta(days=30)
        }, JWT_SECRET, algorithm='HS256')
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': user[0],
                'username': user[1],
                'email': user[2]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@dataclass
class Task:
    id: str
    description: str
    status: str
    result: str = ""


@dataclass
class ConversationContext:
    """Track conversation context for better understanding"""
    languages_mentioned: Set[str]
    topics_discussed: Set[str] 
    user_skill_level: str  # beginner, intermediate, advanced
    question_types: List[str]
    error_patterns: List[str]
    
    def __post_init__(self):
        if not isinstance(self.languages_mentioned, set):
            self.languages_mentioned = set()
        if not isinstance(self.topics_discussed, set):
            self.topics_discussed = set()

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

    @staticmethod
    def execute_csharp_code(code):
            """Execute C# code using dotnet"""
            import subprocess
            import tempfile
            import os
            import shutil
            try:
                    temp_dir = os.path.join(tempfile.gettempdir(), f"csharp_temp_{os.getpid()}")
                    os.makedirs(temp_dir, exist_ok=True)

                    try:
                        subprocess.run(['dotnet', 'new', 'console', '--force'], 
                                      cwd=temp_dir, capture_output=True, text=True, check=True)
                        
                        program_file = os.path.join(temp_dir, 'Program.cs')
                                            
                        if 'class Program' not in code and 'static void Main' not in code:
                            wrapped_code = f"""using System;


using System;
class Program 
{{
    static void Main() 
    {{
        {code}
    }}
}}"""
                        else:
                          wrapped_code = code

                        with open(program_file, 'w', encoding='utf-8') as f:
                         f.write(wrapped_code)

                        result = subprocess.run(['dotnet', 'run'], 
                                  cwd=temp_dir, capture_output=True, text=True, timeout=10)
                                

                        if result.returncode == 0:
                          return result.stdout.strip() if result.stdout.strip() else "C# executed successfully"
                        else:
                          return f"C# Error: {result.stderr.strip()}"
                        
                    finally:
                        try:
                            shutil.rmtree(temp_dir)
                        except:
                            pass

            except subprocess.TimeoutExpired:
                return "C# execution timeout"
            except Exception as e:
                return f"C# Error: {result.stderr.strip()}"
            

class SimpleChatBot:
    def __init__(self):
        self.conversation_history = []
        self.max_history = 6  # Keep last 6 messages

    def classify_question_type(self, message: str) -> str:
        """Classify the type of programming question"""
        message_lower = message.lower()
        if any(word in message_lower for word in ["error", "exception", "bug", "not working", "broken", "crash"]):
            return "debugging"
        elif any(phrase in message_lower for phrase in ["how to", "how do i", "how can i", "tutorial", "guide"]):
            return "tutorial"
        elif any(word in message_lower for word in ["best", "better", "optimize", "improve", "recommend"]):
            return "advice"
        elif any(phrase in message_lower for phrase in ["explain", "what does", "analyze", "review"]):
            return "explanation"
        elif any(word in message_lower for word in ["vs", "versus", "compare", "difference"]):
            return "comparison"
        elif any(word in message_lower for word in ["install", "setup", "configure", "environment"]):
            return "setup"
        else:
            return "general"
        
    def extract_programming_languages(self, message: str) -> Set[str]:
        """Extract mentioned programming languages from message"""
        languages = {
            'python', 'javascript', 'java', 'c#', 'csharp', 'c++', 'cpp', 'c', 
            'php', 'ruby', 'go', 'rust', 'swift', 'kotlin', 'scala', 'r',
            'html', 'css', 'sql', 'typescript', 'dart', 'perl', 'bash', 'shell'
        }
        message_lower = message.lower()
        found_languages = set()

        for lang in languages:
            if lang in message_lower:
                # Normalize language names
                if lang in ['c#', 'csharp']:
                    found_languages.add('csharp')
                elif lang in ['c++', 'cpp']:
                    found_languages.add('cpp')
                elif lang == 'javascript':
                    found_languages.add('javascript')
                else:
                    found_languages.add(lang)
                    
        return found_languages
    
    def detect_skill_level(self, message: str, history: List[Dict]) -> str:
        """Detect user's programming skill level"""
        message_lower = message.lower()
        
        # Beginner indicators
        beginner_keywords = [
            'beginner', 'new to', 'learning', 'just started', 'first time',
            'basics', 'simple', 'easy way', 'tutorial', 'guide'
        ]
        
        # Advanced indicators  
        advanced_keywords = [
            'optimization', 'performance', 'architecture', 'design pattern',
            'algorithm complexity', 'scalability', 'refactor', 'enterprise'
        ]
        
        if any(keyword in message_lower for keyword in beginner_keywords):
            return 'beginner'
        elif any(keyword in message_lower for keyword in advanced_keywords):
            return 'advanced'
        
        # Check conversation history for skill indicators
        recent_messages = [msg.get('content', '') for msg in history[-4:]]
        all_text = ' '.join(recent_messages).lower()
        
        if any(keyword in all_text for keyword in beginner_keywords):
            return 'beginner'
        elif any(keyword in all_text for keyword in advanced_keywords):
            return 'advanced'
            
        return 'intermediate'
    
    def build_context_from_history(self) -> ConversationContext:
        """Extract context from recent conversation history"""
        languages_mentioned = set()
        topics_discussed = set()
        question_types = []
        error_patterns = []
        
        # Analyze last 6 messages
        for msg in self.conversation_history[-6:]:
            content = msg.get('content', '')
            
            # Extract languages
            languages_mentioned.update(self.extract_programming_languages(content))
            
            # Extract question type
            q_type = self.classify_question_type(content)
            if q_type != 'general':
                question_types.append(q_type)
            
            # Extract topics (frameworks, technologies)
            content_lower = content.lower()
            topics = [
                'react', 'angular', 'vue', 'nodejs', 'express', 'django', 'flask',
                'spring', 'hibernate', 'mongodb', 'mysql', 'postgresql', 'redis',
                'docker', 'kubernetes', 'aws', 'azure', 'git', 'machine learning',
                'ai', 'web development', 'mobile development', 'game development'
            ]
            
            for topic in topics:
                if topic in content_lower:
                    topics_discussed.add(topic)
            
            # Extract error patterns
            if any(word in content_lower for word in ['error', 'exception', 'traceback']):
                error_patterns.append(content[:100])  # First 100 chars
        
        skill_level = self.detect_skill_level(
            self.conversation_history[-1].get('content', '') if self.conversation_history else '',
            self.conversation_history
        )
        
        return ConversationContext(
            languages_mentioned=languages_mentioned,
            topics_discussed=topics_discussed,
            user_skill_level=skill_level,
            question_types=question_types[-3:],  # Keep last 3 question types
            error_patterns=error_patterns[-2:]   # Keep last 2 error patterns
        )
    
    def get_dynamic_system_prompt(self, user_message: str, context: ConversationContext) -> str:
        """Generate dynamic system prompt based on context"""
        base_prompt = """You are a helpful programming assistant focused on clear communication and practical solutions.

QUESTION UNDERSTANDING:
- Read the entire question carefully before responding
- If a question is vague or ambiguous, ask for clarification
- Identify the programming language, framework, or technology mentioned
- Determine the user's skill level from context (beginner/intermediate/advanced)
- Look for specific requirements, constraints, or desired outcomes
- Pay attention to error messages, code snippets, or examples provided

RESPONSE STRATEGY:
- Start with a direct answer to the main question
- If multiple interpretations exist, address the most likely one first
- Break down complex problems into smaller, manageable parts
- Explain the "why" behind solutions, not just the "how"
- Anticipate follow-up questions and provide relevant context

CODE FORMATTING RULES:
- ALWAYS use proper line breaks and indentation
- NEVER put multiple statements on one line  
- Use markdown code blocks with language tags
- Format with 4-space indentation for most languages
- Each statement on its own line
- Include helpful comments explaining key concepts

MATH FORMATTING:
- Wrap inline math in \\( ... \\)
- Wrap block math in $$ ... $$
- Use proper LaTeX syntax

COMMUNICATION STYLE:
- Be concise but thorough
- Use simple language when possible
- Provide examples that match the user's context
- If you need more information, ask specific questions
- Acknowledge when you're making assumptions

Remember: Better to ask for clarification than to guess incorrectly."""

        # Add context-specific guidance
        dynamic_additions = []
        
        # Language-specific guidance
        if context.languages_mentioned:
            langs = ', '.join(context.languages_mentioned)
            dynamic_additions.append(f"\nCONTEXT: User is working with {langs}. Focus on best practices for these languages.")
        
        # Skill level adjustments
        if context.user_skill_level == 'beginner':
            dynamic_additions.append("""
BEGINNER MODE:
- Provide extra explanations and context
- Define technical terms when first used
- Include step-by-step instructions
- Suggest learning resources when appropriate
- Be encouraging and patient""")
        
        elif context.user_skill_level == 'advanced':
            dynamic_additions.append("""
ADVANCED MODE:
- Focus on efficiency and best practices
- Discuss trade-offs and alternatives
- Include performance considerations
- Reference design patterns when relevant
- Assume familiarity with basic concepts""")
        
        # Question type specific guidance
        if 'debugging' in context.question_types:
            dynamic_additions.append("""
DEBUGGING FOCUS:
- Ask for complete error messages and stack traces
- Suggest systematic debugging approaches
- Recommend debugging tools and techniques""")
        
        if 'tutorial' in context.question_types:
            dynamic_additions.append("""
TUTORIAL MODE:
- Provide step-by-step instructions
- Include multiple examples
- Explain concepts progressively""")
        
        # Topic-specific guidance
        if context.topics_discussed:
            topics = ', '.join(list(context.topics_discussed)[:3])  # Limit to 3 topics
            dynamic_additions.append(f"\nRELEVANT TOPICS: Consider {topics} in your responses.")
        
        return base_prompt + ''.join(dynamic_additions)

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
        """Enhanced LLM response with dynamic prompting and context analysis"""
        try:
            self.add_to_history("user", user_message)
            
            # Build conversation context
            context = self.build_context_from_history()
            
            # Get dynamic system prompt
            system_prompt = self.get_dynamic_system_prompt(user_message, context)
            
            # Log context for debugging
            logger.info(f"Context - Languages: {context.languages_mentioned}, "
                       f"Skill: {context.user_skill_level}, "
                       f"Question type: {self.classify_question_type(user_message)}")
            
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
            elif '```csharp' in task.description or '```c#' in task.description:
                if '```csharp' in task.description:
                    code_start = task.description.find('```csharp') + len('```csharp')
                else:
                    code_start = task.description.find('```c#') + len('```c#')

                code_part = task.description[code_start:].strip()
                if '```' in code_part:
                    code_part = code_part[:code_part.find('```')]
                code_part = code_part.strip()
                print(f"DEBUG: Found C# code: {repr(code_part)}")
                task.result = AgentTools.execute_csharp_code(code_part)
            elif 'print(' in task.description or 'for ' in task.description:
                if ':' in task.description:
                    code_part = task.description.split(':', 1)[1].strip()
                else:
                    code_part = task.description
                print(f"DEBUG: Found plain Python code: {repr(code_part)}")
                task.result = AgentTools.execute_python_code(code_part)          
            else:
                print(f"DEBUG: No supported code found")
                task.result = "No supported code found. Use ```python or ```csharp format"    
                           
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

@app.route('/context', methods=['GET'])
def get_conversation_context():
    """Get current conversation context for debugging"""
    try:
        context = chatbot.build_context_from_history()
        return jsonify({
            "languages_mentioned": list(context.languages_mentioned),
            "topics_discussed": list(context.topics_discussed),
            "user_skill_level": context.user_skill_level,
            "recent_question_types": context.question_types,
            "conversation_length": len(chatbot.conversation_history)
        })
    except Exception as e:
        logger.error(f"Context error: {str(e)}")
        return jsonify({"error": "Error getting context"}), 500

if __name__ == '__main__':
    print(f"🚀 Starting Flask server...")
    print(f"📡 Ollama URL: {OLLAMA_BASE_URL}")
    print(f"🤖 Model: {MODEL_NAME}")
    print(f"🌐 Visit: http://localhost:5000")
    print("⚠️  Make sure Ollama is running!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)