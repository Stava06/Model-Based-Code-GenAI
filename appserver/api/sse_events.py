import time
import threading
from flask import jsonify

def send_to_frontend(type: str, content: str) -> None:
    """
        Send a message to the frontend

        params:
            type: The type of the message
            content: The content of the message
    """
    def send_to_frontend_thread(type: str, content: str) -> None:
        message = {
            "timestamp": time.time(),
            "from": "agent",
            "type": type,
            "content": content,
        }

        return jsonify(message), 200
    
    threading.Thread(target=send_to_frontend_thread, args=(type, content)).start()