from flask import Flask, jsonify, request
from flask_cors import CORS
import base64
import os
import numpy as np
from PIL import Image
import io

# You'll need to import your model implementations here
# For example:
# from models.rnn_attention import RNNAttentionModel
# from models.vision_transformer import VisionTransformerModel

app = Flask(__name__)
CORS(app)

# Placeholder for actual model loading
# In production, you would load your trained models here
def load_models():
    # This is a placeholder - replace with actual model loading code
    models = {
        "rnn_attention": None,  # RNNAttentionModel()
        "vision_transformer": None  # VisionTransformerModel()
    }
    return models

# Initialize models
models = load_models()

@app.route('/caption', methods=['POST'])
def generate_caption():
    try:
        # Get request data
        data = request.json
        if not data:
            return jsonify({
                "message": "Missing request data",
                "error": "No JSON data received"
            }), 400
            
        if 'image' not in data:
            return jsonify({
                "message": "Missing required parameters",
                "error": "No image data provided"
            }), 400
            
        if 'model' not in data:
            return jsonify({
                "message": "Missing required parameters",
                "error": "No model type provided"
            }), 400
        
        # Get the model type
        model_type = data['model']
        if model_type not in ["rnn_attention", "vision_transformer"]:
            return jsonify({
                "message": "Invalid model type",
                "error": "Model type must be 'rnn_attention' or 'vision_transformer'"
            }), 400
        
        # Decode the base64 image
        try:
            # Log some debug info
            image_data = data['image']
            print(f"Received image data of length: {len(image_data)}")
            
            # Check if the image data has the data URL prefix and handle it
            if ',' in image_data:
                prefix, image_data = image_data.split(',', 1)
                print(f"Image prefix: {prefix}")
            
            # Decode base64
            image_bytes = base64.b64decode(image_data)
            print(f"Decoded image bytes length: {len(image_bytes)}")
            
            # Open as an image to validate it
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size
            print(f"Image opened successfully. Size: {width}x{height}, Format: {image.format}")
            
            # For demonstration, we'll return a placeholder caption
            # In production, you would use your actual models
            if model_type == "rnn_attention":
                caption = f"A {image.format} image of size {width}x{height}. [RNN with Attention]"
            else:
                caption = f"A beautiful {image.format} image with dimensions {width}x{height}. [Vision Transformer]"
            
            print(caption)
            return jsonify({
                "message": "Caption generated successfully",
                "data": {
                    "caption": caption
                }
            }), 200
            
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return jsonify({
                "message": "Error processing image",
                "error": str(e)
            }), 400
        
    except Exception as e:
        print(f"Server error: {str(e)}")
        return jsonify({
            "message": "An error occurred",
            "error": str(e)
        }), 500

@app.route('/test', methods=['GET'])
def test_route():
    return jsonify({
        "message": "API is working!",
        "status": "success"
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
