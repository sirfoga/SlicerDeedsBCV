from slicer.parameterNodeWrapper import *
from slicer import vtkMRMLScalarVolumeNode
from pathlib import Path


@parameterNodeWrapper
class deedsBCVParameterNode:
    """ The parameters needed by module. """

    movingVolume: vtkMRMLScalarVolumeNode
    fixedVolume: vtkMRMLScalarVolumeNode
    outputVolume: vtkMRMLScalarVolumeNode

    regularisationParameter: float = 1.6
    numLevelsParameter: int = 5
    gridSpacingParameter: int = 8
    maxSearchRadiusParameter: int = 8
    stepQuantisationParameter: int = 5
    includeAffineStepParameter: bool = True

    affineParamsInputFilepath: Path
    deformableParamsInputFilepath: Path

    outputFolder: Path
