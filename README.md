# Patient Specific Prosthetic Alignment Module

PopScanner is a 3D Slicer extension designed to align patient-specific arm scans with prosthetic elbow models. By using a 3-point landmark registration system, the module calculates the precise rotation and translation needed to fit a prosthetic to a patient's anatomy.

## Installation
1. Download [3D Slicer](https://download.slicer.org/), version 5.10 or higher is recommended.
2. Open **3D Slicer**.
3. Navigate to **Edit** -> **Application Settings** -> **Modules**.
4. Click **Add** and select the folder containing the `PopScanner` directory (where `PopScanner.py` is located).
5. Restart Slicer or search for **PopScanner** in the Module Selector under the **Prosthetics** category.

## How to Use
1. **Load Patient Scan**: Use the **Browse** button to select an STL or OBJ file of the patient's arm. The scan will appear in red.
2. **Place Arm Landmarks**:
   - Select the **Arm Landmarks** widget in the module panel.
   - Click the "Place" button and mark exactly **3 points** on the patient scan (e.g., Lateral Epicondyle, Medial Epicondyle, and Olecranon).
3. **Place Prosthetic Landmarks**:
   - Select the **Prosthetic Landmarks** widget.
   - Place **3 corresponding points** on the green prosthetic model. 
   - **Crucial:** You must place them in the **exact same order** as the arm points (e.g., Point 1 on both must be the Lateral Epicondyle).
4. **Align**: Click **Apply Landmark Registration**. The red patient scan will automatically "snap" to the green prosthetic based on your landmarks.
