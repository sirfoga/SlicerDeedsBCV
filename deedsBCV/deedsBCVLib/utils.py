import platform
import subprocess

import nibabel as nib

# todo as in https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html#launch-external-process-in-startup-environment ?
# from subprocess import check_output
import numpy as np
import qt
import slicer
from slicer.ScriptedLoadableModule import *


def create_folder(path):
    if qt.QDir().mkpath(path):
        return path
    else:
        raise RuntimeError(f'Failed to create directory {path}')


def create_tmp_folder():
    tmp_dir = qt.QDir(slicer.app.temporaryPath)
    file_info = qt.QFileInfo(qt.QDir(tmp_dir), 'deedsBCV')
    tmp_dir = qt.QDir(create_folder(file_info.absoluteFilePath()))

    temp_dir_name = (
        qt.QDateTime().currentDateTime().toString('yyyyMMdd_hhmmss_zzz')
    )
    file_info = qt.QFileInfo(qt.QDir(tmp_dir), temp_dir_name)
    return create_folder(file_info.absoluteFilePath())


def pad_smaller_along_depth(fixed_np, moving_np, value='min'):
    """assuming D, H, W ordering"""

    fixed_dimensions = fixed_np.shape
    moving_dimensions = moving_np.shape

    assert (
        fixed_dimensions[1:] == moving_dimensions[1:]
    )  # image dimensions should be the same

    fixed_z = fixed_dimensions[0]
    moving_z = moving_dimensions[0]

    if fixed_z != moving_z:
        necessary_padding = max(fixed_z, moving_z) - min(fixed_z, moving_z)
        padding_bottom = necessary_padding // 2
        padding_top = necessary_padding - padding_bottom
        padding = ((padding_bottom, padding_top), (0, 0), (0, 0))

        if fixed_z < moving_z:
            if value == 'min':
                value = fixed_np.min()

            fixed_np = np.pad(
                fixed_np, padding, mode='constant', constant_values=value
            )
        else:
            if value == 'min':
                value = moving_np.min()

            moving_np = np.pad(
                moving_np, padding, mode='constant', constant_values=value
            )

    return fixed_np, moving_np


def get_os_info():
    if platform.system() != 'Windows':
        return None

    # Hide console window (only needed on Windows)
    info = subprocess.STARTUPINFO()
    info.dwFlags = 1
    info.wShowWindow = 0
    return info


def create_sub_process(executableFilePath, cmdLineArguments):
    full_command = [executableFilePath] + cmdLineArguments

    return subprocess.Popen(
        full_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        startupinfo=get_os_info(),
        # todo? shell=False
    )


def np2nifty(x, out_path, affine=np.eye(4)):
    img = nib.Nifti1Image(x.swapaxes(0, 2), affine=affine)

    return nib.save(img, out_path)
