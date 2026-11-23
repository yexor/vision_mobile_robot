import socket, time
from collections import deque
import RPi.GPIO as GPIO

# ==== PIN ====
ENA, ENB, IN1, IN2, IN3, IN4 = 18, 19, 17, 27, 22, 23
LEFT_REVERSED = True
PWM_FREQ, SPEED, TURN, BACK, KICK, KICK_MS = 1000, 30, 25, 30, 50, 0.08

# ÖN SENSÖR
TRIG_ON  = 25
ECHO_ON  = 24

# ARKA SENSÖR 
TRIG_ARK = 26
ECHO_ARK = 20

# ==== GÜVENLİK AYARLARI ====
MESAFE_ESIK_CM   = 30   # Bu değerin altına düşünce o yön kilitlenir
MEDYAN_PENCERE   = 5    # Son kaç ölçümün medyanı alınsın
ARDISIK_ONAY     = 3    # Kaç üst üste ölçüm eşiğin altında olursa gerçekten kilitle

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for p in [ENA, ENB, IN1, IN2, IN3, IN4]:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

for p in [TRIG_ON, TRIG_ARK]:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, False)

for p in [ECHO_ON, ECHO_ARK]:
    GPIO.setup(p, GPIO.IN)

pwmA = GPIO.PWM(ENA, PWM_FREQ); pwmB = GPIO.PWM(ENB, PWM_FREQ)
pwmA.start(0); pwmB.start(0)

# ==== MOTOR FONKSİYONLARI ====
def set_left(fwd):
    a, b = (1, 0) if fwd else (0, 1)
    if LEFT_REVERSED: a, b = b, a
    GPIO.output(IN1, a); GPIO.output(IN2, b)

def set_right(fwd):
    a, b = (1, 0) if fwd else (0, 1)
    GPIO.output(IN3, a); GPIO.output(IN4, b)

def pwm_apply(ld, rd):
    pwmA.ChangeDutyCycle(max(ld, KICK)); pwmB.ChangeDutyCycle(max(rd, KICK))
    time.sleep(KICK_MS)
    pwmA.ChangeDutyCycle(ld); pwmB.ChangeDutyCycle(rd)

def coast():
    pwmA.ChangeDutyCycle(0); pwmB.ChangeDutyCycle(0)
    GPIO.output(IN1, 0); GPIO.output(IN2, 0)
    GPIO.output(IN3, 0); GPIO.output(IN4, 0)

def drive_forward():  set_left(True);  set_right(True);  pwm_apply(SPEED, SPEED)
def drive_backward(): set_left(False); set_right(False); pwm_apply(BACK,  BACK)
def pivot_left():     set_left(False); set_right(True);  pwm_apply(TURN,  TURN)
def pivot_right():    set_left(True);  set_right(False); pwm_apply(TURN,  TURN)

# ==== MESAFE OKUMA FONKSİYONU ====
def _ham_mesafe(trig, echo):
    """Tek bir ham HC-SR04 ölçümü yapar. Zaman aşımında -1 döner."""
    GPIO.output(trig, False)
    time.sleep(0.000002)
    GPIO.output(trig, True)
    time.sleep(0.00001)
    GPIO.output(trig, False)

    timeout = time.perf_counter() + 0.03
    while GPIO.input(echo) == 0:
        if time.perf_counter() > timeout:
            return -1
    pulse_start = time.perf_counter()

    timeout = pulse_start + 0.03
    while GPIO.input(echo) == 1:
        if time.perf_counter() > timeout:
            return -1
    pulse_end = time.perf_counter()

    return (pulse_end - pulse_start) * 17150.0

# ==== MEDİYAN FİLTRELİ MESAFE OKUYUCU SINIFI ====
class MesafeSensor:
    """
    Medyan filtresi + ardışık onay sayacı ile güvenli mesafe okuyucu.

    Mantık:
      - Son MEDYAN_PENCERE adet geçerli ölçümün medyanı alınır.
        Bu sayede 999 cm gibi spike değerleri tamamen görmezden gelinir.
      - Medyan değer MESAFE_ESIK_CM'nin altına düşerse bir sayaç artar.
      - Sayaç ARDISIK_ONAY değerine ulaşırsa sensör "engel var" olarak işaretlenir.
      - Medyan eşiğin üstüne çıktığı anda sayaç sıfırlanır ve engel kalkar.
    """
    def __init__(self, trig, echo, isim):
        self.trig  = trig
        self.echo  = echo
        self.isim  = isim
        self.tampon         = deque(maxlen=MEDYAN_PENCERE)
        self.alti_sayac     = 0
        self.engel_var      = False

    def guncelle(self):
        """Bir ölçüm yap, filtreyi güncelle, engel durumunu belirle."""
        ham = _ham_mesafe(self.trig, self.echo)

        # Geçersiz (-1) veya fiziksel olarak imkânsız değerleri filtrele
        if ham > 0:
            self.tampon.append(ham)

        # Henüz yeterli ölçüm birikmemişse karar verme
        if len(self.tampon) < MEDYAN_PENCERE:
            return

        # Medyan hesapla (spike'ları bastırır)
        medyan = sorted(self.tampon)[len(self.tampon) // 2]

        if medyan < MESAFE_ESIK_CM:
            self.alti_sayac += 1
        else:
            # Eşiğin üstüne çıktı → hem sayacı hem engel bayrağını sıfırla
            self.alti_sayac = 0
            self.engel_var  = False

        # Yeterince ardışık düşük ölçüm geldi → engeli onayla
        if self.alti_sayac >= ARDISIK_ONAY:
            self.engel_var = True

    def son_medyan(self):
        """Mevcut tampondaki medyanı döndürür. Yeterli veri yoksa -1."""
        if len(self.tampon) < MEDYAN_PENCERE:
            return -1
        return sorted(self.tampon)[len(self.tampon) // 2]


on_sensor  = MesafeSensor(TRIG_ON,  ECHO_ON,  "ON")
arka_sensor = MesafeSensor(TRIG_ARK, ECHO_ARK, "ARKA")

# ==== KOMUT FİLTRELEME: Engel varsa tehlikeli yönü engelle ====
def guvenli_komut_uygula(komut):
    """
    Engel durumuna göre komutu uygular veya durdurur.

    Kural:
      - Önde engel varsa SADECE BACK komutu çalışır (geri çekil veya dur).
      - Arkada engel varsa SADECE FWD, LEFT, RIGHT çalışır (ileri git veya dön).
      - İki yanda birden engel varsa sadece STOP.
    """
    onde  = on_sensor.engel_var
    arkada = arka_sensor.engel_var

    if onde and arkada:
        # Her iki tarafta da engel → hiçbir yöne gitme
        coast()
        print(f"\r[GÜVENLIK] Çift Engel! DUR                 ", end="")
        return

    if onde and komut == "FWD":
        coast()
        print(f"\r[GÜVENLIK] Önde Engel! İleri KİLİTLİ      ", end="")
        return

    if onde and komut in ("LEFT", "RIGHT"):
        # Dönmeye izin ver, araç yerden oynamak yerine sadece döner
        pass

    if arkada and komut == "BACK":
        coast()
        print(f"\r[GÜVENLIK] Arkada Engel! Geri KİLİTLİ     ", end="")
        return

    # Engel yok veya güvenli komut → normal çalış
    if   komut == "FWD":   drive_forward()
    elif komut == "BACK":  drive_backward()
    elif komut == "LEFT":  pivot_left()
    elif komut == "RIGHT": pivot_right()
    elif komut == "STOP":  coast()

# ==== SOKET HABERLEŞMESİ ====
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 5005))
server.listen(1)

print("\n[HAZIR] Raspberry Pi komut bekliyor...")
print(f"[AYAR] Eşik: {MESAFE_ESIK_CM} cm | Medyan pencere: {MEDYAN_PENCERE} | Ardışık onay: {ARDISIK_ONAY}")

try:
    while True:
        conn, addr = server.accept()
        print(f"\n[BAGLANDI] Laptop baglandi: {addr}")
        conn.settimeout(0.5)
        try:
            while True:
                # Her döngüde her iki sensörü de güncelle
                on_sensor.guncelle()
                arka_sensor.guncelle()

                try:
                    data = conn.recv(1024).decode('utf-8').strip()
                    if not data:
                        break

                    son_komut = data.split('\n')[-1].strip()

                    # Komutu yazdır (bilgi amaçlı)
                    komut_adi = {"FWD": "ILERI", "BACK": "GERI", "LEFT": "SOLA",
                                 "RIGHT": "SAGA", "STOP": "DUR"}.get(son_komut, son_komut)
                    print(f"\rKomut: {komut_adi} | Ön: {on_sensor.son_medyan():.1f}cm | "
                          f"Arka: {arka_sensor.son_medyan():.1f}cm   ", end="")

                    # Güvenlik katmanından geçirerek komutu uygula
                    guvenli_komut_uygula(son_komut)

                    # Laptopa her iki sensörün son medyanını gönder
                    # Format: "on_mesafe,arka_mesafe\n"  (laptop_merkez.py parse edebilir)
                    dist_on   = on_sensor.son_medyan()
                    dist_arka = arka_sensor.son_medyan()
                    conn.sendall(f"{dist_on:.1f},{dist_arka:.1f}\n".encode('utf-8'))

                except socket.timeout:
                    coast()
                    print("\r[BEKLEMEDE] Yeni hareket bekleniyor...              ", end="")

        except Exception as e:
            coast()
            print(f"\n[HATA] {e}")
        finally:
            conn.close()
            coast()
            print("\n[KOPTU] Yeni baglanti bekleniyor...")

except KeyboardInterrupt:
    pass
finally:
    coast()
    GPIO.cleanup()
    server.close()
