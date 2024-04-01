import os
import platform
import logging
import shutil
from pathlib import Path
import subprocess

import slicer
from slicer.ScriptedLoadableModule import *
from slicer import vtkMRMLScalarVolumeNode

from src.utils import create_tmp_folder, pad_smaller_along_depth, create_sub_process
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
    PREDICTION_BASENAME = 'pred'

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

        out_folder = Path(fixed_path).parents[0] / self.OUTPUT_FOLDER
        out_folder.mkdir(parents=True, exist_ok=True)

        regularisationParameter, numLevelsParameter, gridSpacingParameter, maxSearchRadiusParameter, stepQuantisationParameter = advanced_params

        cli_args = [
            '-F', fixed_path,
            '-M', moving_path,
            '-O', str(out_folder / self.PREDICTION_BASENAME),
            '-a', '{:.3f}'.format(regularisationParameter),
            '-l', '{:d}'.format(numLevelsParameter),
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

        return str(out_folder / self.PREDICTION_BASENAME) + '{}.nii.gz'.format('deformed')

    # todo def run_apply_exe(self, moving_path, fixed_path, deformable_path, affine_path=None)

    def getParameterNode(self):
        return deedsBCVParameterNode(super().getParameterNode())

    def processParameterNode(self, parameterNode, deleteTemporaryFiles):
        fixedVolumeNode = parameterNode.fixedVolume
        movingVolumeNode = parameterNode.movingVolume

        self.process(
            fixedVolumeNode,
            movingVolumeNode,
            load_result=(
                None if len(str(parameterNode.affineParamsInputFilepath)) < 4 else parameterNode.affineParamsInputFilepath,
                None if len(str(parameterNode.deformableParamsInputFilepath)) < 4 else parameterNode.deformableParamsInputFilepath
            ),
            alsoAffineStep=parameterNode.includeAffineStepParameter,
            advancedParams=(
                parameterNode.regularisationParameter,
                parameterNode.numLevelsParameter,
                parameterNode.gridSpacingParameter,
                parameterNode.maxSearchRadiusParameter,
                parameterNode.stepQuantisationParameter
            ),
            output_folder=None if len(str(parameterNode.outputFolder)) < 4 else parameterNode.outputFolder,
            deleteTemporaryFiles=deleteTemporaryFiles
        )

    def process(self,
                fixedVolumeNode: vtkMRMLScalarVolumeNode,
                movingVolumeNode: vtkMRMLScalarVolumeNode,
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
        self.add_log('Registration is started in {}'.format(tempDir))

        try:
            self.cancelRequested = False

            _, pred_path = self._process_or_except(
                tempDir,
                fixedVolumeNode,
                movingVolumeNode,
                load_result,
                alsoAffineStep,
                advancedParams,
            )

            self._post_process_or_except(
                tempDir, pred_path, fixedVolumeNode, movingVolumeNode
            )

            if not (output_folder is None):  # this folder is already existing
                self.save_to_output_folder(tempDir, Path(output_folder), advancedParams)
        except Exception as e:
            self.add_log('Registration failed! {}'.format(str(e)))
        finally:
            if deleteTemporaryFiles:
                shutil.rmtree(tempDir)

            self.isRunning = False
            self.cancelRequested = False

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

        out_folder = Path(tempDir, self.OUTPUT_FOLDER)
        out_folder.mkdir(parents=True, exist_ok=True)

        affineParamsInputFilepath, deformableParamsInputFilepath = load_result
        use_affine_from_file = not (affineParamsInputFilepath is None) and len(affineParamsInputFilepath) > 4
        use_deformable_from_file = not (deformableParamsInputFilepath is None) and len(deformableParamsInputFilepath) > 4

        if use_affine_from_file:
            affine_path = affineParamsInputFilepath  # todo run affine
        else:  # check if this step needs to be done
            if alsoAffineStep:
                affine_path = self.run_linear_exe(moving_path, fixed_path, str(out_folder), advanced_params=advancedParams)
            else:
                affine_path = None

        if self.cancelRequested:
            raise ValueError('User requested cancel!')

        if use_deformable_from_file:
            pred_path = deformableParamsInputFilepath  # todo apply deformable
        else:
            pred_path = self.run_deformable_exe(moving_path, fixed_path, affine_path, advanced_params=advancedParams)

        if self.cancelRequested:
            raise ValueError('User requested cancel!')

        self.add_log('Done :)')
        return affine_path, pred_path

    def save_to_output_folder(self, working_folder, output_folder, advancedParams):
        for file_name in [
            '{}.nii.gz'.format(self.FIXED_FILENAME),
            '{}.nii.gz'.format(self.MOVING_FILENAME),
            '{}_{}.nii.gz'.format(self.PREDICTION_BASENAME, 'deformed'),
            'affine_matrix.txt'
        ]:
            file_path = Path(working_folder) / file_name
            if not file_path.exists():
                file_path = Path(working_folder) / self.OUTPUT_FOLDER / file_name  # try in outputs folder

            if file_path.exists():
                shutil.copy(
                    file_path,
                    output_folder / file_name
                )

            self.add_log('Cannot copy {} to output folder!'.format(str(file_path)))

        with open(output_folder / 'params.txt', 'w') as fp:
            fp.write(','.join(map(
                lambda x: '{:.5f}'.format(x),
                advancedParams,
            )))

    def _prepareInput(self, folder, fixed_node, moving_node):
        """ pad smaller input, and save as .nii.gz """

        self.add_log('Pre-processing...')

        #todo check if fixed is None (can be since moving with pre-calc results)

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

    def _load2node(self, file_path, ui_node=None):
        loadedNode = slicer.util.loadVolume(file_path)

        if not (ui_node is None):
            ui_node.SetAndObserveImageData(loadedNode.GetImageData())

    def _post_process_or_except(self, tempDir, pred_path, fixedVolumeNode, movingVolumeNode):
        """ parse outputs, save them, and, if possible, show them"""

        self.add_log('Reloading volumes...')

        self._load2node(
            os.path.join(tempDir, '{}.nii.gz'.format(self.FIXED_FILENAME)),
            fixedVolumeNode
        )
        self._load2node(
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
