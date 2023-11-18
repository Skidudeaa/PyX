#!/usr/bin/env python3

from flask import Flask, jsonify, request, send_from_directory
import os
import sys
import traceback  # Import for detailed error logging

# Add the directory containing your script to the Python path
sys.path.append('/Users/thomasamosson/PyX/pythonScripts')

# Now import your script as a module
import final1Flask  # Replace 'final1' with the actual name of your Python script, without the .py extension

app = Flask(__name__)

@app.route('/get-song-data', methods=['GET'])
def get_song_data():
    song_title = request.args.get('title')
    artist_name = request.args.get('artist')
    
    if not song_title or not artist_name:
        return jsonify({"error": "Missing required parameters"}), 400
    
    try:
        # Call your script's main function or an equivalent function that triggers the processing
        final1Flask.main(song_title, artist_name)  # Adjust this call as necessary
        
        # Construct paths to the saved files
        output_dir = os.path.join(os.getcwd(), 'finalOutput')
        json_file_path = os.path.join(output_dir, 'final_1F.json')
        image_file_path = os.path.join(output_dir, 'artworkF.jpg')  # Adjust filename as necessary
        video_file_path = os.path.join(output_dir, 'AnimatedArtF.mp4')  # Adjust filename as necessary
        
        # Check if files exist
        if not os.path.exists(json_file_path) or not os.path.exists(image_file_path) or not os.path.exists(video_file_path):
            return jsonify({"error": "File(s) not found"}), 404
        
        # Return file paths or URLs
        return jsonify({
            "json_file": json_file_path,
            "image_file": image_file_path,
            "video_file": video_file_path
        })
    
    except Exception as e:
        # Print the full traceback to help diagnose the issue
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Route to serve image and video files
@app.route('/files/<filename>', methods=['GET'])
def serve_file(filename):
    output_dir = os.path.join(os.getcwd(), 'finalOutput')
    return send_from_directory(output_dir, filename)

if __name__ == '__main__':
    app.run(debug=True)
