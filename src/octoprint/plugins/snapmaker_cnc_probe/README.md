# OctoPrint-SnapmakerCncProbe

This OctoPrint plugin provides CNC probing functionality for Snapmaker machines with a rotary axis. It addresses the issue of the rotary axis forgetting its starting position by:

1. Taking multi-angle photos of the part using the B-axis rotation
2. Analyzing the photos using a vision-capable LLM to determine the required alignment angle
3. Applying the calculated rotation to align the physical part with the digital model
4. Tracking the B-axis position between sessions

## Features

- Multi-angle image capture at 0°, -120°, and 60° B-axis rotations
- Reference image upload for Fusion 360 screenshots
- LLM-based image analysis for determining rotational alignment
- B-axis rotation correction with position memory
- Digital dial gauge integration for Z-probing (optional)

## Setup

Install the plugin directly through the OctoPrint Plugin Manager or manually using:

```
pip install -e path/to/OctoPrint-SnapmakerCncProbe
```

## Configuration

1. Set your LLM API key in the plugin settings
2. Configure the rotation wait time based on your machine's performance
3. Set up digital gauge connection details if you plan to use Z-probing

## Usage

1. Position your part on the rotary axis
2. Capture multi-angle images in the CNC Probe tab
3. Upload a Fusion 360 reference screenshot
4. Click "Analyze Images" to determine the alignment angle
5. Apply the rotation correction to align the part

The plugin will remember the B-axis position between sessions, solving the problem of the rotary axis forgetting its position.