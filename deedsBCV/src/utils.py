import qt
import platform

import slicer
from slicer.ScriptedLoadableModule import *

import subprocess
# todo as in https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html#launch-external-process-in-startup-environment ?
# from subprocess import check_output

import numpy as np


def createDirectory(path):
    if qt.QDir().mkpath(path):
        return path
    else:
        raise RuntimeError(f"Failed to create directory {path}")


def getTempDirectoryBase():
    tempDir = qt.QDir(slicer.app.temporaryPath)
    fileInfo = qt.QFileInfo(qt.QDir(tempDir), "deedsBCV")
    return createDirectory(fileInfo.absoluteFilePath())


def createTempDirectory():
    tempDir = qt.QDir(getTempDirectoryBase())
    tempDirName = qt.QDateTime().currentDateTime().toString("yyyyMMdd_hhmmss_zzz")
    fileInfo = qt.QFileInfo(qt.QDir(tempDir), tempDirName)
    return createDirectory(fileInfo.absoluteFilePath())


def pad_smaller_along_depth(fixed_np, moving_np, value='min'):
    """ assuming D, H, W ordering """

    fixed_dimensions = fixed_np.shape
    moving_dimensions = moving_np.shape

    assert fixed_dimensions[1:] == moving_dimensions[1:]  # image dimensions should be the same

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

            fixed_np = np.pad(fixed_np, padding, mode='constant', constant_values=value)
        else:
            if value == 'min':
                value = moving_np.min()

            moving_np = np.pad(moving_np, padding, mode='constant', constant_values=value)

    return fixed_np, moving_np


def getStartupInfo():
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
        startupinfo=getStartupInfo()
        #todo? shell=False
    )
