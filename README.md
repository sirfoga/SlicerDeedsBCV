# Get ready

1. download [Slicer](https://slicer.org/)
2. build it, i.e [Release mode](https://slicer.readthedocs.io/en/latest/developer_guide/build_instructions/linux.html#configure-and-generate-the-slicer-build-project-files)
3. build this extension `cmake -DSlicer_DIR:PATH=~/scratch/Slicer/Slicer-SuperBuild-Debug/Slicer-build -DSlicer_EXTENSION_DESCRIPTION_DIR:PATH=~/ExtensionsIndex -DCMAKE_BUILD_TYPE:STRING=Release ..`

# References

- icon is Figure 2 from the original paper: "MRF-Based Deformable Registration and Ventilation Estimation of Lung CT." by Mattias P. Heinrich, M. Jenkinson, M. Brady and J.A. Schnabel IEEE Transactions on Medical Imaging 2013, Volume 32, Issue 7, July 2013, Pages 1239-1248 http://dx.doi.org/10.1109/TMI.2013.2246577
