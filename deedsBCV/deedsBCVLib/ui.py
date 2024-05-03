from pathlib import Path

from slicer import vtkMRMLScalarVolumeNode
from slicer.parameterNodeWrapper import parameterNodeWrapper


@parameterNodeWrapper
class deedsBCVParameterNode:
    """The parameters needed by module."""

    movingVolume: vtkMRMLScalarVolumeNode
    fixedVolume: vtkMRMLScalarVolumeNode

    regularisationParameter: float = 1.6
    numLevelsParameter: int = 5
    gridSpacingParameter: int = 8
    maxSearchRadiusParameter: int = 8
    stepQuantisationParameter: int = 5
    includeAffineStepParameter: bool = True

    affineParamsInputFilepath: Path
    deformableParamsInputFilepath: Path

    outputFolder: Path
