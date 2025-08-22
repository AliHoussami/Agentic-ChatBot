from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
import requests
import re
import logging
import os
import glob
import platform
import psutil
import subprocess
import sys
from io import StringIO
import tempfile
import shutil
from config import OLLAMA_BASE_URL, MODEL_NAME, MAX_TOKENS, TEMPERATURE
from utils.agent_tools import AgentTools
logger = logging.getLogger(__name__)

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