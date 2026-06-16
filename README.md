# Dosify
### Smart AI-Powered Medication Organizer

Dosify combines Artificial Intelligence, Computer Vision, and Robotics to automate medication management and improve accessibility for people with disabilities. The system reads prescriptions, generates medication schedules, and uses a robotic arm to sort pills into the correct organizer compartments.

## Team Members
- Belard
- Alisher
- Jannah

## Project Overview

Managing medications can be challenging, especially for individuals with visual impairments, motor disabilities, or complex medication schedules. Dosify addresses this challenge by automating the entire medication preparation process.

The user places a prescription beneath the camera, the system extracts medication information using AI-powered OCR, generates a personalized schedule, and instructs a robotic arm to organize the correct pills into designated compartments.

Our primary goal during prototype development was to validate the most critical assumption: **can the robotic arm reliably pick and place pills?** By focusing on robotic manipulation first, we ensured the foundation of the system was practical before expanding the AI and scheduling components.

## Key Features

- Prescription image capture
- AI-powered OCR using Google Gemini
- Personalized medication schedule generation
- Robotic pill sorting and placement
- Verification before dispensing

## Pipeline

```
Prescription Upload
        ↓
OCR Extraction (Gemini Vision)
        ↓
Schedule Generation
        ↓
Robotic Sorting
        ↓
Verification
        ↓
User Delivery
```

## Project Structure

```
dosify/
│
├── assets/
│   ├── cad_models/
│   └── process_images/
│
├── config/
│   └── robot_config.yaml
│
├── launch/
│   └── dosify.launch
│
├── ocr/
│   ├── test_images/
│   ├── ocr_processor.py
│   └── output.json
│
├── scripts/
│   ├── dispense_node.py
│   └── robot_control_node.py
│
└── src/dosify/
├── package.xml
├── setup.py
├── CMakeLists.txt
└── README.md
```

##  Technologies Used

**Artificial Intelligence**
- Google Gemini Vision
- OCR-based prescription extraction

**Robotics**
- Robotic arm manipulation
- Vacuum gripper pickup system
- Automated pill dispensing

**Software**
- Python
- ROS (Robot Operating System)
- YAML configuration

**Computer Vision**
- Prescription image processing
- Medication identification
- Workspace monitoring

## Results

**OCR Extraction** — successfully extracted:
- Medication names
- Dosage information
- Frequency instructions
- Schedule-related information

**Robotic Manipulation** — successfully demonstrated:
- Pill detection
- Vacuum-based pickup
- Accurate placement

## Impact

Dosify is designed to support:
- People with visual impairments
- Elderly users
- Individuals with motor disabilities
- Patients managing multiple medications
- Caregivers seeking safer medication organization

By reducing human error and increasing independence, Dosify has the potential to improve both medication adherence and quality of life.

## Future Improvements

- Mobile application integration
- Voice-assisted interaction
- Medication reminders
- Multi-user support
- Advanced pill recognition using computer vision
