import slicer
from slicer.ScriptedLoadableModule import *

from logic import Logic


class AbstractWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    def __init__(self, parent=None) -> None:
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation

        self.logic = None
        self.ui = None

        self._parameterNode = None
        self._parameterNodeGuiTag = None
        self._updatingGUIFromParameterNode = False

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
        """
        Called each time the user opens a different module.
        """
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

        self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

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
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.inputVolume:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.inputVolume = firstVolumeNode

    def addLog(self, text):
        self.ui.statusLabel.appendPlainText(text)
        slicer.app.processEvents()  # force update


class Widget(AbstractRegistrationWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """

        super().__init__(self, parent)

        self.registrationInProgress = False

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

        #todo more connections

        self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)

    def setParameterNode(self, inputParameterNode):
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        if self._parameterNode and self._parameterNode.inputVolume and self._parameterNode.thresholdedVolume:
            self.ui.applyButton.toolTip = "Compute output volume"
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = "Select input and output volume nodes"
            self.ui.applyButton.enabled = False

    def onApplyButton(self) -> None:
        """
        Run processing when user clicks "Apply" button.
        """

        if self.registrationInProgress:
            self.logic.cancelRequested = True
            self.registrationInProgress = False
        else:
            with slicer.util.tryWithErrorDisplay("Failed to compute results.", waitCursor=True):
                self.ui.statusLabel.plainText = ''

                try:
                    self.registrationInProgress = True
                    self.updateApplyButtonState()

                    self.runLogicOrExcept()
                    self.onLogicSuccess()
                finally:
                    self.registrationInProgress = False

        self.updateApplyButtonState()

    def runLogicOrExcept(self):
        self.logic.processParameterNode(
            self._parameterNode,
            deleteTemporaryFiles=not self.ui.keepTemporaryFilesCheckBox.checked,
            logToStdout=self.ui.showDetailedLogDuringExecutionCheckBox.checked
        )

    def onLogicSuccess(self):
        """ Apply computed transform to moving volume if output transform is computed to immediately see registration results """

        movingVolumeNode = self.ui.movingVolumeSelector.currentNode()
        if self.ui.outputTransformSelector.currentNode() is not None \
            and movingVolumeNode is not None \
            and self.ui.outputVolumeSelector.currentNode() is None:
            movingVolumeNode.SetAndObserveTransformNodeID(self.ui.outputTransformSelector.currentNode().GetID())

    def updateApplyButtonState(self):
        if self.registrationInProgress or self.logic.isRunning:
            if self.logic.cancelRequested:
                self.ui.applyButton.text = "Cancelling..."
                self.ui.applyButton.enabled = False
            else:
                self.ui.applyButton.text = "Cancel"
                self.ui.applyButton.enabled = True
        else:
            fixedVolumeNode = self._parameterNode.GetNodeReference(self.logic.FIXED_VOLUME_REF)
            movingVolumeNode = self._parameterNode.GetNodeReference(self.logic.MOVING_VOLUME_REF)
            outputVolumeNode = self._parameterNode.GetNodeReference(self.logic.OUTPUT_VOLUME_REF)
            outputTransformNode = self._parameterNode.GetNodeReference(self.logic.OUTPUT_TRANSFORM_REF)
            if not fixedVolumeNode or not movingVolumeNode:
                self.ui.applyButton.text = "Select fixed and moving volumes"
                self.ui.applyButton.enabled = False
            elif fixedVolumeNode == movingVolumeNode:
                self.ui.applyButton.text = "Fixed and moving volume must not be the same"
                self.ui.applyButton.enabled = False
            elif not outputVolumeNode and not outputTransformNode:
                self.ui.applyButton.text = "Select an output volume and/or output transform"
                self.ui.applyButton.enabled = False
            else:
                self.ui.applyButton.text = "Apply"
                self.ui.applyButton.enabled = True
