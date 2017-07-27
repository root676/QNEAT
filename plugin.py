import os

from processing.core.Processing import Processing

class ProcessingScriptCollectionPlugin:

    def initGui(self):
        Processing.addScripts(os.path.join(os.path.dirname(__file__), "scripts"))

    def unload(self):
        Processing.removeScripts(os.path.join(os.path.dirname(__file__), "scripts"))
