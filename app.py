from flask import Flask, request, render_template, send_file, redirect, url_for
import os
import zipfile
import logging
from compare_faces import compare_faces
from queue import Queue
import threading

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a dictionary to store passcodes and associated zip file names
passcode_zip_mapping = {}

# Create a queue for processing tasks
task_queue = Queue()

def process_file(file_path, passcode):
    logger.info(f"Processing file: {file_path}, Passcode: {passcode}")
    matches_list = compare_faces(file_path, app.config['DATABASE_FOLDER'])
    
    if passcode:
        # Generate a unique zip file name based on the passcode
        zip_filename = f"{passcode}.zip"
        passcode_zip_mapping[passcode] = zip_filename

        # Create zip file
        zip_file_path = os.path.join(app.config['ZIP_FOLDER'], zip_filename)
        added_files = set()  # Set to store added file paths
        with zipfile.ZipFile(zip_file_path, 'w') as zipf:
            for matched_image_path in matches_list:
                # Check if the file path has been added before
                if matched_image_path not in added_files:
                    # Add the file to the zip file
                    zipf.write(matched_image_path, os.path.basename(matched_image_path))
                    added_files.add(matched_image_path)

        # Update status
        logger.info(f"Processing complete for {file_path}. Creating download file...")

def worker():
    while True:
        task = task_queue.get()
        process_file(*task)
        task_queue.task_done()

# Start worker thread
worker_thread = threading.Thread(target=worker)
worker_thread.daemon = True
worker_thread.start()

@app.route('/', methods=['GET', 'POST'])
def index():
    status = ''  # Initialize status
    error = None
    if request.method == 'POST':
        if 'file' not in request.files:
            error = "No file part"
        else:
            files = request.files.getlist('file')
            passcode = request.form.get('passcode')  # Get passcode from form

            for file in files:
                if file.filename == '':
                    continue

                filename = file.filename
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                # Create the 'uploads' directory if it doesn't exist
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])
                file.save(file_path)
                # Update status
                status = 'Processing...'
                logger.info(f"Added {filename} to processing queue")
                
                # Enqueue the file processing task
                task_queue.put((file_path, passcode))
                
    return render_template('index.html', status=status, error=error)

@app.route('/static/<passcode>')
def download_zip(passcode):
    # Check if the provided passcode exists in the mapping
    if passcode in passcode_zip_mapping:
        # Provide access to the matched images zip file associated with the passcode
        zip_file_path = os.path.join(app.config['ZIP_FOLDER'], passcode_zip_mapping[passcode])
        return send_file(zip_file_path, as_attachment=True)
    else:
        return "Invalid passcode"

if __name__ == '__main__':
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['DATABASE_FOLDER'] = 'database'
    app.config['ZIP_FOLDER'] = 'static'
    app.run(debug=True)
