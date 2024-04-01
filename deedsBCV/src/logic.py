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

    MOVING_FILENAME = 'moving'
    FIXED_FILENAME = 'fixed'
    OUTPUT_FOLDER = 'outputs'

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

    def set_default_parameters(self, parameterNode):
        """
        Initialize parameter node with default settings.
        """

        pass

    def add_log(self, text):
        logging.info(text)

        if self.logCallback:
            self.logCallback(text)
        else:
            print('debug no log callback found')

    def get_bin_folder(self):
        if not (self.binDir):
            self.binDir = self._find_bin_folder_or_except()

        return self.binDir

    def _find_bin_folder_or_except(self):
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
                    self.add_log('Sub-process exited')
                    break

                stdout_line = stdout_line.rstrip()

                if to_stdout:
                    self.add_log(stdout_line)
                else:
                    processOutput += stdout_line + '\n'
            except UnicodeDecodeError as e:
                # Probably system locale is set to non-English, we cannot easily capture process output.
                # Code page conversion happens because `universal_newlines=True` sets process output to text mode.
                pass

            slicer.app.processEvents()  # give a chance to click Cancel button
            if self.cancelRequested:
                process.kill()
                self.add_log('Sub-process killed')
                break

        process.stdout.close()
        self.add_log('Waiting for sub-process return code')
        return_code = process.wait()

        if return_code and not self.cancelRequested:
            if processOutput:
                self.add_log(processOutput)

            raise subprocess.CalledProcessError(return_code, 'deeds')

    def run_linear_exe(self, moving_path, fixed_path, out_folder, advanced_params=None):
        """ output matrix will be on fixed volume's folder; todo parse `advancedParams` """

        affine_path = os.path.join(out_folder, 'affine')
        regularisationParameter, numLevelsParameter, gridSpacingParameter, maxSearchRadiusParameter, stepQuantisationParameter = advanced_params
        # todo use them!

        cli_args = [
            '-F', fixed_path,
            '-M', moving_path,
            '-O', affine_path
        ]
        exe_path = os.path.join(self.get_bin_folder(), 'linear')
        process = create_sub_process(exe_path, cli_args)
        self._handleProcess(process, to_stdout=True)

        return affine_path + '_matrix.txt'  # deeds will append this

    def run_deformable_exe(self, moving_path, fixed_path, affine_path=None, advanced_params=None):
        def _build_stepped_param(init_value, n_steps):
            out = [
                init_value - i  # decrease by 1 each level
                for i in range(n_steps)
            ]
            return 'x'.join(map(str, out))

        if not (affine_path is None):
            out_folder, _ = os.path.split(os.path.abspath(affine_path))
            out_folder = out_folder + '/pred'
        else:
            out_folder, _ = os.path.split(os.path.abspath(fixed_path))
            out_folder = os.path.join(out_folder, '/{}'.format(self.OUTPUT_FOLDER))
            create_folder(out_folder)

            out_folder = os.path.join(out_folder, '/pred')
            print('debug created out folder @', out_folder)

        regularisationParameter, numLevelsParameter, gridSpacingParameter, maxSearchRadiusParameter, stepQuantisationParameter = advanced_params

        cli_args = [
            '-F', fixed_path,
            '-M', moving_path,
            '-O', out_folder,
            '-a', regularisationParameter,
            '-l', numLevelsParameter,
            '-G', _build_stepped_param(gridSpacingParameter, numLevelsParameter),
            '-L', _build_stepped_param(maxSearchRadiusParameter, numLevelsParameter),
            '-Q', _build_stepped_param(stepQuantisationParameter, numLevelsParameter)
        ]
        if not (affine_path is None):
            cli_args += [
                '-A', affine_path
            ]

        exe_path = os.path.join(self.get_bin_folder(), 'deeds')
        process = create_sub_process(exe_path, cli_args)
        self._handleProcess(process, to_stdout=True)

        return out_folder  # output basename path

    # todo def run_apply_exe(self, moving_path, fixed_path, deformable_path, affine_path=None)

    def getParameterNode(self):
        return deedsBCVParameterNode(super().getParameterNode())

    def processParameterNode(self, parameterNode, deleteTemporaryFiles):
        fixedVolumeNode = parameterNode.fixedVolume
        movingVolumeNode = parameterNode.movingVolume
        outputVolumeNode = parameterNode.outputVolume

        self.process(
            fixedVolumeNode,
            movingVolumeNode,
            outputVolumeNode,
            load_result=(
                parameterNode.affineParamsInputFilepath,
                parameterNode.deformableParamsInputFilepath
            ),
            alsoAffineStep=parameterNode.includeAffineStepParameter,
            advancedParams=(
                parameterNode.regularisationParameter,
                parameterNode.numLevelsParameter,
                parameterNode.gridSpacingParameter,
                parameterNode.maxSearchRadiusParameter,
                parameterNode.stepQuantisationParameter
            ),
            output_folder=parameterNode.outputFolder,
            deleteTemporaryFiles=deleteTemporaryFiles
        )

    def process(self,
                fixedVolumeNode: vtkMRMLScalarVolumeNode,
                movingVolumeNode: vtkMRMLScalarVolumeNode,
                outputVolumeNode: vtkMRMLScalarVolumeNode,
                load_result=(None, None),
                alsoAffineStep: bool = True,
                advancedParams: tuple[float] = (1.60, 5, 8, 8, 5),
                output_folder=None,
                deleteTemporaryFiles: bool = False) -> None:
        """
        Run the processing algorithm.
        Can be used without GUI widget.
        """

        self.isRunning = True
        tempDir = create_tmp_folder()
        self.add_log('Registration is started in working directory: {}'.format(tempDir))

        try:
            self.cancelRequested = False
            affine_path, pred_path = self._process_or_except(
                tempDir,
                fixedVolumeNode,
                movingVolumeNode,
                load_result,
                alsoAffineStep,
                advancedParams,
            )

            self._post_process_or_except(
                tempDir,
                affine_path, pred_path,
                fixedVolumeNode, movingVolumeNode, outputVolumeNode,
            )
        except Exception as e:
            self.add_log('Registration failed due to {}'.format(str(e)))
        finally:
            if deleteTemporaryFiles:
                shutil.rmtree(tempDir)

            self.isRunning = False
            self.cancelRequested = False

        # todo save to output_folder if needed

    def _process_or_except(self,
                tempDir,
                fixedVolumeNode,
                movingVolumeNode,
                load_result,
                alsoAffineStep,
                advancedParams) -> None:
        fixed_path, moving_path = self._prepareInput(
            tempDir, fixedVolumeNode, movingVolumeNode
        )

        out_folder = os.path.join(tempDir, '{}'.format(self.OUTPUT_FOLDER))
        create_folder(out_folder)

        # todo use load_result if needed

        if alsoAffineStep:
            affine_path = self.run_linear_exe(moving_path, fixed_path, out_folder, advanced_params=advancedParams)
        else:
            affine_path = None

        if self.cancelRequested:
            raise ValueError('User requested cancel!')

        pred_path = self.run_deformable_exe(moving_path, fixed_path, affine_path, advanced_params=advancedParams)

        if self.cancelRequested:
            raise ValueError('User requested cancel!')

        self.add_log('Done :)')
        return affine_path, pred_path

    def _prepareInput(self, folder, fixed_node, moving_node):
        """ pad smaller input, and save as .nii.gz """

        self.add_log('Pre-processing...')

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

        self.add_log('Reloading volumes...')

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
