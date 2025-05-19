$(function() {
    function SnapmakerCncProbeViewModel(parameters) {
        var self = this;
        
        self.loginState = parameters[0];
        self.settings = parameters[1];
        
        self.isBusy = ko.observable(false);
        self.isAnalyzing = ko.observable(false);
        self.hasImages = ko.observable(false);
        self.hasFusionImage = ko.observable(false);
        self.hasAnalysisResult = ko.observable(false);
        
        self.image0Deg = ko.observable();
        self.image120Deg = ko.observable();
        self.image60Deg = ko.observable();
        self.fusionImageUrl = ko.observable();
        self.fusionImagePath = ko.observable();
        
        // Analysis results
        self.alignmentAngle = ko.observable();
        self.confidence = ko.observable();
        self.explanation = ko.observable();
        
        self.captureMultiAngleImages = function() {
            if (!self.loginState.isUser()) return;
            
            self.isBusy(true);
            $.ajax({
                url: API_BASEURL + "plugin/snapmaker_cnc_probe/capture",
                type: "POST",
                dataType: "json",
                success: function(response) {
                    if (response.status === "success" && response.images.length === 3) {
                        self.image0Deg({ url: response.images[0] });
                        self.image120Deg({ url: response.images[1] });
                        self.image60Deg({ url: response.images[2] });
                        self.hasImages(true);
                        // Reset any previous analysis
                        self.hasAnalysisResult(false);
                    } else {
                        new PNotify({
                            title: "Error",
                            text: "Failed to capture all images",
                            type: "error"
                        });
                    }
                    self.isBusy(false);
                },
                error: function() {
                    new PNotify({
                        title: "Error",
                        text: "Failed to communicate with the plugin",
                        type: "error"
                    });
                    self.isBusy(false);
                }
            });
        };
        
        self.uploadReferenceImage = function(data, event) {
            var file = event.target.files[0];
            if (file) {
                // First upload the file to the server
                var formData = new FormData();
                formData.append("file", file);
                
                self.isBusy(true);
                $.ajax({
                    url: API_BASEURL + "plugin/snapmaker_cnc_probe/upload_reference",
                    type: "POST",
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function(response) {
                        if (response.status === "success") {
                            self.fusionImageUrl(response.url);
                            self.fusionImagePath(response.path);
                            self.hasFusionImage(true);
                            // Reset any previous analysis
                            self.hasAnalysisResult(false);
                        } else {
                            new PNotify({
                                title: "Error",
                                text: response.message || "Failed to upload reference image",
                                type: "error"
                            });
                        }
                        self.isBusy(false);
                    },
                    error: function() {
                        new PNotify({
                            title: "Error",
                            text: "Failed to upload reference image",
                            type: "error"
                        });
                        self.isBusy(false);
                    }
                });
            }
        };
        
        self.analyzeImages = function() {
            if (!self.hasImages() || !self.hasFusionImage()) {
                new PNotify({
                    title: "Warning",
                    text: "Please capture part images and upload a Fusion 360 reference image first",
                    type: "warning"
                });
                return;
            }
            
            self.isAnalyzing(true);
            
            // Prepare the data for the LLM analysis
            var data = {
                part_images: [
                    self.image0Deg().url,
                    self.image120Deg().url,
                    self.image60Deg().url
                ],
                fusion_image: self.fusionImageUrl()
            };
            
            $.ajax({
                url: API_BASEURL + "plugin/snapmaker_cnc_probe/analyze",
                type: "POST",
                dataType: "json",
                contentType: "application/json",
                data: JSON.stringify(data),
                success: function(response) {
                    if (response.status === "success" && response.result) {
                        // Store the analysis results
                        var result = response.result;
                        self.alignmentAngle(result.alignment_angle);
                        self.confidence(result.confidence);
                        self.explanation(result.explanation);
                        self.hasAnalysisResult(true);
                        
                        new PNotify({
                            title: "Analysis Complete",
                            text: "Alignment angle: " + result.alignment_angle.toFixed(2) + "° (Confidence: " + (result.confidence * 100).toFixed(0) + "%)",
                            type: "info"
                        });
                    } else {
                        new PNotify({
                            title: "Analysis Failed",
                            text: response.message || "Failed to analyze images",
                            type: "error"
                        });
                    }
                    self.isAnalyzing(false);
                },
                error: function() {
                    new PNotify({
                        title: "Error",
                        text: "Failed to communicate with the plugin",
                        type: "error"
                    });
                    self.isAnalyzing(false);
                }
            });
        };
        
        self.applyRotation = function() {
            if (!self.hasAnalysisResult()) {
                new PNotify({
                    title: "Warning",
                    text: "Please analyze images first to determine the alignment angle",
                    type: "warning"
                });
                return;
            }
            
            // Confirm before applying rotation
            if (!confirm("Apply rotation correction of " + self.alignmentAngle().toFixed(2) + "°?")) {
                return;
            }
            
            self.isBusy(true);
            
            $.ajax({
                url: API_BASEURL + "plugin/snapmaker_cnc_probe/apply_rotation",
                type: "POST",
                dataType: "json",
                contentType: "application/json",
                data: JSON.stringify({ angle: self.alignmentAngle() }),
                success: function(response) {
                    if (response.status === "success") {
                        new PNotify({
                            title: "Success",
                            text: response.message || "Applied rotation correction",
                            type: "success"
                        });
                    } else {
                        new PNotify({
                            title: "Error",
                            text: response.message || "Failed to apply rotation",
                            type: "error"
                        });
                    }
                    self.isBusy(false);
                },
                error: function() {
                    new PNotify({
                        title: "Error",
                        text: "Failed to communicate with the plugin",
                        type: "error"
                    });
                    self.isBusy(false);
                }
            });
        };
        
        self.resetBAxis = function() {
            // Confirm before resetting
            if (!confirm("Reset B-axis to home position?")) {
                return;
            }
            
            self.isBusy(true);
            
            $.ajax({
                url: API_BASEURL + "plugin/snapmaker_cnc_probe/reset_b_axis",
                type: "POST",
                dataType: "json",
                contentType: "application/json",
                data: JSON.stringify({}),
                success: function(response) {
                    if (response.status === "success") {
                        new PNotify({
                            title: "Success",
                            text: response.message || "Reset B-axis to home position",
                            type: "success"
                        });
                    } else {
                        new PNotify({
                            title: "Error",
                            text: response.message || "Failed to reset B-axis",
                            type: "error"
                        });
                    }
                    self.isBusy(false);
                },
                error: function() {
                    new PNotify({
                        title: "Error",
                        text: "Failed to communicate with the plugin",
                        type: "error"
                    });
                    self.isBusy(false);
                }
            });
        };
    }
    
    OCTOPRINT_VIEWMODELS.push({
        construct: SnapmakerCncProbeViewModel,
        dependencies: ["loginStateViewModel", "settingsViewModel"],
        elements: ["#snapmaker_cnc_probe"]
    });
});