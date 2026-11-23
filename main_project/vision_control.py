import cv2
import socket
from ultralytics import YOLO

# PI IP ADRESİ
PI_IP = "10.58.4.123" #(pi de terminalde hostname -I ile ip adresi buraya yazılacak)
PORT  = 5005

print("[BILGI] Robota baglanmaya calisiliyor...")
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    client.connect((PI_IP, PORT))
    print("[OK] Robota BASARIYLA BAGLANILDI!")
    client.setblocking(False)
except Exception as e:
    print(f"[HATA] Baglanti hatasi! Pi'nin acik oldugundan emin ol.\nHata: {e}")
    exit()

# ==== MODEL AYARLARI ====
model = YOLO("best.pt")
CENTER_L, CENTER_R = 0.35, 0.65

cap = cv2.VideoCapture(0)
mode = "MANUAL"
last_command = "STOP"

# ==== VISION MODU KOMUT KARARLILIĞI FİLTRESİ ====
# STOP anında uygulanır. Diğer komutlar ~1 saniye üst üste
# görülürse onaylanır. Bu sayede modelin anlık hatalı tahminleri
# arabayı hareket ettirmez.
ONAY_SAYISI      = 25        # 25 FPS varsayımıyla ~1 saniye
aday_komut       = "STOP"    # Şu an biriken komut adayı
aday_sayac       = 0         # Kaç kez üst üste geldi
onayli_komut     = "STOP"    # Gerçekten Pi'ye gönderilecek komut

# Ekranda gösterilecek mesafe yazıları (ön ve arka)
mesafe_on_yazisi   = "Bekleniyor..."
mesafe_arka_yazisi = "Bekleniyor..."

print("\n--- KONTROL REHBERI ---")
print("V: Vision (AI) Moduna Gec")
print("M: Manuel Moda Gec")
print("W,A,S,D: Manuel Surus")
print("Space: Durdur")
print("Q: Cikis\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    src_h, src_w = frame.shape[:2]
    command = "STOP"

    key = cv2.waitKey(1) & 0xFF

    if key == ord('v'):
        mode = "VISION"
        print("\r[MOD] VISION (Yapay Zeka) Aktif     ", end="")
    elif key == ord('m'):
        mode = "MANUAL"
        print("\r[MOD] MANUEL Kontrol Aktif          ", end="")
    elif key == ord(' '):
        command = "STOP"
    elif key == ord('q'):
        break

    if mode == "MANUAL":
        if   key == ord('w'): command = "FWD"
        elif key == ord('s'): command = "BACK"
        elif key == ord('a'): command = "LEFT"
        elif key == ord('d'): command = "RIGHT"
        else: command = last_command if key != 255 else "STOP"
    else:
        results = model.predict(frame, conf=0.4, verbose=False)
        result  = results[0]

        if len(result.boxes) > 0:
            best_idx  = result.boxes.conf.argmax()
            best_box  = result.boxes[best_idx]
            class_id  = int(best_box.cls)
            class_name = model.names[class_id]
            x1, y1, x2, y2 = best_box.xyxy[0].tolist()
            cx   = (x1 + x2) / 2.0
            norm = cx / src_w

            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(frame, f"{class_name}", (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            if   class_name == "el":   command = "FWD"
            elif class_name == "one":  command = "BACK"
            elif class_name == "none": command = "STOP"
            elif class_name == "two":
                if   norm < CENTER_L: command = "LEFT"
                elif norm > CENTER_R: command = "RIGHT"
                else:                 command = "FWD"
        else:
            command = "STOP"

    # ==== KOMUT KARARLILIĞI FİLTRESİ (sadece VISION modunda) ====
    if mode == "VISION":
        if command == "STOP":
            # STOP her zaman anında geçerli
            aday_komut   = "STOP"
            aday_sayac   = 0
            onayli_komut = "STOP"
        elif command == aday_komut:
            # Aynı komut üst üste geliyor, sayacı artır
            aday_sayac += 1
            if aday_sayac >= ONAY_SAYISI:
                onayli_komut = aday_komut  # ~1 saniye doldu, onayla
        else:
            # Farklı bir komut geldi, sayacı sıfırla ve yeni adayı başlat
            aday_komut = command
            aday_sayac = 1
            # Onaylı komut değişmez, araç önceki onaylı komutla devam eder
        command = onayli_komut  # Ekranda ve Pi'ye gidecek komut
    # Manuel modda filtre yok, komut direkt gönderilir

    # 1. Komutu Pi'ye gönder
    try:
        client.sendall((command + "\n").encode('utf-8'))
        last_command = command
    except BlockingIOError:
        pass
    except Exception:
        print("\n[HATA] Baglanti koptu!")
        break

    # 2. Pi'den gelen mesafeyi oku
    # Pi artık "on_mesafe,arka_mesafe\n" formatında gönderiyor
    try:
        data = client.recv(1024).decode('utf-8').strip()
        if data:
            son_olcum = data.split('\n')[-1].strip()
            if ',' in son_olcum:
                parcalar = son_olcum.split(',')
                on_val   = parcalar[0].strip()
                arka_val = parcalar[1].strip()

                mesafe_on_yazisi   = f"{on_val} cm"   if on_val   not in ("-1.0", "-1") else "Menzil Disi"
                mesafe_arka_yazisi = f"{arka_val} cm" if arka_val not in ("-1.0", "-1") else "Menzil Disi"
            else:
                # Eski format gelirse (tek değer) geriye dönük uyumluluk
                mesafe_on_yazisi = f"{son_olcum} cm" if son_olcum not in ("-1.0", "-1") else "Menzil Disi"

    except BlockingIOError:
        pass  # Bekleyen yeni veri yok, atla
    except Exception:
        pass

    # ==== EKRANA YAZDIR ====
    color = (0, 255, 0) if mode == "VISION" else (255, 255, 0)
    # Vision modunda onay bekliyorsa kaç frame kaldığını göster
    if mode == "VISION" and aday_komut != "STOP" and aday_sayac < ONAY_SAYISI:
        yuzdе = int((aday_sayac / ONAY_SAYISI) * 100)
        durum_yazi = f"MOD: {mode} | ONAYLANIYOR: {aday_komut} %{yuzdе}"
    else:
        durum_yazi = f"MOD: {mode} | KOMUT: {command}"
    cv2.putText(frame, durum_yazi,
                (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    cv2.putText(frame, f"ON MESAFE:   {mesafe_on_yazisi}",
                (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    cv2.putText(frame, f"ARKA MESAFE: {mesafe_arka_yazisi}",
                (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)

    cv2.imshow("kontrol", frame)

try:
    client.setblocking(True)
    client.sendall("STOP\n".encode('utf-8'))
except:
    pass

client.close()
cap.release()
cv2.destroyAllWindows()
