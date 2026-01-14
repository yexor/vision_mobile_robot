import sys
import termios
import tty
import time
import RPi.GPIO as GPIO

#pin
ENA, ENB = 18, 19
IN1, IN2 = 17, 27
IN3, IN4 = 22, 23

GPIO.setmode(GPIO.BCM)
GPIO.setup([ENA, ENB, IN1, IN2, IN3, IN4], GPIO.OUT)

pwmA = GPIO.PWM(ENA, 1000)
pwmB = GPIO.PWM(ENB, 1000)
pwmA.start(0)
pwmB.start(0)

#motorgpio
def ileri():
    GPIO.output(IN1, 1)
    GPIO.output(IN2, 0)
    GPIO.output(IN3, 1)
    GPIO.output(IN4, 0)
    pwmA.ChangeDutyCycle(40)
    pwmB.ChangeDutyCycle(40)

def geri():
    GPIO.output(IN1, 0)
    GPIO.output(IN2, 1)
    GPIO.output(IN3, 0)
    GPIO.output(IN4, 1)
    pwmA.ChangeDutyCycle(35)
    pwmB.ChangeDutyCycle(35)

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

print("""
Manuel surus modu
  --------------
W : ileri
S : geri
A : Sola don
D : Saga don
SPACE : dur
Q : cikis
""")

old_settings = termios.tcgetattr(sys.stdin)
tty.setcbreak(sys.stdin.fileno())

try:
    while True:
        key = sys.stdin.read(1)

        if key.lower() == 'w':
            ileri()
        elif key.lower() == 's':
            geri()
        elif key.lower() == 'a':
            sola_don()
        elif key.lower() == 'd':
            saga_don()
        elif key == ' ':
            dur()
        elif key.lower() == 'q':
            break

        time.sleep(0.05)

finally:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    dur()
    pwmA.stop()
    pwmB.stop()
    GPIO.cleanup()
