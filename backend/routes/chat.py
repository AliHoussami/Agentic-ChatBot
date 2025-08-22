from flask import Blueprint, request, jsonify, current_app
import requests
import base64
import io
from PIL import Image
from time import perf_counter
import logging
from config import OLLAMA_BASE_URL, MAX_TOKENS

chat_bp = Blueprint('chat', __name__)
logger = logging.getLogger(__name__)

@chat_bp.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        start = perf_counter()
        ai_response = current_app.chatbot.get_agentic_response(user_message)
        end = perf_counter()
        response_time = round(end - start, 2)

        return jsonify({
            "response": ai_response,
            "response_time": response_time
        })
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@chat_bp.route('/clear', methods=['POST'])
def clear_chat():
    """Clear conversation history"""
    try:
        current_app.chatbot.clear_history()
        return jsonify({"message": "Chat cleared"})
    except Exception as e:
        logger.error(f"Clear error: {str(e)}")
        return jsonify({"error": "Error clearing chat"}), 500

@chat_bp.route('/chat-image', methods=['POST'])
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
            
            ai_response = current_app.chatbot.clean_response(ai_response)
            logger.info(f"Image analysis completed")
            
            return jsonify({"response": ai_response})
        else:
            logger.error(f"Ollama error: {response.status_code}")
            return jsonify({"error": "Error processing image"}), 500
            
    except Exception as e:
        logger.error(f"Image chat error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500