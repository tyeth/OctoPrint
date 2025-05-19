$(function() {
    function SnapmakerCncProbeViewModel(parameters) {
        var self = this;
        
        self.loginState = parameters[0];
        self.settings = parameters[1];
        
        self.isBusy = ko.observable(false);
        self.hasImages = ko.observable(false);
        self.hasFusionImage = ko.observable(false);
        
        self.image0Deg = ko.observable();
        self.image120Deg = ko.observable();
        self.image60Deg = ko.observable();
        self.fusionImageUrl = ko.observable();
        
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
                var reader = new FileReader();
                reader.onload = function(e) {
                    self.fusionImageUrl(e.target.result);
                    self.hasFusionImage(true);
                };
                reader.readAsDataURL(file);
            }
        };
    }
    
    OCTOPRINT_VIEWMODELS.push({
        construct: SnapmakerCncProbeViewModel,
        dependencies: ["loginStateViewModel", "settingsViewModel"],
        elements: ["#snapmaker_cnc_probe"]
    });
});