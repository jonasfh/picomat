import network
import socket
import time
import machine

# Tilkobling til Wi-Fi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect('f5-nest', 'mnbvcxz1')

while not wlan.isconnected():
    print("Kobler til Wi-Fi...")
    time.sleep(1)

print("Tilkoblet!", wlan.ifconfig())

# Sett opp server socket
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)
print("Server kjører på", addr)

sensor = machine.ADC(4)
conversion = 3.3 / (65535)

knapp = machine.Pin(15, machine.Pin.OUT)
knapp.value(1)  # Sett knapp til HIGH for å aktivere

while True:
    try:
        cl, addr = s.accept()
        print("Ny tilkobling fra", addr)

        request = cl.recv(1024)
        print("Request mottatt")

        reading = sensor.read_u16() * conversion
        temp = 27 - (reading - 0.706) / 0.001721

        knapp.value(0)  # Slå av knappen for å mate
        time.sleep(0.5)  # Vent litt for å sikre at knappen er av
        knapp.value(1)


        response = f"""\
HTTP/1.1 200 OK

<!DOCTYPE html>
<html>
  <head><title>PicoTemp</title></head>
  <body>
    <h1>Temperatur: {temp:.2f} °C</h1>
    <p>Mater ut 1 porsjon mat til kissen.</p>
  </body>
</html>
"""
        cl.send(response)
        cl.close()

        # 💤 Legg inn pause
        time.sleep(0.1)

    except Exception as e:
        print("Feil:", e)
        time.sleep(1)

# Rydd opp ved avslutning
knapp.value(1)  # Sett knapp til HIGH før avslutning
s.close()
wlan.disconnect()
wlan.active(False)
print("Server avsluttet.")