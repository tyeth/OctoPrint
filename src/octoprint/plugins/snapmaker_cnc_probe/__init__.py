__license__ = "MIT License"
__author__ = "Tyeth Gundry"
__copyright__ = "Copyright (C) 2025 Tyeth Gundry - All rights reserved"
__version__ = "0.1.0"

import os
import serial
import base64
import json
from datetime import datetime

import requests
import time
import threading
from tempfile import mkstemp

from flask import abort, jsonify, request, url_for, send_from_directory
from flask_babel import gettext
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename

import octoprint.plugin
from octoprint.access import ADMIN_GROUP
from octoprint.access.permissions import Permissions
from octoprint.server import NO_CONTENT
from octoprint.server.util.flask import no_firstrun_access, redirect_to_tornado
from octoprint.settings import settings
from octoprint.util import is_hidden_path, yaml


class SnapmakerProbePlugin(octoprint.plugin.StartupPlugin,
                          octoprint.plugin.TemplatePlugin,
                          octoprint.plugin.SettingsPlugin,
                          octoprint.plugin.AssetPlugin,
                          octoprint.plugin.BlueprintPlugin):
    
    def is_blueprint_csrf_protected(self):
        return True  # Enable CSRF protection by default


    def capture_current_image(self, name):
        """Capture an image using OctoPrint's configured webcam"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{name}_{timestamp}.jpg"
        filepath = os.path.join(self.get_image_folder(), filename)
        
        # Get webcam URL from OctoPrint settings
        webcam_settings = self._settings.global_get(["webcam"])
        snapshot_url = webcam_settings.get("snapshot", "")
        
        if not snapshot_url:
            self._logger.error("No webcam snapshot URL configured in OctoPrint")
            return None
        
        try:
            self._logger.info(f"Taking snapshot from {snapshot_url}")
            
            # Some cameras need a warmup call
            requests.get(snapshot_url, timeout=5)
            time.sleep(0.5)  # Short delay to allow camera to stabilize
            
            # Take the actual image
            response = requests.get(snapshot_url, timeout=5)
            
            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                self._logger.info(f"Snapshot saved to {filepath}")
                return filepath
            else:
                self._logger.error(f"Failed to get snapshot, status code: {response.status_code}")
                return None
        except Exception as e:
            self._logger.exception(f"Error taking snapshot: {str(e)}")
            return None
    
    def capture_multi_angle_images(self):
        """Capture images at multiple B-axis rotations"""
        images = []
        
        # Step 1: Capture image at current position (assumed to be 0°)
        filepath = self.capture_current_image("angle_0")
        if filepath:
            images.append(filepath)
            self._logger.info("Captured image at 0°")
        
        # Step 2: Rotate B-axis 120° CCW and capture
        self._printer.commands("G0 B-120")
        time.sleep(3)  # Allow more time for rotation to complete
        filepath = self.capture_current_image("angle_120ccw")
        if filepath:
            images.append(filepath)
            self._logger.info("Captured image at 120° CCW")
        
        # Step 3: Rotate B-axis 180° CW and capture
        self._printer.commands("G0 B60")
        time.sleep(3)
        filepath = self.capture_current_image("angle_60cw")
        if filepath:
            images.append(filepath)
            self._logger.info("Captured image at 60° CW")
        
        # Step 4: Return to 0°
        self._printer.commands("G0 B0")
        time.sleep(2)
        self._logger.info("Returned to 0°")
        
        return images
    

    def initialize_gauge_connection(self):
        """Initialize connection to digital dial gauge"""
        port = self._settings.get(["gauge_port"])
        baud = self._settings.get_int(["gauge_baud"])
        
        try:
            self.gauge_serial = serial.Serial(port, baud, timeout=1)
            self._logger.info(f"Connected to digital gauge at {port}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to connect to digital gauge: {str(e)}")
            return False

    def read_gauge_value(self):
        """Read current value from digital dial gauge"""
        if not hasattr(self, 'gauge_serial') or self.gauge_serial is None:
            self._logger.error("Gauge not connected")
            return None
            
        try:
            # Send command to request reading (depends on your gauge protocol)
            self.gauge_serial.write(b"READ\r\n")
            
            # Read response
            response = self.gauge_serial.readline().decode('utf-8').strip()
            
            # Parse gauge value (adjust based on your gauge output format)
            value = float(response)
            self._logger.info(f"Gauge reading: {value}")
            return value
        except Exception as e:
            self._logger.error(f"Failed to read gauge: {str(e)}")
            return None
        

    def perform_z_probing(self, x, y, z_approach):
        """
        Perform Z-axis probing at a specified XY position
        
        Args:
            x, y: Target XY position
            z_approach: Starting Z height above expected contact
        
        Returns:
            Z height at contact or None if failed
        """
        # Move to position with clearance
        self._printer.commands(f"G0 X{x} Y{y} Z{z_approach}")
        self._printer.commands("G4 P500")  # Pause for stability
        
        # Initialize gauge reading
        initial_gauge = self.read_gauge_value()
        if initial_gauge is None:
            return None
        
        # Set the threshold for contact detection
        contact_threshold = 0.01  # mm of dial gauge movement
        
        # Approach in small increments
        current_z = z_approach
        z_increment = -0.1  # 0.1mm steps down
        min_z = z_approach - 20  # Safety limit
        
        while current_z > min_z:
            # Move down incrementally
            current_z += z_increment
            self._printer.commands(f"G0 Z{current_z} F50")  # Slow feed rate
            self._printer.commands("G4 P200")  # Pause for stability
            
            # Read gauge
            gauge_reading = self.read_gauge_value()
            if gauge_reading is None:
                return None
            
            # Check if contact detected
            if abs(gauge_reading - initial_gauge) > contact_threshold:
                self._logger.info(f"Contact detected at Z={current_z}")
                return current_z
        
        self._logger.warning("Probing failed: reached minimum Z without contact")
        return None
    
    
    def on_after_startup(self):
        self._logger.info("Snapmaker CNC Probe Plugin loaded")
        self.image_folder = os.path.join(self.get_plugin_data_folder(), "images")
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)
    
    def get_settings_defaults(self):
        return {
            "rotation_wait_time": 3,  # seconds to wait after rotation
            "gauge_port": "/dev/ttyUSB0",
            "gauge_baud": 9600,
            "llm_api_key": "",
            "llm_api_url": "https://api.anthropic.com/v1/messages",
            "llm_model": "claude-3-haiku-20240307",
            "b_axis_home_position": 0,  # Store the home position of B axis
        }
    
    def get_template_configs(self):
        return [
            dict(type="tab", name="CNC Probe"),
            dict(type="settings", custom_bindings=False)
        ]
    
    def get_assets(self):
        return dict(
            js=["js/snapmaker_cnc_probe.js"],
            css=["css/snapmaker_cnc_probe.css"]
        )
    
    def get_image_folder(self):
        """Get or create the folder for storing images"""
        if not hasattr(self, "image_folder"):
            self.image_folder = os.path.join(self.get_plugin_data_folder(), "images")
            if not os.path.exists(self.image_folder):
                os.makedirs(self.image_folder)
        return self.image_folder

    def store_b_axis_position(self, position):
        """Store the current B-axis position as the home/reference position"""
        self._settings.set(["b_axis_home_position"], position)
        self._settings.save()
        self._logger.info(f"Stored B-axis home position: {position}")
    
    def get_b_axis_position(self):
        """Get the stored B-axis home position"""
        return self._settings.get_float(["b_axis_home_position"])
    
    def encode_image_to_base64(self, image_path):
        """Convert image file to base64 encoding for API requests"""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            self._logger.error(f"Error encoding image {image_path}: {str(e)}")
            return None
    
    def analyze_images_with_llm(self, part_images, fusion_image):
        """
        Use LLM to analyze images and determine rotation alignment
        
        Args:
            part_images: List of paths to multi-angle part images
            fusion_image: Path to Fusion 360 reference image
            
        Returns:
            Dict with alignment angle and confidence
        """
        api_key = self._settings.get(["llm_api_key"])
        api_url = self._settings.get(["llm_api_url"])
        model = self._settings.get(["llm_model"])
        
        if not api_key:
            self._logger.error("No LLM API key configured in settings")
            return {"error": "No API key configured"}
        
        # Encode all images to base64
        encoded_fusion = self.encode_image_to_base64(fusion_image)
        encoded_part_images = [self.encode_image_to_base64(img) for img in part_images]
        
        # Check if any encoding failed
        if None in encoded_part_images or encoded_fusion is None:
            self._logger.error("Failed to encode one or more images")
            return {"error": "Failed to encode images"}
        
        # Create the prompt for the LLM
        system_prompt = """You are a computer vision expert assisting with a CNC machining task. You will analyze multiple images of a part at different rotations and compare them with a reference CAD screenshot from Fusion 360.

Your task is to determine the rotational angle adjustment needed to align the physical part with the CAD model orientation.

Provide your response in this JSON format ONLY:
{"alignment_angle": float, "confidence": float, "explanation": "brief explanation"}

Where:
- alignment_angle is the B-axis rotation in degrees needed to align with CAD (negative = counterclockwise, positive = clockwise)
- confidence is a value between 0.0-1.0 indicating your confidence level
- explanation is a brief rationale for your decision
"""
        
        # Build the request payload
        content = [
            {"type": "text", "text": "Analyze these images to determine the rotational alignment needed for the part. The first image is the Fusion 360 reference showing the desired orientation. The subsequent three images show the physical part at 0°, -120°, and 60° B-axis rotations."},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded_fusion}},
            {"type": "text", "text": "Fusion 360 reference image (target orientation)"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded_part_images[0]}},
            {"type": "text", "text": "Physical part at 0° B-axis rotation"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded_part_images[1]}},
            {"type": "text", "text": "Physical part at -120° B-axis rotation"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded_part_images[2]}},
            {"type": "text", "text": "Physical part at 60° B-axis rotation"},
        ]
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 1024
        }
        
        try:
            self._logger.info("Sending images to LLM for analysis")
            response = requests.post(api_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                assistant_message = result.get("content", [])
                
                # Extract the JSON response from the text
                if assistant_message:
                    for message in assistant_message:
                        if message.get("type") == "text":
                            text_content = message.get("text", "")
                            # Try to extract JSON from the response
                            try:
                                # Find JSON in the response
                                json_start = text_content.find("{")
                                json_end = text_content.rfind("}") + 1
                                if json_start >= 0 and json_end > json_start:
                                    json_str = text_content[json_start:json_end]
                                    result = json.loads(json_str)
                                    self._logger.info(f"LLM analysis result: {result}")
                                    return result
                            except json.JSONDecodeError:
                                self._logger.error("Failed to parse JSON from LLM response")
                
                self._logger.error("No valid JSON found in LLM response")
                return {"error": "Failed to parse response from LLM"}
            else:
                self._logger.error(f"LLM API request failed: {response.status_code} - {response.text}")
                return {"error": f"API request failed with status {response.status_code}"}
                
        except Exception as e:
            self._logger.exception(f"Exception during LLM analysis: {str(e)}")
            return {"error": str(e)}
            
    # API endpoints
    @octoprint.plugin.BlueprintPlugin.route("/capture", methods=["POST"])
    def api_capture_images(self):
        try:
            # Verify that OctoPrint has a webcam configured
            webcam_settings = self._settings.global_get(["webcam"])
            snapshot_url = webcam_settings.get("snapshot", "")
            
            if not snapshot_url:
                return jsonify({
                    "status": "error", 
                    "message": "No webcam configured in OctoPrint. Please configure a webcam in OctoPrint settings first."
                })
            
            # Now capture the images
            images = self.capture_multi_angle_images()
            
            if not images or len(images) < 3:
                return jsonify({
                    "status": "error", 
                    "message": f"Failed to capture all images. Only captured {len(images) if images else 0} of 3 images."
                })
            
            # Convert file paths to URLs for the frontend
            image_urls = [f"/plugin/snapmaker_cnc_probe/image/{os.path.basename(img)}" for img in images]
            return jsonify({"status": "success", "images": image_urls})
        except Exception as e:
            self._logger.exception(f"Error in capture: {str(e)}")
            return jsonify({"status": "error", "message": str(e)})

    @octoprint.plugin.BlueprintPlugin.route("/image/<filename>", methods=["GET"])
    def get_image(self, filename):
        # Serve image files from the plugin's image folder
        safe_filename = secure_filename(filename)
        path = os.path.join(self.get_image_folder(), safe_filename)
        if not os.path.exists(path):
            abort(404)
        return send_from_directory(self.get_image_folder(), safe_filename)
    
    @octoprint.plugin.BlueprintPlugin.route("/upload_reference", methods=["POST"])
    def api_upload_reference(self):
        if not "file" in request.files:
            return jsonify({"status": "error", "message": "No file provided"})
            
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "No file selected"})
            
        if file:
            filename = secure_filename(f"fusion_reference_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
            path = os.path.join(self.get_image_folder(), filename)
            file.save(path)
            
            url = f"/plugin/snapmaker_cnc_probe/image/{filename}"
            return jsonify({"status": "success", "url": url, "path": path})
        
        return jsonify({"status": "error", "message": "Failed to save file"})
    
    @octoprint.plugin.BlueprintPlugin.route("/analyze", methods=["POST"])
    def api_analyze_images(self):
        """Analyze images with LLM and determine alignment angle"""
        try:
            data = request.json
            
            # Check for required data
            if not data or "part_images" not in data or "fusion_image" not in data:
                return jsonify({
                    "status": "error", 
                    "message": "Missing required image data"
                })
                
            # Get image paths from URLs
            part_image_paths = []
            for url in data["part_images"]:
                # Extract filename from URL
                filename = os.path.basename(url)
                path = os.path.join(self.get_image_folder(), secure_filename(filename))
                if not os.path.exists(path):
                    return jsonify({
                        "status": "error", 
                        "message": f"Image file not found: {filename}"
                    })
                part_image_paths.append(path)
                
            # Get fusion image path
            fusion_filename = os.path.basename(data["fusion_image"])
            fusion_path = os.path.join(self.get_image_folder(), secure_filename(fusion_filename))
            if not os.path.exists(fusion_path):
                return jsonify({
                    "status": "error", 
                    "message": f"Fusion reference image not found: {fusion_filename}"
                })
                
            # Analyze images with LLM
            analysis_result = self.analyze_images_with_llm(part_image_paths, fusion_path)
            
            if "error" in analysis_result:
                return jsonify({
                    "status": "error",
                    "message": analysis_result["error"]
                })
                
            # Return the analysis results
            return jsonify({
                "status": "success",
                "result": analysis_result
            })
                
        except Exception as e:
            self._logger.exception(f"Error in analyze endpoint: {str(e)}")
            return jsonify({"status": "error", "message": str(e)})
    
    @octoprint.plugin.BlueprintPlugin.route("/apply_rotation", methods=["POST"])
    def api_apply_rotation(self):
        """Apply the calculated rotation to align the part"""
        try:
            data = request.json
            
            if not data or "angle" not in data:
                return jsonify({
                    "status": "error", 
                    "message": "Missing required angle data"
                })
                
            angle = float(data["angle"])
            current_position = self.get_b_axis_position()
            new_position = current_position + angle
            
            # Store new position before rotation
            self.store_b_axis_position(new_position)
            
            # Send the rotation command
            self._printer.commands(f"G0 B{angle} ; Applying alignment rotation")
            
            # Wait for rotation (use the configured wait time)
            wait_time = self._settings.get_int(["rotation_wait_time"])
            time.sleep(wait_time)
            
            return jsonify({
                "status": "success",
                "message": f"Applied rotation of {angle} degrees",
                "new_position": new_position
            })
                
        except Exception as e:
            self._logger.exception(f"Error applying rotation: {str(e)}")
            return jsonify({"status": "error", "message": str(e)})
    
    @octoprint.plugin.BlueprintPlugin.route("/reset_b_axis", methods=["POST"])
    def api_reset_b_axis(self):
        """Reset B-axis to stored home position"""
        try:
            home_position = self.get_b_axis_position()
            
            # Send the command to return to home position
            self._printer.commands(f"G0 B{home_position} ; Returning to home position")
            
            # Wait for rotation
            wait_time = self._settings.get_int(["rotation_wait_time"])
            time.sleep(wait_time)
            
            return jsonify({
                "status": "success",
                "message": f"Reset B-axis to home position: {home_position} degrees"
            })
                
        except Exception as e:
            self._logger.exception(f"Error resetting B-axis: {str(e)}")
            return jsonify({"status": "error", "message": str(e)})
    
    # Additional permissions
    def get_additional_permissions(self):
        return [
            {
                "key": "CAPTURE",
                "name": "Capture images",
                "description": "Allows to capture and analyze probe images",
                "default_groups": [ADMIN_GROUP],
                "roles": ["admin"]
            }
        ]
    
    def get_update_information(self):
        return {
            "snapmaker_cnc_probe": {
                "displayName": "Snapmaker CNC Probe",
                "displayVersion": self._plugin_version,
                "type": "github_release",
                "user": "tyeth",
                "repo": "OctoPrint-SnapmakerCncProbe",
                "current": self._plugin_version,
                "stable_branch": {
                    "name": "Stable",
                    "branch": "main",
                    "comittish": ["main"],
                },
                "prerelease_branches": [
                    {
                        "name": "Development",
                        "branch": "devel",
                        "comittish": ["devel", "main"],
                    }
                ],
                "pip": "https://github.com/tyeth/OctoPrint-SnapmakerCncProbe/archive/{target_version}.zip",
            }
        }

# Plugin registration
__plugin_name__ = "Snapmaker CNC Probe"
__plugin_pythoncompat__ = ">=3,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = SnapmakerProbePlugin()
    
    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.access.permissions": __plugin_implementation__.get_additional_permissions
    }