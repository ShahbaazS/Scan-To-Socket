import logging
import os
from typing import Annotated

import vtk
import qt

import slicer
from slicer import vtkMRMLModelNode
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)
from slicer import vtkMRMLMarkupsFiducialNode

from slicer import vtkMRMLScalarVolumeNode


#
# PopScanner
#


class PopScanner(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("PopScanner")  # TODO: make this more human readable by adding spaces
        # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Examples")]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["John Doe (AnyWare Corp.)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#PopScanner">module documentation</a>.
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _("""
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""")

        # Additional initialization step after application startup is complete
        slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#


def registerSampleData():
    """Add data sets to Sample Data module."""
    # It is always recommended to provide sample data for users to make it easy to try the module,
    # but if no sample data is available then this method (and associated startupCompeted signal connection) can be removed.

    import SampleData

    iconsPath = os.path.join(os.path.dirname(__file__), "Resources/Icons")

    # To ensure that the source code repository remains small (can be downloaded and installed quickly)
    # it is recommended to store data sets that are larger than a few MB in a Github release.

    # PopScanner1
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category="PopScanner",
        sampleName="PopScanner1",
        # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
        # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
        thumbnailFileName=os.path.join(iconsPath, "PopScanner1.png"),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        fileNames="PopScanner1.nrrd",
        # Checksum to ensure file integrity. Can be computed by this command:
        #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
        checksums="SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        # This node name will be used when the data set is loaded
        nodeNames="PopScanner1",
    )

    # PopScanner2
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category="PopScanner",
        sampleName="PopScanner2",
        thumbnailFileName=os.path.join(iconsPath, "PopScanner2.png"),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        fileNames="PopScanner2.nrrd",
        checksums="SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        # This node name will be used when the data set is loaded
        nodeNames="PopScanner2",
    )


#
# PopScannerParameterNode
#


@parameterNodeWrapper
class PopScannerParameterNode:
    """
    The parameters needed by module.

    inputFilePath - Path to the STL or OBJ file to process.
    imageThreshold - The value at which to threshold the input volume.
    invertThreshold - If true, will invert the threshold.
    thresholdedVolume - The output volume that will contain the thresholded volume.
    invertedVolume - The output volume that will contain the inverted thresholded volume.
    """

    inputFilePath: str
    outputModel: vtkMRMLModelNode
    # New nodes for registration
    armLandmarks: vtkMRMLMarkupsFiducialNode
    prostheticLandmarks: vtkMRMLMarkupsFiducialNode


#
# PopScannerWidget
#


class PopScannerWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/PopScanner.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = PopScannerLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.inputFileBrowseButton.connect("clicked(bool)", self.onBrowseInputFile)

        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()
        
        # Load the prosthetic elbow model at startup
        self.loadProstheticModel()

    def loadProstheticModel(self) -> None:
        """Load the prosthetic elbow model at startup."""
        # Get the path relative to this module
        moduleDir = os.path.dirname(os.path.abspath(__file__))
        prostheticModelPath = os.path.join(os.path.dirname(moduleDir), "elbow.stl")
        
        if not os.path.exists(prostheticModelPath):
            slicer.util.errorDisplay(
                f"Prosthetic model not found at:\n{prostheticModelPath}\n\n"
                "Please ensure the elbow.stl file is in the correct location."
            )
            logging.error(f"Prosthetic model file not found: {prostheticModelPath}")
            return
        
        try:
            success, modelNode = slicer.util.loadModel(prostheticModelPath, returnNode=True)
            if success and modelNode:
                # Rename for clarity in the scene
                modelNode.SetName("Prosthetic Elbow")
                # Set color to green
                displayNode = modelNode.GetDisplayNode()
                if displayNode:
                    displayNode.SetColor(0, 1, 0)  # Green: R=0, G=1, B=0
                logging.info(f"Prosthetic model loaded successfully: {modelNode.GetName()}")
            else:
                slicer.util.errorDisplay("Failed to load the prosthetic model (elbow.stl).")
                logging.error("Failed to load prosthetic model")
        except Exception as e:
            logging.error(f"Error loading prosthetic model: {str(e)}")
            slicer.util.errorDisplay(f"Error loading prosthetic model:\n{str(e)}")

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """Ensure parameter node exists and observed."""
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

    def setParameterNode(self, inputParameterNode: PopScannerParameterNode | None) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        # Logic: Only enable if we have an input file AND both sets of landmarks have 3 points
        armReady = self.ui.armMarkupsWidget.currentNode() and self.ui.armMarkupsWidget.currentNode().GetNumberOfControlPoints() >= 3
        prosReady = self.ui.prostheticMarkupsWidget.currentNode() and self.ui.prostheticMarkupsWidget.currentNode().GetNumberOfControlPoints() >= 3
        
        if self._parameterNode and self._parameterNode.inputFilePath and armReady and prosReady:
            self.ui.applyButton.text = _("Align Prosthetic")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.text = _("Place 3 points on each model")
            self.ui.applyButton.enabled = False

    def onApplyButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Perform registration using arm and prosthetic landmarks
            self.logic.process(
                self._parameterNode.inputFilePath,
                self.ui.armMarkupsWidget.currentNode(),
                self.ui.prostheticMarkupsWidget.currentNode()
            )
    def onBrowseInputFile(self) -> None:
        """Open file dialog to select STL or OBJ file."""
        fileName = qt.QFileDialog.getOpenFileName(
            None,
            "Select STL or OBJ file",
            "",
            "Model files (*.stl *.obj);;All files (*)"
        )
        if fileName:
            self.ui.inputFilePathEdit.setText(fileName)
            self._parameterNode.inputFilePath = fileName
            
            # Load and display the model in the 3D scene
            try:
                success, modelNode = slicer.util.loadModel(fileName, returnNode=True)
                if success and modelNode:
                    # Set color to red
                    displayNode = modelNode.GetDisplayNode()
                    if displayNode:
                        displayNode.SetColor(1, 0, 0)  # Red: R=1, G=0, B=0
                    logging.info(f"Model loaded successfully: {modelNode.GetName()}")
                    # The model is automatically added to the scene and visible
                else:
                    slicer.util.errorDisplay("Failed to load the selected file. Please check if it's a valid STL or OBJ file.")
            except Exception as e:
                logging.error(f"Error loading model: {str(e)}")
                slicer.util.errorDisplay(f"Error loading model: {str(e)}")

#
# PopScannerLogic
#


class PopScannerLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

    def getParameterNode(self):
        return PopScannerParameterNode(super().getParameterNode())

    def process(self, inputFilePath: str, outputModel: vtkMRMLModelNode) -> None:
        """
        Loads an STL, computes its orientation via PCA, and prepares it for registration.
        """
        if not inputFilePath or not os.path.exists(inputFilePath):
            raise ValueError("Input file path is invalid")

        # 1. Load the STL/OBJ file
        # We use a specific model loader to ensure it's handled as a mesh
        success, modelNode = slicer.util.loadModel(inputFilePath, returnNode=True)
        if not success:
            raise ValueError(f"Failed to load model from: {inputFilePath}")

        logging.info(f"Model loaded: {modelNode.GetName()}")

        # 2. PCA Orientation (Logic for your perpendicular circle plan)
        # This finds the 'long' axis of the arm scan
        import numpy as np
        polyData = modelNode.GetPolyData()
        points = polyData.GetPoints()
        n_points = points.GetNumberOfPoints()
        
        # Convert VTK points to Numpy for PCA
        point_array = np.array([points.GetPoint(i) for i in range(n_points)])
        centroid = np.mean(point_array, axis=0)
        
        # Compute PCA using Singular Value Decomposition
        datacenter = point_array - centroid
        _, _, vh = np.linalg.svd(datacenter, full_matrices=False)
        major_axis = vh[0] # This is the vector of the arm's length
        
        logging.info(f"Arm major axis computed: {major_axis}")
        
        # 3. Future Step: Landmark Registration
        # You will use 'major_axis' to place your perpendicular circles here.


#
# PopScannerTest
#


class PopScannerTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_PopScanner1()

    def test_PopScanner1(self):
        """Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")

        # Get/create input data

        import SampleData
        import tempfile

        registerSampleData()
        inputVolume = SampleData.downloadSample("PopScanner1")
        self.delayDisplay("Loaded test data set")

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        # Save input volume as a temporary STL file for testing file path input
        tempDir = tempfile.gettempdir()
        testFilePath = os.path.join(tempDir, "test_input.stl")
        # Note: In production, you would convert the volume to a model and save as STL
        # For this test, we'll use the volume directly via slicer's save function
        slicer.util.saveNode(inputVolume, testFilePath)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = PopScannerLogic()

        # Test algorithm with non-inverted threshold
        logic.process(testFilePath, outputVolume, threshold, True)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], threshold)

        # Test algorithm with inverted threshold
        logic.process(testFilePath, outputVolume, threshold, False)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], inputScalarRange[1])

        # Clean up temporary file
        if os.path.exists(testFilePath):
            os.remove(testFilePath)

        self.delayDisplay("Test passed")
