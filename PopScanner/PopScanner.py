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
        self.parent.title = _("PopScanner")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Prosthetics")]
        self.parent.dependencies = []
        self.parent.contributors = ["Emese Elkind, Shahbaaz Siddiqui"]
        self.parent.helpText = _("Module developed by Q-CAR for above-elbow prosthetic alignment.")
        self.parent.acknowledgementText = _("Developed by Q-CARE.")

        # --- ADD THESE LINES FOR THE LOGO ---
        moduleDir = os.path.dirname(os.path.abspath(__file__))
        # Assuming your logo is in a 'Resources/Icons' folder relative to this file
        iconPath = os.path.join(moduleDir, 'Resources', 'Icons', 'qcare logo2.png')
        
        if os.path.exists(iconPath):
            self.parent.icon = qt.QIcon(iconPath)
        else:
            logging.error(f"Logo not found at {iconPath}")
        # -------------------------------------

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

        uiWidget = slicer.util.loadUI(self.resourcePath("UI/PopScanner.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        uiWidget.setMRMLScene(slicer.mrmlScene)

        self.logic = PopScannerLogic()
        
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.inputFileBrowseButton.connect("clicked(bool)", self.onBrowseInputFile)
        
        # --- Connections for reactivity ---
        self.ui.armMarkupsWidget.connect("markupsNodeChanged()", self._onArmMarkupsNodeChanged)
        self.ui.prostheticMarkupsWidget.connect("markupsNodeChanged()", self._onProstheticMarkupsNodeChanged)
        
        self.ui.armMarkupsWidget.connect("activeMarkupsNodeChanged(vtkMRMLNode*)", self._onArmMarkupsNodeChanged)
        self.ui.prostheticMarkupsWidget.connect("activeMarkupsNodeChanged(vtkMRMLNode*)", self._onProstheticMarkupsNodeChanged)

        self.initializeParameterNode()
        self.loadProstheticModel()

    def loadProstheticModel(self) -> None:
        """Load the prosthetic elbow model at startup."""
        # Get the path relative to this module
        moduleDir = os.path.dirname(os.path.abspath(__file__))
        prostheticModelPath = os.path.join(os.path.dirname(moduleDir), "elbow.stl")
        
        logging.info(f"Looking for prosthetic model at: {prostheticModelPath}")
        
        if not os.path.exists(prostheticModelPath):
            logging.error(f"Prosthetic model file not found: {prostheticModelPath}")
            slicer.util.errorDisplay(
                f"Prosthetic model not found at:\n{prostheticModelPath}\n\n"
                "Please ensure the elbow.stl file is in the correct location."
            )
            return
        
        try:
            logging.info(f"Attempting to load model from: {prostheticModelPath}")
            modelNode = slicer.util.loadModel(prostheticModelPath)
            if modelNode:
                # Rename for clarity in the scene
                modelNode.SetName("Prosthetic Elbow")
                # Set color to green
                displayNode = modelNode.GetDisplayNode()
                if displayNode:
                    displayNode.SetColor(0, 1, 0)  # Green: R=0, G=1, B=0
                logging.info(f"Prosthetic model loaded successfully: {modelNode.GetName()}")
                return True
            else:
                logging.error("Failed to load the prosthetic model (elbow.stl) - loadModel returned None")
                slicer.util.errorDisplay("Failed to load the prosthetic model (elbow.stl).")
                return False
        except Exception as e:
            logging.error(f"Exception loading prosthetic model: {str(e)}", exc_info=True)
            slicer.util.errorDisplay(f"Error loading prosthetic model:\n{str(e)}")
            return False

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()
        # 1. Switch to 100% 3D View
        layoutManager = slicer.app.layoutManager()
        if layoutManager:
            layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOne3DView)
            
        # 2. Optional: Center the camera on your models
        threeDWidget = layoutManager.threeDWidget(0)
        threeDView = threeDWidget.threeDView()
        threeDView.resetFocalPoint()

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
    
    def _onArmMarkupsNodeChanged(self) -> None:
        """Called when arm markup node changes."""
        armNode = self.ui.armMarkupsWidget.currentNode()
        if armNode:
            # Set the limit on the data node itself
            armNode.SetMaximumNumberOfControlPoints(3)
            self.addObserver(armNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._checkCanApply()
    
    def _onProstheticMarkupsNodeChanged(self) -> None:
        """Called when prosthetic markup node changes."""
        prosNode = self.ui.prostheticMarkupsWidget.currentNode()
        if prosNode:
            # Set the limit on the data node itself
            prosNode.SetMaximumNumberOfControlPoints(3)
            self.addObserver(prosNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        # Logic: Only enable if we have an input file AND both sets of landmarks have 3 points
        armReady = self.ui.armMarkupsWidget.currentNode() and self.ui.armMarkupsWidget.currentNode().GetNumberOfControlPoints() >= 3
        prosReady = self.ui.prostheticMarkupsWidget.currentNode() and self.ui.prostheticMarkupsWidget.currentNode().GetNumberOfControlPoints() >= 3
        
        if self._parameterNode and self._parameterNode.inputFilePath and armReady and prosReady:
            self.ui.applyButton.text = _("Apply Landmark Registration")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.text = _("Place 3 points on each model")
            self.ui.applyButton.enabled = False

    def onApplyButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
        # Get the actual model node currently named "Patient Scan"
        patientModel = slicer.util.getNode("Patient Scan")
        armNode = self.ui.armMarkupsWidget.currentNode()
        prosNode = self.ui.prostheticMarkupsWidget.currentNode()
        
        if patientModel and armNode and prosNode:
            self.logic.process(patientModel, armNode, prosNode)
        else:
            slicer.util.errorDisplay("Make sure 'Patient Scan' is loaded and 3 points are placed.")

    def onBrowseInputFile(self) -> None:
        """Open file dialog to select STL or OBJ file."""
        fileName = qt.QFileDialog.getOpenFileName(
            None,
            "Select STL or OBJ file",
            "",
            "Model files (*.stl *.obj);;All files (*)"
        )
        if fileName:
            # Ensure parameter node is initialized
            if not self._parameterNode:
                self.setParameterNode(self.logic.getParameterNode())
            
            # Clear previous markup nodes if a new file is selected
            armNode = self.ui.armMarkupsWidget.currentNode()
            if armNode:
                slicer.mrmlScene.RemoveNode(armNode)
            prosNode = self.ui.prostheticMarkupsWidget.currentNode()
            if prosNode:
                slicer.mrmlScene.RemoveNode(prosNode)
            
            self.ui.inputFilePathEdit.setText(fileName)
            self._parameterNode.inputFilePath = fileName
            
            # Clear any previous patient models from the scene
            for node in slicer.mrmlScene.GetNodesByName("Patient Scan"):
                slicer.mrmlScene.RemoveNode(node)
            
            # Load the prosthetic model only when an input file is selected
            self.loadProstheticModel()
            
            # Load and display the patient model in the 3D scene
            try:
                modelNode = slicer.util.loadModel(fileName)
                if modelNode:
                    # Set color to red
                    displayNode = modelNode.GetDisplayNode()
                    if displayNode:
                        displayNode.SetColor(1, 0, 0)  # Red: R=1, G=0, B=0
                    modelNode.SetName("Patient Scan")
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

    def process(self, patientModelNode, armLandmarks, prostheticLandmarks) -> None:
        """
        Calculates and applies the transformation matrix.
        """
        if not patientModelNode or not armLandmarks or not prostheticLandmarks:
            logging.warning("Missing required nodes for alignment.")
            return

        # Extract Coordinates (1->1, 2->2, 3->3)
        sourcePoints = vtk.vtkPoints() # Red (Patient)
        targetPoints = vtk.vtkPoints() # Green (Prosthetic)
        
        for i in range(3):
            p_source = [0,0,0]
            p_target = [0,0,0]
            armLandmarks.GetNthControlPointPosition(i, p_source)
            prostheticLandmarks.GetNthControlPointPosition(i, p_target)
            sourcePoints.InsertNextPoint(p_source)
            targetPoints.InsertNextPoint(p_target)

        landmarkTransform = vtk.vtkLandmarkTransform()
        landmarkTransform.SetSourceLandmarks(sourcePoints)
        landmarkTransform.SetTargetLandmarks(targetPoints)
        landmarkTransform.SetModeToRigidBody() # Only Rotate and Translate (no stretching)
        landmarkTransform.Update()

        transformNode = slicer.mrmlScene.GetFirstNodeByName("AlignmentTransform")
        if not transformNode:
            transformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", "AlignmentTransform")
        
        transformNode.SetAndObserveMatrixTransformToParent(landmarkTransform.GetMatrix())
        
        # 4. Snap the Patient Scan to this Transform
        patientModelNode.SetAndObserveTransformNodeID(transformNode.GetID())
        
        # 5. Force UI to refresh the 3D view
        slicer.util.resetThreeDViews()
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

        # import SampleData
        import tempfile

        # registerSampleData()
        # inputVolume = SampleData.downloadSample("PopScanner1")
        # self.delayDisplay("Loaded test data set")

        # # inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        # self.assertEqual(inputScalarRange[0], 0)
        # self.assertEqual(inputScalarRange[1], 695)

        # # Save input volume as a temporary STL file for testing file path input
        # tempDir = tempfile.gettempdir()
        # testFilePath = os.path.join(tempDir, "test_input.stl")
        # # Note: In production, you would convert the volume to a model and save as STL
        # # For this test, we'll use the volume directly via slicer's save function
        # slicer.util.saveNode(inputVolume, testFilePath)

        # outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        # threshold = 100

        # # Test the module logic

        # logic = PopScannerLogic()

        # # Test algorithm with non-inverted threshold
        # logic.process(testFilePath, outputVolume, threshold, True)
        # outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        # self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        # self.assertEqual(outputScalarRange[1], threshold)

        # # Test algorithm with inverted threshold
        # logic.process(testFilePath, outputVolume, threshold, False)
        # outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        # self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        # self.assertEqual(outputScalarRange[1], inputScalarRange[1])

        # # Clean up temporary file
        # if os.path.exists(testFilePath):
        #     os.remove(testFilePath)

        self.delayDisplay("Test passed")
