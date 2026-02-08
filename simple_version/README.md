# Vision Based Mobile Robot

This project is a Raspberry Pi 4 based mobile robot with manual and vision-based driving modes.

## Files
- manual.py : Keyboard controlled driving
- robot.py : Camera based autonomous driving

## Hardware
- Raspberry Pi 4
- L298N motor driver
- 4 DC motors
- Pi Camera
- 5V / 3A power bank (Raspberry Pi)
- Li-ion battery (motors)

## Power
Raspberry Pi and motors are powered separately.  
Grounds are connected together.

## Wiring
ENA  -> GPIO18  
IN1  -> GPIO17  
IN2  -> GPIO27  
ENB  -> GPIO19  
IN3  -> GPIO22  
IN4  -> GPIO23  

## Virtual Environment
Vision code requires a virtual environment.

If the ONNX or .pt model does not run correctly, try activating your Python virtual environment:

source ~/venv/pose/bin/activate


## Run
Manual mode:

python3 manual.py

Vision mode:

python3 vision.py

## Notes
- Vision mode starts only after user input.
- ONNX model file is not included. Set your own model path.
