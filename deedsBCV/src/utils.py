import qt
import slicer
from slicer.ScriptedLoadableModule import *


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
