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
        self.parent.contributors = ["Stefano Fogarollo, Matthias Harders (IGS, UIBK)"]

        self.parent.helpText = """Register two medical volumes with DEEDS. See original implementation <a href="https://github.com/mattiaspaul/deedsBCV">here</a>."""

        self.parent.acknowledgementText = """This file was originally developed by Stefano Fogarollo and Matthias Harders (IGS, UIBK), and was partially funded by FWF, project DOC 110."""
