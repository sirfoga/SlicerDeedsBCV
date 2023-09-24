import logging
import os
import platform
import subprocess
import shutil
from typing import Annotated, Optional

import vtk

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode

from logic import Logic as deedsBCVLogic
from widget import Widget as deedsBCVWidget
from tests import Test as deedsBCVTest


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
        slicer.app.connect("startupCompleted()", registerSampleData)
