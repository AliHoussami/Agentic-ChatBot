from flask import Flask
from flask_cors import CORS
import logging
from config import *
from utils.database import test_db_connection
from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.agent import agent_bp
from models.conversation import SimpleChatBot

# Import configuration
from config import *

# Import utilities
from utils.database import test_db_connection

# Import route blueprints
from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.agent import agent_bp

# Import models
from models.conversation import SimpleChatBot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)
CORS(app, supports_credentials=True, origins=['*'])

# Test database connection on startup
test_db_connection()

# Initialize chatbot instance
chatbot = SimpleChatBot()

# Make chatbot available to routes
app.chatbot = chatbot

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(agent_bp)

if __name__ == '__main__':
    print(f"🚀 Starting Flask server...")
    print(f"📡 Ollama URL: {OLLAMA_BASE_URL}")
    print(f"🤖 Model: {MODEL_NAME}")
    print(f"🌐 Visit: http://localhost:5000")
    print("⚠️  Make sure Ollama is running!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)