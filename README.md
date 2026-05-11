# ERC-UCU-Drone-2026


## Erso Drone Ground Station Setup Guide

This document provides instructions for configuring the network connectivity and executing the ground station web application on the Raspberry Pi 5. The system operates in two distinct network modes: Hotspot Mode (field operations via an independent Access Point) and Local Network Mode (development via a shared Wi-Fi router).

## Prerequisites

Ensure the virtual environment is initialized and all required dependencies are installed. Execute the following commands within the project root directory:

```bash
source .venv/bin/activate
pip install fastapi uvicorn opencv-python-headless jinja2
```

## Mode 1: Hotspot Mode (Field Operations)

In this mode, the Raspberry Pi broadcasts its own wireless network.

### 1. Initialize the Access Point
Execute the command below to create and start the hotspot. Note that if the Raspberry Pi is currently connected to a local router via Wi-Fi, this command will terminate the active SSH session as the wireless interface switches to broadcast mode.

```bash
sudo nmcli device wifi hotspot con-name erso_drone ssid erso_drone password 12345678
```

### 2. Establish Connection
1. Connect the host computer to the `erso_drone` wireless network using the password `12345678`.
2. Establish a new SSH connection using the default static IP address assigned to the access point (`10.42.0.1`):

```bash
ssh username@10.42.0.1
```
*(Replace `username` with the appropriate Raspberry Pi user account)*

### 3. Execute the Server
Activate the virtual environment and launch the application server:

```bash
cd ~/drone_autonomy_project
source .venv/bin/activate
python -m src.web_ui.server
```

Access the live video stream by navigating to `http://10.42.0.1:8000` in a web browser.

### 4. Terminate the Access Point
To stop the broadcast and permit the Raspberry Pi to reconnect to known local networks, execute:

```bash
sudo nmcli connection down erso_drone
```

## Mode 2: Local Network Mode (Home Wi-Fi)

In this mode, the Raspberry Pi and the host computer communicate over a shared local wireless router.

### 1. Connect to the Local Network
If the device does not automatically reconnect after terminating the hotspot, establish the connection manually:

```bash
sudo nmcli device wifi connect "Local_Network_SSID" password "Local_Network_Password"
```

### 2. Determine the Assigned IP Address
Retrieve the local IP address assigned by the router:

```bash
hostname -I
```

### 3. Execute the Server
Establish an SSH session using the retrieved IP address (e.g., `192.168.1.50`):

```bash
ssh username@192.168.1.50
```

Launch the application:

```bash
source .venv/bin/activate
python -m src.web_ui.server
```

Access the interface via `http://<Raspberry_Pi_IP>:8000` in a web browser.

## Network Profile Management

NetworkManager persists configured connection profiles. Use the commands below to switch between operational modes efficiently:

* **Enable Field Mode (Hotspot):**
  ```bash
  sudo nmcli connection up erso_drone
  ```
* **Enable Local Network Mode (Router):**
  ```bash
  sudo nmcli connection down erso_drone
  ```