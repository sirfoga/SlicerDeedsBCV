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

        # todo remove toolbar, only show modules, mouse, contrast
        # todo remove statusbar if main app: slicer.util.setStatusBarVisible(False)

    def _setupConnections(self) -> None:
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)

        # toggle file browser
        self.ui.loadAffineCheckBox.toggled.connect(self._toggleLoadAffineFileBrowser)
        self.ui.loadAffineCheckBox.toggled.connect(self._onParameterNodeChange)

        self.ui.loadDeformableCheckBox.toggled.connect(self._toggleLoadDeformableFileBrowser)
        self.ui.loadDeformableCheckBox.toggled.connect(self._onParameterNodeChange)

        self.ui.saveOutputsCheckBox.toggled.connect(self._toggleSaveOutputsFileBrowser)

    def _toggleLoadAffineFileBrowser(self):
        self.ui.affineParamsLineEdit.setEnabled(
            self.ui.loadAffineCheckBox.checked
        )

    def _toggleLoadDeformableFileBrowser(self):
        self.ui.deformableParamsLineEdit.setEnabled(
            self.ui.loadDeformableCheckBox.checked
        )

    def _toggleSaveOutputsFileBrowser(self):
        self.ui.outputFolderLineEdit.setEnabled(
            self.ui.saveOutputsCheckBox.checked
        )

    def setParameterNode(self, inputParameterNode: Optional[deedsBCVParameterNode] = None) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if inputParameterNode:
            self.logic.set_default_parameters(inputParameterNode)

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

        self._updateApplyButtonState()

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
                    self._updateApplyButtonState()

                    self.runLogicOrExcept()
                    self.onLogicSuccess()
                finally:
                    self.registrationInProgress = False

        self._updateApplyButtonState()

    def getUIProperty(self, key, prop):
        widget = getattr(self.ui, key)
        return getattr(widget, prop)

    def runLogicOrExcept(self):
        if not self.ui.loadAffineCheckBox.checked:
            self._parameterNode.affineParamsInputFilepath = None

        if not self.ui.loadDeformableCheckBox.checked:
            self._parameterNode.deformableParamsInputFilepath = None

        if not self.ui.saveOutputsCheckBox.checked:
            self._parameterNode.outputFolder = None

        self.logic.processParameterNode(
            self._parameterNode,
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

    def _updateApplyButtonState(self):
        if self.registrationInProgress or self.logic.isRunning:
            if self.logic.cancelRequested:
                self.disableApplyButton('Cancelling...')
            else:
                self.enableApplyButton('Cancel')
        else:
            movingVolumeNode = self._parameterNode.movingVolume
            fixedVolumeNode = self._parameterNode.fixedVolume
            outputVolumeNode = self._parameterNode.outputVolume

            affineParamsPath = self._parameterNode.affineParamsInputFilepath
            deformableParamsPath = self._parameterNode.deformableParamsInputFilepath

            if not movingVolumeNode:
                self.disableApplyButton('Select at least the moving volume')
                return

            loading_pre_result = (self.ui.loadAffineCheckBox.checked and len(str(affineParamsPath)) > 4) or (self.ui.loadDeformableCheckBox.checked and len(str(deformableParamsPath)) > 4)
            computing_result = not(fixedVolumeNode is None)

            if loading_pre_result and computing_result:
                self.disableApplyButton('Fixed volume is chosen, even if loading from file!')
                return

            if fixedVolumeNode == movingVolumeNode:
                self.disableApplyButton('Fixed and moving volume are the same!')
                return

            if not outputVolumeNode:
                self.disableApplyButton('Select an output volume')
                return
            
            print()

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
