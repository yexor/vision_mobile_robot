import time
import sys
import select
import termios
import tty

import cv2
import numpy as np
import onnxruntime as ort
from picamera2 import Picamera2
import RPi.GPIO as GPIO

#gpio
ENA, ENB = 18, 19
IN1, IN2 = 17, 27
IN3, IN4 = 22, 23

GPIO.setmode(GPIO.BCM)
GPIO.setup([ENA, ENB, IN1, IN2, IN3, IN4], GPIO.OUT)

pwmA = GPIO.PWM(ENA, 1000)
pwmB = GPIO.PWM(ENB, 1000)
pwmA.start(0)
pwmB.start(0)

def ileri(hiz):
    GPIO.output(IN1, 1)
    GPIO.output(IN2, 0)
    GPIO.output(IN3, 1)
    GPIO.output(IN4, 0)
    pwmA.ChangeDutyCycle(hiz)
    pwmB.ChangeDutyCycle(hiz)

def sola_don():
    GPIO.output(IN1, 0)
    GPIO.output(IN2, 1)
    GPIO.output(IN3, 1)
    GPIO.output(IN4, 0)
    pwmA.ChangeDutyCycle(30)
    pwmB.ChangeDutyCycle(30)

def saga_don():
    GPIO.output(IN1, 1)
    GPIO.output(IN2, 0)
    GPIO.output(IN3, 0)
    GPIO.output(IN4, 1)
    pwmA.ChangeDutyCycle(30)
    pwmB.ChangeDutyCycle(30)

def dur():
    pwmA.ChangeDutyCycle(0)
    pwmB.ChangeDutyCycle(0)

#picamera2
camera = Picamera2()
camera.configure(
    camera.create_preview_configuration(
        main={"size": (640, 480), "format": "RGB888"}
    )
)
camera.start()
time.sleep(1)

#onnx
session = ort.InferenceSession("best.onnx")
input_name = session.get_inputs()[0].name
output_name = session.get_outputs()[0].name

def read_key():
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:
        return sys.stdin.read(1)
    return None

old_settings = termios.tcgetattr(sys.stdin)
tty.setcbreak(sys.stdin.fileno())

#state
armed = False           
emergency_stop = False 

print("\nvision mode")
print("enter : sistemi baslat")
print("space : acil stop / devam")
print("q : Cikis")

try:
    while True:
        key = read_key()

        
        if key in ['q', 'Q']:
            break

       
        if key == '\n' and not armed:
            armed = True
            print("sistem aktif")
            continue

        
        if key == ' ' and armed:
            emergency_stop = not emergency_stop
            dur()
            print("acil stop" if emergency_stop else "devam")
            continue
        
        if not armed or emergency_stop:
            dur()
            time.sleep(0.1)
            continue
            #vision
        frame = camera.capture_array()

        img = cv2.resize(frame, (320, 320))
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)

        output = session.run([output_name], {input_name: img})[0]

        if len(output) > 0:
            x_center = output[0][0]#!!

            if x_center < 0.4:
                sola_don()
            elif x_center > 0.6:
                saga_don()
            else:
                ileri(40)
        else:
            dur()

        time.sleep(0.05)

finally:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    dur()
    pwmA.stop()
    pwmB.stop()
    GPIO.cleanup()
