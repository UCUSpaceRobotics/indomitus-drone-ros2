# ERC Droning Sub-Task: Autonomous Quadcopter Technical Specification

**Author:** Marko Pasternak

## 1. System Architecture & Hardware Stack

### 1.1 Frame & Propulsion
* **Chassis:** F450 quadcopter frame equipped with landing gears.
* **Custom Mounts:** Custom-manufactured holder integrated into the frame to securely mount the computer vision camera, optical flow sensor, and LiPo battery.
* **Motors:** DJI 2212 920KV brushless motors.
* **Propellers:** 1045R (10x4.5) propellers.
* **Power Source:** 4S LiPo battery pack.

### 1.2 Computing & Control
* **Low-Level Flight Controller:** Pixhawk 6C. Manages real-time flight dynamics, motor PWM output, and low-level stabilization.
* **Companion Computer:** Raspberry Pi 5. Serves as the central processing unit for computer vision, high-level autonomous navigation, and state management.

### 1.3 Sensor Suite
* **Vision:** Downward-facing wide-angle computer vision camera featuring a 120-degree field of view. It is directly connected to the Raspberry Pi to transmit real-time video feed for target and probe detection.
* **Odometry:** Physical optical flow sensor used for stable, GPS-denied autonomous hovering and flight.

## 2. Software Architecture & Communication

### 2.1 Communication Protocol
* The Raspberry Pi and Pixhawk communicate via a hardwired **UART connection**.
* Messages are exchanged using the **MAVLink protocol**.

### 2.2 Control Logic
* The high-level software on the Raspberry Pi is structured as a **State Machine**.
* Python is utilized as the primary language, employing the `pymavlink` library to construct and transmit command packets to the flight controller.

### 2.3 Sensor Fusion
* State estimation and sensor fusion are handled entirely by the **Pixhawk firmware**. The built-in Extended Kalman Filter (EKF) natively merges optical flow and IMU data without requiring manual filter setup or external configuration on the companion computer.

## 3. ERC Droning Sub-Task Mission Parameters
Based on the ERC 2026 rulebook, the drone must accomplish the following objectives within a 10x10x4m enclosed cage.

### 3.1 Preflight Safety Checks
Before the mission, the system must pass strict safety validations:
* Real-time telemetry and video feedback to the operator.
* Demonstrated capability for manual remote-control override.
* Automatic mid-air stability holding.
* Initialization of automatic landing on demand.
* Configured fail-safe mechanisms for loss of RC/ground station connection, battery loss, or positioning system glitches.
* Configured polygon inclusion geofencing for the competition area.

### 3.2 Mission Execution
* **Time constraints:** 15 minutes for preparation, 30 minutes for task execution.
* **Flight Mode:** The mission must be performed strictly in automated mode. Manual interventions incur penalties.
* **Core Objective:** Execute 3 sequential flights. Each flight consists of an autonomous lift-off from the central spot (1x1m square, ArUco ID 101), locating a randomized landing target (0.5m radius disc, ArUco ID 102) positioned within a 3-meter radius, and performing a precision landing.

### 3.3 Probe Detection & Additional Scoring
* **Probe Detection:** Identify and estimate the grid position of 3 separate probes scattered within the 3-meter radius. The arena is divided into 1x1m virtual sectors (e.g., A2, D1), and the system must output the sector ID for each detected probe.
* **Custom Landing Platform:** An optional custom landing platform (max 0.5m radius disc) can be attached to the rover. Successfully landing on this platform yields additional points.
* **Software Requirement Note:** The ERC rules stipulate that image processing, object detection, and high-level decision-making must be implemented using MATLAB/Simulink. Integration between the existing Python/pymavlink state machine and MATLAB toolboxes will be necessary to meet this specific compliance rule.
