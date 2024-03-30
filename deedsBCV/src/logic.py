import os
import platform
import logging
import shutil
import subprocess

import slicer
from slicer.ScriptedLoadableModule import *
from slicer import vtkMRMLScalarVolumeNode

from src.utils import create_tmp_folder, create_folder, pad_smaller_along_depth, create_sub_process
from src.ui import deedsBCVParameterNode


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
    PIPELINE_STEPS = 'includeAffineStepCheckbox'

    # advanced params
    ADVANCED_REG_PARAM_REF = 'regularisationSpinBox'
    ADVANCED_NLEVELS_PARAM_REF = 'numLevelsSpinBox'
    ADVANCED_SPACING_PARAM_REF = 'gridSpacingSpinBox'
    ADVANCED_MAX_SEARCH_RADIUS_PARAM_REF = 'maxSearchRadiusSpinBox'
    ADVANCED_QUANT_PARAM_REF = 'stepQuantisationSpinBox'

    # outputs
    OUTPUT_VOLUME_REF = 'outputVolumeSelector'
    OUTPUT_FOLDER = 'outputs'

    # files
    FIXED_FILENAME = 'fixed'
    MOVING_FILENAME = 'moving'

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

        pass

    def addLog(self, text):
        logging.info(text)

        if self.logCallback:
            self.logCallback(text)
        else:
            print('debug no log callback found')

    def getBinDir(self):
        if not (self.binDir):
            self.binDir = self._findBinDirOrExcept()

        return self.binDir

    def _findBinDirOrExcept(self):
        candidates = [
            # build tree
            os.path.join(self.scriptPath, '../../build/bin'),
        ]

        for candidate in candidates:
            candidate_path = os.path.join(candidate, self.linearExeFilename)
            if os.path.isfile(candidate_path):
                return os.path.abspath(candidate)

        raise ValueError('bin not found')

    def _handleProcess(self, process, to_stdout=False):
        # save process output (if not logged) so that it can be displayed in case of an error
        processOutput = ''

        while True:  # todo scary
            try:
                stdout_line = process.stdout.readline()
                if not stdout_line:
                    self.addLog('Sub-process exited')
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

            slicer.app.processEvents()  # give a chance to click Cancel button
            if self.cancelRequested:
                process.kill()
                self.addLog('Sub-process killed')
                break

        process.stdout.close()
        self.addLog('Waiting for sub-process return code')
        return_code = process.wait()

        if return_code and not self.cancelRequested:
            if processOutput:
                self.addLog(processOutput)

            raise subprocess.CalledProcessError(return_code, 'deeds')

    def run_linear_exe(self, moving_path, fixed_path, out_folder, advanced_params=None):
        """ output matrix will be on fixed volume's folder; todo parse `advancedParams` """

        affine_path = os.path.join(out_folder, 'affine')

        cli_args = [
            '-F', fixed_path,
            '-M', moving_path,
            '-O', affine_path
        ]
        exe_path = os.path.join(self.getBinDir(), 'linear')
        process = create_sub_process(exe_path, cli_args)
        self._handleProcess(process, to_stdout=True)

        return affine_path + '_matrix.txt'  # deeds will append this

    def run_deformable_exe(self, moving_path, fixed_path, affine_path=None, advanced_params=None):
        """ todo parse `advancedParams` """

        if not (affine_path is None):
            out_folder, _ = os.path.split(os.path.abspath(affine_path))
            out_folder = out_folder + '/pred'
        else:
            out_folder, _ = os.path.split(os.path.abspath(fixed_path))
            out_folder = os.path.join(out_folder, '/{}'.format(self.OUTPUT_FOLDER))
            create_folder(out_folder)

            out_folder = os.path.join(out_folder, '/pred')
            print('debug created out folder @', out_folder)

        cli_args = [
            '-F', fixed_path,
            '-M', moving_path,
            '-O', out_folder
        ]
        if not (affine_path is None):
            cli_args += [
                '-A', affine_path
            ]

        exe_path = os.path.join(self.getBinDir(), 'deeds')
        process = create_sub_process(exe_path, cli_args)
        self._handleProcess(process, to_stdout=True)

        return out_folder  # output basename path

    def getParameterNode(self):
        return deedsBCVParameterNode(super().getParameterNode())

    def processParameterNode(self, parameterNode, alsoAffineStep, advancedParams, deleteTemporaryFiles):
        fixedVolumeNode = parameterNode.fixedVolume
        movingVolumeNode = parameterNode.movingVolume
        outputVolumeNode = parameterNode.outputVolume

        self.process(
            fixedVolumeNode,
            movingVolumeNode,
            outputVolumeNode,
            alsoAffineStep,
            advancedParams,
            deleteTemporaryFiles
        )

    def process(self,
                fixedVolumeNode: vtkMRMLScalarVolumeNode,
                movingVolumeNode: vtkMRMLScalarVolumeNode,
                outputVolumeNode: vtkMRMLScalarVolumeNode,
                alsoAffineStep: bool = True,
                advancedParams: tuple[float] = (1.60, 5, 8, 8, 5),
                deleteTemporaryFiles: bool = False) -> None:
        """
        Run the processing algorithm.
        Can be used without GUI widget.
        """

        self.isRunning = True
        tempDir = create_tmp_folder()
        self.addLog('Registration is started in working directory: {}'.format(tempDir))

        try:
            self.cancelRequested = False
            affine_path, pred_path = self._process_or_except(
                tempDir,
                fixedVolumeNode,
                movingVolumeNode,
                alsoAffineStep,
                advancedParams,
            )

            self._post_process_or_except(
                tempDir,
                affine_path, pred_path,
                fixedVolumeNode, movingVolumeNode, outputVolumeNode,
            )
        except Exception as e:
            self.addLog('Registration failed due to {}'.format(str(e)))
        finally:
            if deleteTemporaryFiles:
                shutil.rmtree(tempDir)

            self.isRunning = False
            self.cancelRequested = False

    def _process_or_except(self,
                tempDir,
                fixedVolumeNode,
                movingVolumeNode,
                alsoAffineStep,
                advancedParams) -> None:
        fixed_path, moving_path = self._prepareInput(
            tempDir, fixedVolumeNode, movingVolumeNode
        )

        out_folder = os.path.join(tempDir, '{}'.format(self.OUTPUT_FOLDER))
        create_folder(out_folder)

        if alsoAffineStep:
            affine_path = self.run_linear_exe(moving_path, fixed_path, out_folder, advanced_params=advancedParams)
        else:
            affine_path = None

        if self.cancelRequested:
            raise ValueError('User requested cancel!')

        pred_path = self.run_deformable_exe(moving_path, fixed_path, affine_path, advanced_params=advancedParams)

        if self.cancelRequested:
            raise ValueError('User requested cancel!')

        self.addLog('Done :)')
        return affine_path, pred_path

    def _prepareInput(self, folder, fixed_node, moving_node):
        """ pad smaller input, and save as .nii.gz """

        self.addLog('Pre-processing...')

        fixed_np = slicer.util.arrayFromVolume(fixed_node)
        moving_np = slicer.util.arrayFromVolume(moving_node)

        fixed_np, moving_np = pad_smaller_along_depth(fixed_np, moving_np)

        # update nodes, and export them
        slicer.util.updateVolumeFromArray(fixed_node, fixed_np)
        fixed_path = os.path.join(folder, '{}.nii.gz'.format(self.FIXED_FILENAME))
        slicer.util.exportNode(fixed_node, fixed_path)

        slicer.util.updateVolumeFromArray(moving_node, moving_np)
        moving_path = os.path.join(folder, '{}.nii.gz'.format(self.MOVING_FILENAME))
        slicer.util.exportNode(moving_node, moving_path)

        return fixed_path, moving_path

    def _load_and_display(self, file_path, ui_node):
        loadedOutputVolumeNode = slicer.util.loadVolume(file_path)
        ui_node.SetAndObserveImageData(loadedOutputVolumeNode.GetImageData())

    def _post_process_or_except(self,
                tempDir,
                affine_path, pred_path,
                fixedVolumeNode, movingVolumeNode, outputVolumeNode):
        """ parse outputs, save them, and, if possible, show them"""

        self.addLog('Reloading volumes...')

        self._load_and_display(
            os.path.join(tempDir, '{}.nii.gz'.format(self.FIXED_FILENAME)),
            fixedVolumeNode
        )
        self._load_and_display(
            os.path.join(tempDir, '{}.nii.gz'.format(self.MOVING_FILENAME)),
            movingVolumeNode
        )
        self._load_and_display(
            pred_path + '_deformed.nii.gz',
            outputVolumeNode
        )  # todo add correct affine params

        #todo save `affine_path` in Export menu
