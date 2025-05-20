import octoprint.plugin

class HelloWorldPlugin(octoprint.plugin.StartupPlugin,
                       octoprint.plugin.TemplatePlugin,
                       octoprint.plugin.SettingsPlugin,
                       octoprint.plugin.BlueprintPlugin,
                       octoprint.plugin.AssetPlugin):
    def on_after_startup(self):
        self._logger.info("Helloo World! (more %s)" % self._settings.get(["url"]))

    def get_settings_defaults(self):
        return dict(
            url="https://en.wikipedia.org/wiki/Hello_world"
        )
    
    # def get_template_vars(self):
    #     return dict(url=self._settings.get(["url"]))

    def get_template_configs(self):
        return [
            dict(type="navbar", custom_bindings=False),
            dict(type="settings", custom_bindings=False)
        ]
    
    def get_assets(self):
        return dict(
            js=["js/helloworld.js"],
            css=["css/helloworld.css"],
            less=["less/helloworld.less"]
        )

    @octoprint.plugin.BlueprintPlugin.route("/hello_world", methods=["GET"])
    def hello_world(self):
        """
        A simple hello world endpoint that returns a string.
        Access at http://localhost:5000/plugin/helloworld/hello_world
        or http://localhost:5000/plugin/octoprint_helloworld/hello_world
        depending on the plugin name / installation folder name.
        """
        # This is a GET request and thus not subject to CSRF protection
        return "Hello world!"
    
    # @octoprint.plugin.BlueprintPlugin.route("/hello_world/<name>", methods=["POST"])
    # @octoprint.plugin.BlueprintPlugin.exclude_csrf()
    # def hello_world_name(self, name):
    #     """
    #     A simple hello world endpoint that returns a personalized greeting.
    #     Access at http://localhost:5000/plugin/helloworld/hello_world/<name>
    #     """
    #     # This is a POST request and thus subject to CSRF protection
    #     return "Hello %s!" % name


__plugin_description__ = "A quick \"Hello World\" example plugin for OctoPrint"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = HelloWorldPlugin()
