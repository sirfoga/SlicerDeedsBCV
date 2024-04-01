import vtk
import qt
import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from typing import Optional
from pathlib import Path
import os

from src.logic import deedsBCVLogic as Logic
from src.ui import deedsBCVParameterNode


def load2node(file_path, ui_node=None):
    loadedNode = slicer.util.loadVolume(file_path)

    if not (ui_node is None):
        ui_node.SetAndObserveImageData(loadedNode.GetImageData())


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

        self.isSingleModuleShown = False
        slicer.util.mainWindow().setWindowTitle('Liver registration')
        self._show_single_module(True)

        self._setup_shortcuts()
        self._setup_connections()

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

    def _setup_connections(self) -> None:
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)

        # toggle file browser
        self.ui.loadAffineCheckBox.toggled.connect(self._toggleLoadAffineFileBrowser)
        self.ui.loadAffineCheckBox.toggled.connect(self._onParameterNodeChange)

        self.ui.loadDeformableCheckBox.toggled.connect(self._toggleLoadDeformableFileBrowser)
        self.ui.loadDeformableCheckBox.toggled.connect(self._onParameterNodeChange)

        self.ui.saveOutputsCheckBox.toggled.connect(self._toggleSaveOutputsFileBrowser)

    def _setup_shortcuts(self):
        shortcut = qt.QShortcut(slicer.util.mainWindow())
        shortcut.setKey(qt.QKeySequence('Ctrl+Shift+b'))
        shortcut.connect('activated()', lambda: self._show_single_module(toggle=True))

    def _show_single_module(self, singleModule=True, toggle=False):
        if toggle:
            singleModule = not self.isSingleModuleShown

        self.isSingleModuleShown = singleModule

        if singleModule:
            # We hide all toolbars, etc. which is inconvenient as a default startup setting,
            # therefore disable saving of window setup.

            import qt
            settings = qt.QSettings()
            settings.setValue('MainWindow/RestoreGeometry', 'false')

        keepToolbars = [
            slicer.util.findChild(slicer.util.mainWindow(), toolbar)
            for toolbar in ['ModuleSelectorToolBar', 'MouseModeToolBar']
        ]
        slicer.util.setToolbarsVisible(not singleModule, keepToolbars)

        slicer.util.setMenuBarsVisible(not singleModule)
        slicer.util.setApplicationLogoVisible(not singleModule)
        slicer.util.setModuleHelpSectionVisible(not singleModule)
        slicer.util.setModulePanelTitleVisible(not singleModule)
        slicer.util.setViewControllersVisible(not singleModule)

        if singleModule:
            slicer.util.setPythonConsoleVisible(False)
            slicer.util.setStatusBarVisible(False)

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
            self._parameterNode.affineParamsInputFilepath = Path('')

        if not self.ui.loadDeformableCheckBox.checked:
            self._parameterNode.deformableParamsInputFilepath = Path('')

        if not self.ui.saveOutputsCheckBox.checked:
            self._parameterNode.outputFolder = Path('')

        tempDir, pred_path = self.logic._processParameterNode(
            self._parameterNode,
            deleteTemporaryFiles=False,
            #deprecated, of course log! logToStdout=True
        )

        if not (pred_path is None):
            self._post_process_or_except(
                tempDir, pred_path
            )

    def _post_process_or_except(self, tempDir, pred_path):
        """ parse outputs, save them, and, if possible, show them"""

        fixedVolumeNode, movingVolumeNode = self._parameterNode.fixedVolume, self._parameterNode.movingVolume

        load2node(
            os.path.join(tempDir, '{}.nii.gz'.format(self.FIXED_FILENAME)),
            fixedVolumeNode
        )
        load2node(
            os.path.join(tempDir, '{}.nii.gz'.format(self.MOVING_FILENAME)),
            movingVolumeNode
        )

        properties = {
            'name': 'moved',
            'singleFile': True,
            'discardOrientation': False,  # liver on bottom-left
            'autoWindowLevel': False,  # don't even need if using pre-processed data
            'show': True
        }
        slicer.util.loadVolume(pred_path, properties=properties)  # no node required

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

            if (not computing_result) and (not loading_pre_result):
                self.disableApplyButton('Choose a fixed volume or load from file!')
                return

            if fixedVolumeNode == movingVolumeNode:
                self.disableApplyButton('Fixed and moving volume are the same!')
                return

            self.enableApplyButton('Register!')

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
