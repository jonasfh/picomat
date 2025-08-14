# MicroPython – Kattemater m/2 sensorer, dagsteller, SVG-status
# Linjelengde <= 80

import network
import socket
import time
import machine

# --- Konfig ---
WIFI_SSID = 'f5-nest'
WIFI_PASS = 'mnbvcxz1'
PORT = 80

# --- Hjelp: tid uten strftime ---
def now_str():
    t = time.localtime()
    y, m, d, H, M, S = t[0], t[1], t[2], t[3], t[4], t[5]
    return "%04d-%02d-%02d %02d:%02d:%02d" % (y, m, d, H, M, S)

def today_str():
    t = time.localtime()
    return "%04d-%02d-%02d" % (t[0], t[1], t[2])

# --- SVG-status ---
def svg_status(voltage):
    if voltage > 2.5:
        color = "green"
    elif voltage > 2.0:
        color = "yellow"
    else:
        color = "red"
    return (f"<svg width='20' height='20'>"
            f"<circle cx='10' cy='10' r='8' fill='{color}'/>"
            f"</svg>")

# --- Klasse ---
class Kattemater:
    def __init__(self, knapp_pin, adc_pin1, adc_pin2,
                 thr_mid_v=0.66, hyst_v=0.03, press_s=0.5):
        self.knapp = machine.Pin(knapp_pin, machine.Pin.OUT)
        self.adc1 = machine.ADC(adc_pin1)
        self.adc2 = machine.ADC(adc_pin2)
        self.conv = 3.3 / 65535
        self.logg = []
        self.knapp.value(1)
        self.thr_mid_v = thr_mid_v
        self.hyst_v = hyst_v
        self.state = None
        self.press_s = press_s
        self.teller = 0
        self.dato = today_str()

    def _adc_avg(self, adc, n=16):
        s = 0
        for _ in range(n):
            s += adc.read_u16()
        raw = s // n
        v = raw * self.conv
        return raw, v

    def les_sensorer(self):
        return self._adc_avg(self.adc1), self._adc_avg(self.adc2)

    def nivaa(self):
        _, v = self._adc_avg(self.adc1)
        low_t = self.thr_mid_v - self.hyst_v
        high_t = self.thr_mid_v + self.hyst_v
        if self.state is None:
            self.state = "mer_enn_halv" if v < self.thr_mid_v \
                         else "mindre_enn_halv"
        else:
            if self.state == "mer_enn_halv" and v > high_t:
                self.state = "mindre_enn_halv"
            elif self.state == "mindre_enn_halv" and v < low_t:
                self.state = "mer_enn_halv"
        txt = "Mer enn halvfull" if self.state == "mer_enn_halv" \
              else "Mindre enn halvfull"
        return v, txt

    def mate(self, varighet=None):
        if today_str() != self.dato:
            self.teller = 0
            self.dato = today_str()
        dur = self.press_s if varighet is None else varighet
        self.knapp.value(0)
        time.sleep(dur)
        self.knapp.value(1)
        self.teller += 1
        ts = now_str()
        self.logg.insert(0, f"{ts} - matet i {dur:.2f}s "
                            f"(nr {self.teller} i dag)")
        self.logg = self.logg[:30]

    def to_html(self):
        (raw1, v1), (raw2, v2) = self.les_sensorer()
        _, niv_txt = self.nivaa()
        log_items = "".join(f"<li>{e}</li>" for e in self.logg)
        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html><head><meta charset='utf-8'>")
        html.append("<title>Kattemater</title></head><body>")
        html.append("<h1>Kattemater</h1>")
        html.append(f"<p>Sensor1: raw={raw1}, volt={v1:.2f} V</p>")
        html.append(f"<p>Sensor2: raw={raw2}, volt={v2:.2f} V</p>")
        html.append(f"<p>Nivå: <b>{niv_txt}</b> {svg_status(v2)}</p>")
        html.append(f"<p>Matinger i dag: {self.teller}</p>")
        html.append("<form method='POST'>")
        html.append("<button type='submit'>Mat Kisse</button>")
        html.append("</form>")
        html.append("<p>Quick link: <a href='/feed'>/feed</a></p>")
        html.append("<h2>Logg (seneste først)</h2><ul>")
        html.append(log_items or "<li>(ingen hendelser ennå)</li>")
        html.append("</ul></body></html>")
        return "\r\n".join(html)

# --- Wi-Fi ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)
while not wlan.isconnected():
    print("Kobler til Wi-Fi...")
    time.sleep(1)
print("Tilkoblet!", wlan.ifconfig())

# --- Server ---
mater = Kattemater(knapp_pin=15, adc_pin1=26, adc_pin2=27,
                   thr_mid_v=0.66, hyst_v=0.03)

addr = socket.getaddrinfo('0.0.0.0', PORT)[0][-1]
srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(addr)
srv.listen(1)
print("Server på", addr)

while True:
    try:
        cl, a = srv.accept()
        req = cl.recv(1024).decode('utf-8', 'ignore')
        first = req.split("\r\n", 1)[0] if req else ""
        do_feed = ("POST " in first) or ("GET /feed" in first)
        if do_feed:
            mater.mate()
            print("Mating:", now_str())
        body = mater.to_html()
        resp = []
        resp.append("HTTP/1.1 200 OK")
        resp.append("Content-Type: text/html; charset=utf-8")
        resp.append("Connection: close")
        resp.append("")
        resp.append(body)
        cl.send("\r\n".join(resp))
        cl.close()
    except Exception as e:
        print("Feil:", e)
        time.sleep(0.5)
