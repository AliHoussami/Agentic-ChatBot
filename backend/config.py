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