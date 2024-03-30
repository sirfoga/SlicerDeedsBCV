from slicer.parameterNodeWrapper import *
from slicer import vtkMRMLScalarVolumeNode


@parameterNodeWrapper
class deedsBCVParameterNode:
    """ The parameters needed by module. """

    fixedVolume: vtkMRMLScalarVolumeNode
    movingVolume: vtkMRMLScalarVolumeNode
    outputVolume: vtkMRMLScalarVolumeNode
