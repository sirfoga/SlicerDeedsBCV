from slicer.ScriptedLoadableModule import *


def createDirectory(path):
    if qt.QDir().mkpath(path):
        return path
    else:
        raise RuntimeError(f"Failed to create directory {path}")
