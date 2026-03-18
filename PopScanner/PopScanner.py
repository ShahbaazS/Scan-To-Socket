import logging
import os
from typing import Annotated

import vtk
import qt
import numpy as np
import math

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

        self.distanceSpinBox = qt.QDoubleSpinBox()
        self.distanceSpinBox.setRange(0.0, 500.0)
        self.distanceSpinBox.setValue(150.0) # Default extension distance
        self.distanceSpinBox.setSuffix(" mm")
        self.distanceSpinBox.setToolTip("Distance from the bottom of the stump to the elbow joint.")
        
        distanceLayout = qt.QHBoxLayout()
        distanceLayout.addWidget(qt.QLabel("Extension Distance:"))
        distanceLayout.addWidget(self.distanceSpinBox)
        
        # Insert right above the Apply button
        applyButtonLayout = self.ui.applyButton.parent().layout()
        applyButtonLayout.insertLayout(applyButtonLayout.count() - 1, distanceLayout)

        self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.inputFileBrowseButton.connect("clicked(bool)", self.onBrowseInputFile)
        
        self.ui.armMarkupsWidget.connect("markupsNodeChanged()", self._onArmMarkupsNodeChanged)
        self.ui.armMarkupsWidget.connect("activeMarkupsNodeChanged(vtkMRMLNode*)", self._onArmMarkupsNodeChanged)

        self.initializeParameterNode()
        self.loadProstheticModel()

    def loadProstheticModel(self) -> None:
        """Load the prosthetic elbow model at startup."""
        # Get the path relative to this module
        
        try:
            if slicer.util.getNode("Prosthetic Elbow"):
                return  # Exit early, don't load again
        except:
            pass
        
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
        armNode = self.ui.armMarkupsWidget.currentNode()
        if armNode:
            armNode.SetMaximumNumberOfControlPoints(3)
            self.addObserver(armNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._checkCanApply()
    
    def _onProstheticMarkupsNodeChanged(self) -> None:
        # ignore
        pass

    def _checkCanApply(self, caller=None, event=None) -> None:
        # Logic: Only enable if we have an input file AND the patient arm has exactly 3 points
        armReady = self.ui.armMarkupsWidget.currentNode() and self.ui.armMarkupsWidget.currentNode().GetNumberOfControlPoints() == 3
        
        if self._parameterNode and self._parameterNode.inputFilePath and armReady:
            self.ui.applyButton.text = _("Generate Prosthetic Socket")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.text = _("Place 3 points on Patient Arm")
            self.ui.applyButton.enabled = False

    def onApplyButton(self) -> None:
        slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
        patientModel = slicer.util.getNode("Patient Scan")
        prostheticModel = slicer.util.getNode("Prosthetic Elbow")
        armNode = self.ui.armMarkupsWidget.currentNode()
        
        if patientModel and prostheticModel and armNode:
            # Pass the user-inputted distance into the logic
            target_distance = self.distanceSpinBox.value
            self.logic.process(patientModel, armNode, prostheticModel, target_distance)
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

    def process(self, patientModelNode, armLandmarks, elbowModelNode, offset_distance) -> None:

        if armLandmarks.GetNumberOfControlPoints() < 3:
            logging.error("Please place exactly 3 points: Shoulder, Stump Center, Stump Edge.")
            return

        # Extract the 3 Points
        p0_shoulder = np.zeros(3)
        p1_stump_center = np.zeros(3)
        p2_stump_edge = np.zeros(3)

        armLandmarks.GetNthControlPointPosition(0, p0_shoulder)
        armLandmarks.GetNthControlPointPosition(1, p1_stump_center)
        armLandmarks.GetNthControlPointPosition(2, p2_stump_edge)

        # Calculate Trajectory Vector (Z-Axis)
        direction_vector = p1_stump_center - p0_shoulder
        norm = np.linalg.norm(direction_vector)
        if norm == 0:
            logging.error("Shoulder and stump center points overlap.")
            return
        direction_vector = direction_vector / norm # Normalized Z-axis

        # Calculate Orthogonal Scale (Point-to-Line Distance)
        center_to_edge_vector = p2_stump_edge - p1_stump_center
        cross_product = np.cross(center_to_edge_vector, direction_vector)
        stump_radius = np.linalg.norm(cross_product)
        
        # Set to exact radius of the top of the unscaled elbow.stl
        cad_elbow_radius = 25.0 
        scale_factor = stump_radius / cad_elbow_radius

        # Calculate Target Position for the Elbow
        # We move exactly 'offset_distance' mm down the trajectory vector
        elbow_target_pos = p1_stump_center + (direction_vector * offset_distance)

        # Build Orthonormal Rotation Matrix
        z_axis = direction_vector
        y_axis = np.cross(z_axis, center_to_edge_vector)
        norm_y = np.linalg.norm(y_axis)
        if norm_y > 0:
            y_axis = y_axis / norm_y
        else:
            y_axis = np.array([0.0, 1.0, 0.0]) # Fallback if collinear
            
        x_axis = np.cross(y_axis, z_axis)
        x_axis = x_axis / np.linalg.norm(x_axis)

        rotation_matrix = vtk.vtkMatrix4x4()
        for i in range(3):
            rotation_matrix.SetElement(i, 0, x_axis[i])
            rotation_matrix.SetElement(i, 1, y_axis[i])
            rotation_matrix.SetElement(i, 2, z_axis[i])

        # Apply Transforms (Translate -> Rotate -> Scale)
        transform = vtk.vtkTransform()
        transform.Translate(elbow_target_pos)
        transform.Concatenate(rotation_matrix)
        transform.RotateY(180)
        transform.Scale(scale_factor, scale_factor, scale_factor)

        transformNode = slicer.mrmlScene.GetFirstNodeByName("MasterElbowTransform")
        if not transformNode:
            transformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", "MasterElbowTransform")
            
        transformNode.SetMatrixTransformToParent(transform.GetMatrix())
        elbowModelNode.SetAndObserveTransformNodeID(transformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(elbowModelNode)
        
        logging.info(f"Elbow aligned! Scale factor applied: {scale_factor:.2f}x")
        
        # Proceed to Boolean Hollowing
        self.generate_prosthetic_socket(patientModelNode, elbowModelNode, p1_stump_center, elbow_target_pos, offset_distance, stump_radius)

    def generate_prosthetic_socket(self, patientModelNode, elbowModelNode, p1_stump_center, elbow_target_pos, offset_distance, stump_radius):

        logging.info("Generating bridging cylinder and executing Booleans...")

        # Generate the Bridging Cylinder
        overlap_top = 50.0    # Plunge 50mm deep into the patient's stump
        overlap_bottom = 15.0 # Plunge 15mm deep into the elbow CAD
        
        total_height = offset_distance + overlap_top + overlap_bottom

        cylinder = vtk.vtkCylinderSource()
        cylinder.SetRadius(stump_radius * 1.1) # 10% wider than the stump
        cylinder.SetHeight(total_height) 
        cylinder.SetResolution(50)
        cylinder.Update()

        # Orient and Position the Cylinder
        direction = elbow_target_pos - p1_stump_center
        direction = direction / np.linalg.norm(direction)

        default_axis = [0.0, 1.0, 0.0]
        rotation_axis = np.cross(default_axis, direction)
        rotation_axis = rotation_axis / np.linalg.norm(rotation_axis)
        angle_rad = math.acos(np.dot(default_axis, direction))
        angle_deg = math.degrees(angle_rad)

        # Calculate the new asymmetric center point
        top_point = p1_stump_center - (direction * overlap_top)
        bottom_point = elbow_target_pos + (direction * overlap_bottom)
        true_center = (top_point + bottom_point) / 2.0

        cylTransform = vtk.vtkTransform()
        cylTransform.Translate(true_center)
        cylTransform.RotateWXYZ(angle_deg, rotation_axis)

        transformFilter = vtk.vtkTransformPolyDataFilter()
        transformFilter.SetInputData(cylinder.GetOutput())
        transformFilter.SetTransform(cylTransform)
        transformFilter.Update()

        cylinderModelNode = slicer.modules.models.logic().AddModel(transformFilter.GetOutput())
        cylinderModelNode.SetName("Bridge Cylinder")

        # Execute Headless Booleans via Segmentations
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "SocketSegmentation")
        segNode.CreateDefaultDisplayNodes()
        
        slicer.modules.segmentations.logic().ImportModelToSegmentationNode(patientModelNode, segNode)
        slicer.modules.segmentations.logic().ImportModelToSegmentationNode(cylinderModelNode, segNode)
        slicer.modules.segmentations.logic().ImportModelToSegmentationNode(elbowModelNode, segNode)

        segmentation = segNode.GetSegmentation()
        patientVoidID = segmentation.GetNthSegmentID(0)
        cylinderID = segmentation.GetNthSegmentID(1)
        elbowID = segmentation.GetNthSegmentID(2)

        # Duplicate the Patient segment to create the outer Socket Blank
        segmentation.CopySegmentFromSegmentation(segmentation, patientVoidID)
        socketBlankID = segmentation.GetNthSegmentID(3)

        segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
        segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
        segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
        segmentEditorWidget.setSegmentationNode(segNode)

        # --- BOOLEAN OPERATIONS ---         
        # Patient Void: Expand by 3mm for the prosthetic liner tolerance
        segmentEditorNode.SetSelectedSegmentID(patientVoidID)
        segmentEditorWidget.setActiveEffectByName("Margin")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("MarginSizeMm", "3.0")
        effect.self().onApply()

        # Socket Blank: Expand by 8mm for structural wall thickness
        segmentEditorNode.SetSelectedSegmentID(socketBlankID)
        segmentEditorWidget.setActiveEffectByName("Margin")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("MarginSizeMm", "8.0")
        effect.self().onApply()

        # Fusion: Merge Cylinder and Elbow into the Socket Blank
        segmentEditorNode.SetSelectedSegmentID(socketBlankID)
        segmentEditorWidget.setActiveEffectByName("Logical operators")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("Operation", "UNION")
        effect.setParameter("ModifierSegmentID", cylinderID)
        effect.self().onApply()
        effect.setParameter("ModifierSegmentID", elbowID)
        effect.self().onApply()

        # Subtraction: Carve the expanded Patient Void out of the solid block
        segmentEditorNode.SetSelectedSegmentID(socketBlankID)
        segmentEditorWidget.setActiveEffectByName("Logical operators")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("Operation", "SUBTRACT")
        effect.setParameter("ModifierSegmentID", patientVoidID)
        effect.self().onApply()

        # Cleanup Scene
        patientModelNode.GetDisplayNode().SetVisibility(False)
        cylinderModelNode.GetDisplayNode().SetVisibility(False)
        elbowModelNode.GetDisplayNode().SetVisibility(False)
        slicer.mrmlScene.RemoveNode(segmentEditorNode)
        
        # Export final segmentation to a 3D Model Node
        slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segNode, slicer.mrmlScene.GetSubjectHierarchyNode().GetSceneItemID())
        
        logging.info("Socket generation complete.")
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
