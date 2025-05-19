Snapmaker CNC Probe Plugin Development Plan
Current Implementation Status

Created OctoPrint plugin structure (snapmaker_cnc_probe)
Implemented multi-angle image capture (0°, -120°, 60°) using B-axis rotation
Integrated with OctoPrint webcam for image capture
Added reference image upload capability for Fusion 360 screenshots
Implemented skeleton for digital dial gauge serial communication

Core Components

__init__.py: Main plugin file with class SnapmakerProbePlugin
templates/snapmaker_cnc_probe_tab.jinja2: UI interface
static/js/snapmaker_cnc_probe.js: Frontend logic
static/css/snapmaker_cnc_probe.css: Basic styling
setup.py: Plugin installation configuration

Key Functionality

B-axis rotation control via G-code commands
Webcam snapshot capture via OctoPrint's configured camera
Image storage and serving via BlueprintPlugin routes
LLM-based part alignment analysis comparing captured images to Fusion 360 reference

LLM Integration Plan

Send multi-angle part photos + Fusion 360 reference to vision-capable LLM
LLM estimates rotation angle required to match reference orientation
Apply calculated rotation to align physical part with digital model
Format: JSON response with angle and confidence values

Remaining Implementation Tasks

Complete LLM API integration for image analysis
Finalize digital dial gauge connection and probing logic
Implement Renishaw-compatible probe results format
Add probe point execution with gauge-based feedback
Create results export for Fusion 360 import
Add error handling and validation throughout workflow
Implement configuration UI for API keys and advanced settings

Execution Flow

Capture images at multiple B-axis rotations
Upload Fusion 360 reference screenshot
Process with LLM to determine alignment angle
Apply rotation correction via B-axis
Execute probing sequence with digital gauge
Generate compatible results file for Fusion 360
Import results into Fusion 360 for toolpath adjustment

This plugin bridges visual alignment and touch probing to produce accurate part machining with proper alignment to CAD model.