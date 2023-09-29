import os
import platform
import logging
import shutil

import slicer
from slicer.ScriptedLoadableModule import *

from src.utils import createTempDirectory, createDirectory


def exportNode(node, folder, filename):
    """ todo in nii.gz! """

    filePath = os.path.join(folder, filename)
    slicer.util.exportNode(node, filePath)

    return filePath


class deedsBCVLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    # inputs
    FIXED_VOLUME_REF = 'fixedVolumeSelector'  # MUST match .ui naming
    MOVING_VOLUME_REF = 'movingVolumeSelector'

    # pipeline params
    PIPELINE_STEP_AFFINE_REF = 'pipelineStepAffineButton'
    PIPELINE_STEP_DEFORMABLE_REF = 'pipelineStepDeformableButton'
    PIPELINE_STEP_BOTH_REF = 'pipelineStepBothButton'

    # advanced params
    ADVANCED_REG_PARAM_REF = 'regularisationSpinBox'
    ADVANCED_NLEVELS_PARAM_REF = 'numLevelsSpinBox'
    ADVANCED_SPACING_PARAM_REF = 'gridSpacingSpinBox'
    ADVANCED_MAX_SEARCH_RADIUS_PARAM_REF = 'maxSearchRadiusSpinBox'
    ADVANCED_QUANT_PARAM_REF = 'stepQuantisationSpinBox'

    # outputs
    OUTPUT_VOLUME_REF = 'outputVolumeSelector'

    INPUT_DIR_NAME = 'input'

    def __init__(self) -> None:
        """
        Called when the logic class is instantiated. Can be used for initializing member variables.
        """
        ScriptedLoadableModuleLogic.__init__(self)

        self.logCallback = None
        self.isRunning = False
        self.cancelRequested = False

        self.scriptPath = os.path.dirname(os.path.abspath(__file__))
        self.binDir = None  # this will be determined dynamically

        executableExt = '.exe' if platform.system() == 'Windows' else ''
        self.linearExeFilename = 'linear' + executableExt
        #todo deformable

    def setDefaultParameters(self, parameterNode):
        """
        Initialize parameter node with default settings.
        """

        print('debug only', parameterNode)

        # if not parameterNode.GetParameter(self.FORCE_GRID_TRANSFORM_PARAM):
        #     parameterNode.SetParameter(self.FORCE_GRID_TRANSFORM_PARAM, "False")

        # if not parameterNode.GetParameter(self.REGISTRATION_PRESET_ID_PARAM):
        #     parameterNode.SetParameter(self.REGISTRATION_PRESET_ID_PARAM, self.DEFAULT_PRESET_ID)

    def addLog(self, text):
        logging.info(text)
        if self.logCallback:
            self.logCallback(text)

    def getBinDir(self):
        if not (self.binDir):
            self.binDir = self._findBinDirOrExcept()

        return self.binDir

    def _findBinDirOrExcept(self):
        candidates = [
            # install tree
            os.path.join(self.scriptPath, '..'),
            os.path.join(self.scriptPath, '../../../bin'),
            # build tree
            os.path.join(self.scriptPath, '../../../../bin'),
            os.path.join(self.scriptPath, '../../../../bin/Release'),
            os.path.join(self.scriptPath, '../../../../bin/Debug'),
            os.path.join(self.scriptPath, '../../../../bin/RelWithDebInfo'),
            os.path.join(self.scriptPath, '../../../../bin/MinSizeRel') ]

        for candidate in candidates:
            candidate_path = os.path.join(candidate, self.linearExeFilename)
            if os.path.isfile(candidate_path):
                return os.path.abspath(candidate)

        raise ValueError('Elastix not found')

    def _getEnv(self):  # todo needed?
        """Create an environment for elastix where executables are added to the path"""

        binDir = self.getBinDir()
        binEnv = os.environ.copy()
        binEnv["PATH"] = os.path.join(binDir, binEnv["PATH"]) if binEnv.get("PATH") else binDir

        if platform.system() != 'Windows':
            libDir = os.path.abspath(os.path.join(binDir, '../lib'))
            binEnv["LD_LIBRARY_PATH"] = os.path.join(libDir, binEnv["LD_LIBRARY_PATH"]) if binEnv.get("LD_LIBRARY_PATH") else libDir

        return binEnv

    def runExec(self, cmdLineArguments):
        self.addLog("Register volumes...")

        executableFilePath = os.path.join(
            self.getBinDir(),
            self.linearExeFilename
        )  # todo also deformable
        logging.info(f"Running exe using: {executableFilePath}: {cmdLineArguments!r}")
        return self._createSubProcess(executableFilePath, cmdLineArguments)

    def _createSubProcess(self, executableFilePath, cmdLineArguments):
        full_command = [executableFilePath] + cmdLineArguments
        return subprocess.Popen(
            full_command,
            env=self._getEnv(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            startupinfo=self._getStartupInfo()
        )

    def _getStartupInfo(self):
        if platform.system() != 'Windows':
            return None

        # Hide console window (only needed on Windows)
        info = subprocess.STARTUPINFO()
        info.dwFlags = 1
        info.wShowWindow = 0
        return info

    def _logProcessOutput(self, process, to_stdout=False):
        # save process output (if not logged) so that it can be displayed in case of an error
        processOutput = ''

        while True:  # todo scary
            try:
                stdout_line = process.stdout.readline()
                if not stdout_line:
                    break
                stdout_line = stdout_line.rstrip()

                if to_stdout:
                    self.addLog(stdout_line)
                else:
                    processOutput += stdout_line + '\n'
            except UnicodeDecodeError as e:
                # Probably system locale is set to non-English, we cannot easily capture process output.
                # Code page conversion happens because `universal_newlines=True` sets process output to text mode.
                pass
            slicer.app.processEvents()    # give a chance to click Cancel button
            if self.cancelRequested:
                process.kill()
                break

        process.stdout.close()
        return_code = process.wait()
        if return_code and not self.cancelRequested:
            if processOutput:
                self.addLog(processOutput)
            raise subprocess.CalledProcessError(return_code, "deeds")

    def processParameterNode(self, parameterNode, pipelineSteps, advancedParams, deleteTemporaryFiles, logToStdout):
        fixedVolumeNode = parameterNode.GetNodeReference(self.FIXED_VOLUME_REF)
        movingVolumeNode = parameterNode.GetNodeReference(self.MOVING_VOLUME_REF)

        # todo get more options from `parameterNode`

        self.process(
            fixedVolumeNode,
            movingVolumeNode,
            pipelineSteps,
            advancedParams,
            deleteTemporaryFiles,
            logToStdout
        )

    def _processOrExcept(self,
                tempDir,
                fixedVolumeNode,
                movingVolumeNode,
                logToStdout=False) -> None:
        inputDir = createDirectory(os.path.join(tempDir, self.INPUT_DIR_NAME))
        resultTransformDir = createDirectory(os.path.join(tempDir, self.OUTPUT_TRANSFORM_DIR_NAME))

        # compose parameters
        inputParams = self._addInputVolumes(inputDir, [
            [fixedVolumeNode, 'fixed.nii.gz', '-f'],  # todo check options!
            [movingVolumeNode, 'moving.nii.gz', '-m'],
        ])

        # todo check options!
        #inputParams += self._addParameterFiles(parameterFilenames)
        #inputParams += ['-out', resultTransformDir]

        sub_process = self.runExec(inputParams)
        self._logProcessOutput(sub_process, to_stdout=logToStdout)

        if self.cancelRequested:
            self.addLog("User requested cancel.")
        else:
            self._process_outputs(
                tempDir, parameterFilenames, fixedVolumeNode, movingVolumeNode,
                outputVolumeNode, outputTransformNode
            )
            self.addLog("Registration is completed")

    def process(self,
                fixedVolumeNode,
                movingVolumeNode,
                pipelineSteps='both',
                advancedParams=(1.60, 5, 8, 8, 5),
                deleteTemporaryFiles=False,
                logToStdout=True) -> None:
        """
        Run the processing algorithm.
        Can be used without GUI widget.
        """

        self.isRunning = True
        tempDir = createTempDirectory()
        self.addLog(f'Registration is started in working directory: {tempDir}')

        try:
            self.cancelRequested = False

            print('self._processOrExcept in {}'.format(tempDir))

            print(pipelineSteps)

            regularisation, n_levels, init_grid_spacing, max_search_r, step_q = advancedParams
            print(regularisation, n_levels, init_grid_spacing, max_search_r, step_q)

            if False:  # todo
                self._processOrExcept(
                    tempDir,
                    fixedVolumeNode,
                    movingVolumeNode,
                    logToStdout
                )
        finally:  # Clean up
            if deleteTemporaryFiles:
                shutil.rmtree(tempDir)

            self.isRunning = False
            self.cancelRequested = False

    def _addInputVolumes(self, inputDir, inputVolumes):
        params = []

        for node, filename, paramName in inputVolumes:
            if not node:  # node is not present in scene
                continue

            filePath = exportNode(node, inputDir, filename)
            params += [paramName, filePath]

        return params

    def _process_outputs(self,
                tempDir,
                parameterFilenames,
                fixedVolumeNode,
                movingVolumeNode,
                outputVolumeNode,
                outputTransformNode):
        pass  # todo checkout `_processElastixOutput`

        if slicer.app.majorVersion >= 5 or (slicer.app.majorVersion >= 4 and slicer.app.minorVersion >= 11):
            outputTransformNode.AddNodeReferenceID(
                slicer.vtkMRMLTransformNode.GetFixedNodeReferenceRole(), fixedVolumeNode.GetID()
            )
            outputTransformNode.AddNodeReferenceID(
                slicer.vtkMRMLTransformNode.GetMovingNodeReferenceRole(), movingVolumeNode.GetID()
            )
