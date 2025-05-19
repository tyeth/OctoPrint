__license__ = "MIT License"
__author__ = "Tyeth Gundry"
__copyright__ = "Copyright (C) 2025 Tyeth Gundry - All rights reserved"
__version__ = "0.1.0"

import os
import serial
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
                          octoprint.plugin.AssetPlugin):
    
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