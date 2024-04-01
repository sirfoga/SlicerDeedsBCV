from slicer.parameterNodeWrapper import *
from slicer import vtkMRMLScalarVolumeNode
import pathlib


@parameterNodeWrapper
class deedsBCVParameterNode:
    """ The parameters needed by module. """

    fixedVolume: vtkMRMLScalarVolumeNode
    movingVolume: vtkMRMLScalarVolumeNode
    outputVolume: vtkMRMLScalarVolumeNode

    regularisationParameter: float = 1.6
    numLevelsParameter: int = 5
    gridSpacingParameter: int = 8
    maxSearchRadiusParameter: int = 8
    stepQuantisationParameter: int = 5
    includeAffineStepParameter: bool = True

    affineParamsInputFilepath: pathlib.Path
    deformableParamsInputFilepath: pathlib.Path

    outputFolder: pathlib.Path
