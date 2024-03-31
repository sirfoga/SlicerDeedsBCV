import vtk
import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from typing import Optional

from src.logic import deedsBCVLogic as Logic
from src.ui import deedsBCVParameterNode


class deedsBCVWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """

        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation

        self.logic = None
        self.ui = None

        self._parameterNode = None
        self._parameterNodeGuiTag = None
        self.registrationInProgress = False

    def setup(self) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        self._setupLogic()
        self._setupUI()
        self._setupConnections()

        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()

    def _setupLogic(self) -> None:
        self.logic = Logic()
        self.logic.logCallback = self.addLog

        self.registrationInProgress = False

    def _setupUI(self) -> None:
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/deedsBCV.ui'))
        uiWidget.setMRMLScene(slicer.mrmlScene)

        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

    def _setupConnections(self) -> None:
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)

        # inputs
        #self.ui.fixedVolumeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.updateParameterNodeFromGUI)
        #self.ui.movingVolumeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.updateParameterNodeFromGUI)

        # outputs
        #self.ui.outputVolumeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.updateParameterNodeFromGUI)

    def setParameterNode(self, inputParameterNode: Optional[deedsBCVParameterNode] = None) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if inputParameterNode:
            self.logic.setDefaultParameters(inputParameterNode)

        # Unobserve previously selected parameter node and add an observer to the newly selected.
        # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
        # those are reflected immediately in the GUI.
        if self._parameterNode is not None and self.hasObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._onParameterNodeChange):
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._onParameterNodeChange)

        self._parameterNode = inputParameterNode
        if self._parameterNode is not None:
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._onParameterNodeChange)  # monitor change in GUI

    def _onParameterNodeChange(self, caller=None, event=None):
        if self._parameterNode is None:
            return

        # todo needed ?
        # self.ui.fixedVolumeSelector.setCurrentNode(self._parameterNode.fixedVolume)

        self.updateApplyButtonState()

    def onApplyButton(self) -> None:
        """ Run processing when user clicks "Apply" button. """

        if self.registrationInProgress:
            self.logic.cancelRequested = True
            self.registrationInProgress = False
        else:
            with slicer.util.tryWithErrorDisplay('Failed to compute results.', waitCursor=True):
                self.ui.statusLabel.plainText = ''

                try:
                    self.registrationInProgress = True
                    self.updateApplyButtonState()

                    self.runLogicOrExcept()
                    self.onLogicSuccess()
                finally:
                    self.registrationInProgress = False

        self.updateApplyButtonState()

    def getUIProperty(self, key, prop):
        widget = getattr(self.ui, key)
        return getattr(widget, prop)

    def getPipelineStepSelected(self):
        return self.getUIProperty(self.logic.PIPELINE_STEPS, 'checked')

    def getAdvancedParams(self):
        keys = [
            self.logic.ADVANCED_REG_PARAM_REF,
            self.logic.ADVANCED_NLEVELS_PARAM_REF,
            self.logic.ADVANCED_SPACING_PARAM_REF,
            self.logic.ADVANCED_MAX_SEARCH_RADIUS_PARAM_REF,
            self.logic.ADVANCED_QUANT_PARAM_REF
        ]
        return tuple(map(
            lambda key: self.getUIProperty(key, 'value'),
            keys
        ))

    def runLogicOrExcept(self):
        self.logic.processParameterNode(
            self._parameterNode,
            alsoAffineStep=self.getPipelineStepSelected(),
            advancedParams=self.getAdvancedParams(),
            deleteTemporaryFiles=False,
            #deprecated, of course log! logToStdout=True
        )

    def onLogicSuccess(self):
        """ Apply computed transform to moving volume if output transform is computed to immediately see registration results """

        movingVolumeNode = self.ui.movingVolumeSelector.currentNode()
        # todo get ouput (moved) from logic and display
        # get affine (rigid) (+ deformable) trans from logic and save in the Save folder

    def setStateApplyButton(self, enabled, text=None):
        if not (text is None):
            self.ui.applyButton.text = text

        self.ui.applyButton.enabled = enabled

    def disableApplyButton(self, text=None):
        self.setStateApplyButton(False, text)

    def enableApplyButton(self, text=None):
        self.setStateApplyButton(True, text)

    def updateApplyButtonState(self):
        if self.registrationInProgress or self.logic.isRunning:
            if self.logic.cancelRequested:
                self.disableApplyButton('Cancelling...')
            else:
                self.enableApplyButton('Cancel')
        else:
            fixedVolumeNode = self._parameterNode.fixedVolume
            movingVolumeNode = self._parameterNode.movingVolume
            outputVolumeNode = self._parameterNode.outputVolume

            if not fixedVolumeNode or not movingVolumeNode:
                self.disableApplyButton('Select fixed and moving volumes')
            elif fixedVolumeNode == movingVolumeNode:
                print(fixedVolumeNode, movingVolumeNode)
                self.disableApplyButton('Fixed and moving volume must not be the same')
            elif not outputVolumeNode:
                self.disableApplyButton('Select an output volume')
            else:
                self.enableApplyButton('Apply')

    def cleanup(self) -> None:
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()

    def enter(self) -> None:
        """
        Called each time the user opens this module.
        """

        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""

        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._onParameterNodeChange)

    def onSceneStartClose(self, caller, event) -> None:
        """
        Called just before the scene is closed.
        """

        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """
        Called just after the scene is closed.
        """
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """
        Ensure parameter node exists and observed.
        """

        self.setParameterNode(self.logic.getParameterNode())

    def addLog(self, text):
        self.ui.statusLabel.appendPlainText(text)
        slicer.app.processEvents()  # force update
