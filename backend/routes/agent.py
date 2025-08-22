from flask import Blueprint, jsonify, current_app
import requests
import logging
from config import OLLAMA_BASE_URL, MODEL_NAME

agent_bp = Blueprint('agent', __name__)
logger = logging.getLogger(__name__)

@agent_bp.route('/health', methods=['GET'])
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

@agent_bp.route('/agent/status', methods=['GET'])
def agent_status():
    """Get agent capabilities"""
    return jsonify({
        "tools": ["search_files", "read_file", "calculate"],
        "agentic_mode": True,
        "available_actions": ["file_operations", "calculations", "searches"]
    })

@agent_bp.route('/context', methods=['GET'])
def get_conversation_context():
    """Get current conversation context for debugging"""
    try:
        context = current_app.chatbot.build_context_from_history()
        return jsonify({
            "languages_mentioned": list(context.languages_mentioned),
            "topics_discussed": list(context.topics_discussed),
            "user_skill_level": context.user_skill_level,
            "recent_question_types": context.question_types,
            "conversation_length": len(current_app.chatbot.conversation_history)
        })
    except Exception as e:
        logger.error(f"Context error: {str(e)}")
        return jsonify({"error": "Error getting context"}), 500