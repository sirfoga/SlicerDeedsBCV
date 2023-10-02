from slicer.ScriptedLoadableModule import *

from src.widget import deedsBCVWidget  # else 'Warning, there is no UI for the module "deedsBCV"' ..


class deedsBCV(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "DeedsBCV"
        self.parent.categories = ["Registration"]
        self.parent.dependencies = []
        self.parent.contributors = ["Stefano Fogarollo (IGS, Innsbruck University)"]

        self.parent.helpText = """Register two medical volumes with DEEDS. See original implementation <a href="https://github.com/mattiaspaul/deedsBCV">here</a>."""

        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """Grazie mamma"""

        # Additional initialization step after application startup is complete
        #slicer.app.connect("startupCompleted()", registerSampleData)
