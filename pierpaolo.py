import math
import socket
import threading
import time

# ==========================
# Parametri dell'Ippodromo
# ==========================

ZeroLati = 44.60878672          # Latitudine del punto di riferimento (traguardo)
ZeroLong = 10.91568733          # Longitudine del punto di riferimento (traguardo)

theta_deg = 16                  # Angolo di rotazione dell'ippodromo (gradi)
theta_rad = math.radians(theta_deg)
vCosRotIpp = math.cos(theta_rad)  # Coseno dell'angolo di rotazione
vSinRotIpp = math.sin(theta_rad)  # Seno dell'angolo di rotazione

# Parametri del tracciato
mRaggio1 = 81                   # Raggio delle semicirconferenze (metri)
mRetAfterP0 = 70                # Metri del rettilineo dopo il punto zero (arrivo/partenza)
mRetBeforeP0 = 180              # Metri del rettilineo prima del punto zero (arrivo/partenza)
mLarghezza = 20                 # Metri di larghezza del circuito Ippodromo

total_race_meters = 1600        # Lunghezza della gara in metri

# ==========================
# Funzioni utili
# ==========================

# Calcolo dinamico dei metri per millesimo di grado
def calculate_meters_per_degree(ZeroLati):
    # Raggio della Terra (in metri)
    R = 6378137

    # Calcola i metri per millesimo di grado di latitudine
    mxmLati = (math.pi / 180) * R / 1000

    # Calcola i metri per millesimo di grado di longitudine in base alla latitudine
    mxmLong = (math.pi / 180) * R * math.cos(math.radians(ZeroLati)) / 1000

    return mxmLati, mxmLong

# Converti le coordinate GPS in coordinate locali
def convert_gps_to_local(CavLati, CavLong, ZeroLati, ZeroLong, mxmLati, mxmLong, vCosRotIpp, vSinRotIpp):
    # Calcola le differenze in millesimi di grado
    deltaLat = (CavLati - ZeroLati) * 1000  # Differenza in millesimi di grado
    deltaLong = (CavLong - ZeroLong) * 1000

    # Converti in metri
    deltaLat_m = deltaLat * mxmLati
    deltaLong_m = deltaLong * mxmLong

    # Applica la rotazione corretta (antiorario)
    xCav = deltaLong_m * vCosRotIpp - deltaLat_m * vSinRotIpp
    yCav = deltaLong_m * vSinRotIpp + deltaLat_m * vCosRotIpp

    return xCav, yCav

# Converti le coordinate locali in coordinate GPS
def convert_local_to_gps(x, y, ZeroLati, ZeroLong, mxmLati, mxmLong, vCosRotIpp, vSinRotIpp):
    # Applica la rotazione inversa
    deltaLong_m = x * vCosRotIpp + y * vSinRotIpp
    deltaLat_m = -x * vSinRotIpp + y * vCosRotIpp

    # Converti in millesimi di grado
    deltaLat = deltaLat_m / mxmLati
    deltaLong = deltaLong_m / mxmLong

    # Converti in gradi
    CavLati = ZeroLati + (deltaLat / 1000)
    CavLong = ZeroLong + (deltaLong / 1000)

    return CavLati, CavLong

# Calcola la distanza punto-segmento e la proiezione sul segmento
def point_to_segment_distance(x, y, segment):
    x1, y1 = segment['x1'], segment['y1']
    x2, y2 = segment['x2'], segment['y2']
    dx = x2 - x1
    dy = y2 - y1
    if dx == dy == 0:
        # Il segmento è un punto
        return math.hypot(x - x1, y - y1), x1, y1
    # Calcola il parametro t della proiezione del punto sul segmento
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    # Calcola la proiezione
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    # Distanza tra il punto e la proiezione
    distance = math.hypot(x - proj_x, y - proj_y)
    return distance, proj_x, proj_y

# ==========================
# Generazione dei Settori (Segmenti)
# ==========================

def generate_track_segments():
    segments = []  # Lista dei segmenti da memorizzare

    # Definizione delle sezioni del tracciato
    sections = [
        ('straight_after_traguardo', mRetAfterP0),
        ('curve_bottom', math.pi * mRaggio1),  # Circonferenza inferiore
        ('straight_opposite', mRetAfterP0 + mRetBeforeP0),
        ('curve_top', math.pi * mRaggio1),     # Circonferenza superiore
        ('straight_before_traguardo', mRetBeforeP0)
    ]

    desired_segment_length = 1.0  # Lunghezza desiderata per ogni segmento (metri)
    cumulative_distance = 0.0  # Distanza cumulativa

    for section_name, section_length in sections:
        if section_name == 'straight_after_traguardo':
            num_segments = int(section_length / desired_segment_length)
            dx = desired_segment_length
            for i in range(num_segments):
                start_x = i * dx
                start_y = 0.0
                end_x = start_x + dx
                end_y = 0.0
                segment_length = math.hypot(end_x - start_x, end_y - start_y)
                cumulative_distance += segment_length
                segments.append(create_segment(len(segments), start_x, start_y, end_x, end_y, cumulative_distance))
        elif section_name == 'curve_bottom':
            total_arc_length = section_length
            num_segments = int(total_arc_length / desired_segment_length)
            angle_increment = math.pi / num_segments
            for i in range(num_segments):
                theta1 = i * angle_increment
                theta2 = (i + 1) * angle_increment
                start_x = mRetAfterP0 + mRaggio1 * math.sin(theta1)
                start_y = mRaggio1 - mRaggio1 * math.cos(theta1)
                end_x = mRetAfterP0 + mRaggio1 * math.sin(theta2)
                end_y = mRaggio1 - mRaggio1 * math.cos(theta2)
                segment_length = math.hypot(end_x - start_x, end_y - start_y)
                cumulative_distance += segment_length
                segments.append(create_segment(len(segments), start_x, start_y, end_x, end_y, cumulative_distance))
        elif section_name == 'straight_opposite':
            num_segments = int(section_length / desired_segment_length)
            dx = desired_segment_length
            start_x = mRetAfterP0 + mRaggio1 * math.sin(math.pi)
            for i in range(num_segments):
                x = start_x - i * dx
                start_y = 2 * mRaggio1
                end_x = x - dx
                end_y = start_y
                segment_length = math.hypot(end_x - x, end_y - start_y)
                cumulative_distance += segment_length
                segments.append(create_segment(len(segments), x, start_y, end_x, end_y, cumulative_distance))
        elif section_name == 'curve_top':
            total_arc_length = section_length
            num_segments = int(total_arc_length / desired_segment_length)
            angle_increment = math.pi / num_segments
            for i in range(num_segments):
                theta1 = math.pi + i * angle_increment
                theta2 = math.pi + (i + 1) * angle_increment
                start_x = -mRetBeforeP0 + mRaggio1 * math.sin(theta1)
                start_y = mRaggio1 - mRaggio1 * math.cos(theta1)
                end_x = -mRetBeforeP0 + mRaggio1 * math.sin(theta2)
                end_y = mRaggio1 - mRaggio1 * math.cos(theta2)
                segment_length = math.hypot(end_x - start_x, end_y - start_y)
                cumulative_distance += segment_length
                segments.append(create_segment(len(segments), start_x, start_y, end_x, end_y, cumulative_distance))

        elif section_name == 'straight_before_traguardo':
            num_segments = int(section_length / desired_segment_length)
            dx = desired_segment_length
            for i in range(num_segments):
                start_x = -mRetBeforeP0 + i * dx
                start_y = 0.0
                end_x = start_x + dx
                end_y = 0.0
                segment_length = math.hypot(end_x - start_x, end_y - start_y)
                cumulative_distance += segment_length
                segments.append(create_segment(len(segments), start_x, start_y, end_x, end_y, cumulative_distance))

    print(f"Total cumulative distance: {cumulative_distance} meters")
    return segments, cumulative_distance

def create_segment(index, x1, y1, x2, y2, cumulative_distance):
    """
    Crea un segmento con i valori A, B, C per il calcolo della distanza punto-retta.
    """
    # Calcola i coefficienti A, B, C della retta Ax + By + C = 0
    A = y2 - y1  # A = y2 - y1
    B = x1 - x2  # B = x1 - x2
    C = (x2 * y1) - (x1 * y2)  # C = x2*y1 - x1*y2
    rad = math.sqrt(A*A + B*B)
    return {
        's': index,    # Indice del settore
        'x1': x1,
        'y1': y1,
        'x2': x2,
        'y2': y2,
        'A': A,        # Coefficiente A della retta
        'B': B,        # Coefficiente B della retta
        'C': C,        # Coefficiente C della retta
        'rad': rad,    # Radice del denominatore per la distanza punto-retta
        'cumulative_distance': cumulative_distance - math.hypot(x2 - x1, y2 - y1)  # Distanza cumulativa fino all'inizio di questo segmento
    }

# ==========================
# Gestione del Server UDP
# ==========================

class UDPServer:
    def __init__(self, listen_ip, listen_port, segments, ZeroLati, ZeroLong, mxmLati, mxmLong, vCosRotIpp, vSinRotIpp, race_started_event, total_track_length):
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.segments = segments
        self.ZeroLati = ZeroLati
        self.ZeroLong = ZeroLong
        self.mxmLati = mxmLati
        self.mxmLong = mxmLong
        self.vCosRotIpp = vCosRotIpp
        self.vSinRotIpp = vSinRotIpp
        self.race_started_event = race_started_event
        self.total_track_length = total_track_length
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.horses = {}  # Dizionario per tenere traccia dei cavalli
        self.race_start_time = None

        # Socket per inviare i pacchetti della classifica
        self.broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_address = ('0.0.0.0', 4141)

        try:
            self.sock.bind((self.listen_ip, self.listen_port))
            print(f"Server UDP in ascolto su {self.listen_ip}:{self.listen_port}")
        except Exception as e:
            print(f"Errore nel bind della socket: {e}")
            exit(1)

    def start(self):
        thread = threading.Thread(target=self.listen)
        thread.daemon = True
        thread.start()

    def listen(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)  # Buffer size 1024 bytes
                self.process_packet(data, addr)
            except Exception as e:
                print(f"Errore nella ricezione dei dati: {e}")

    def process_packet(self, data, addr):
        data_str = data.decode('utf-8').strip()
        # print(data_str)
        if not self.race_started_event.is_set():
            if "START" in data_str.upper():
                self.horses = {}  # Resetta le informazioni dei cavalli
                print("[INFO] Comando di avvio ricevuto. Inizio della gara!")
                self.race_started_event.set()
                self.race_start_time = time.time() # parte il timer
            return
        else:
            if "END" in data_str.upper():
                print("[INFO] Comando di fine gara ricevuto. Fine della gara!")
                self.horses = {}  # Resetta le informazioni dei cavalli
                self.race_started_event.clear()
                self.race_start_time = None
                return
            # Se la gara è iniziata, processa i pacchetti GPS
            try:
                parts = data_str.split(',')
                if len(parts) < 9:
                    print(f"Dati incompleti ricevuti: {data_str}")
                    return
                if parts[0].strip().upper() != 'GPS':
                    print(f"Formato dati inaspettato: {data_str}")
                    return

                # Estrarre i dati del cavallo
                horse_id = parts[1].strip()
                CavLati = float(parts[2].strip())
                CavLong = float(parts[3].strip())
                horseSpeed = float(parts[6].strip()) * 3.6

                # Converti le coordinate GPS in coordinate locali
                xCav, yCav = convert_gps_to_local(
                    CavLati, CavLong, self.ZeroLati, self.ZeroLong,
                    self.mxmLati, self.mxmLong, self.vCosRotIpp, self.vSinRotIpp
                )

                # Trova il segmento più vicino
                min_distance = float('inf')
                closest_segment = None
                for segment in self.segments:
                    distance, proj_x, proj_y = point_to_segment_distance(xCav, yCav, segment)
                    if distance < min_distance:
                        min_distance = distance
                        closest_segment = segment
                        segment_progress = math.hypot(proj_x - segment['x1'], proj_y - segment['y1'])

                if closest_segment:
                    cumulative_distance = closest_segment['cumulative_distance']
                    total_distance = cumulative_distance + segment_progress

                    # Calcola metriCorsiaDelCavallo
                    metriCorsiaDelCavallo = math.hypot(xCav - closest_segment['x1'], yCav - closest_segment['y1'])

                    # Aggiorna le informazioni del cavallo
                    horse = self.horses.get(horse_id, {
                        'distance': 0.0,
                        'x': 0.0,
                        'y': 0.0,
                        'laps_completed': 0,
                        'prev_distance': 0.0,
                        'meters_covered': 0,
                        'last_segment': None,
                        'metriCorsiaDelCavallo': 0.0,
                        'horseSpeed': 0.0,
                        'start_time': time.time()
                    })

                    # Verifica se il cavallo ha completato un giro
                    if total_distance < horse['prev_distance'] and (horse['prev_distance'] - total_distance) > (self.total_track_length / 2):
                        horse['laps_completed'] += 1

                    horse['prev_distance'] = total_distance
                    
                    # Aggiorno velocità
                    horse['horseSpeed'] = horseSpeed

                    # Calcola la distanza totale con i giri inclusi
                    total_distance_with_laps = horse['laps_completed'] * self.total_track_length + total_distance

                    # Check if the horse has moved to a new segment
                    if closest_segment['s'] != horse.get('last_segment'):
                        horse['meters_covered'] += 1  # Increment meters_covered by 1
                        horse['last_segment'] = closest_segment['s']  # Update the last_segment

                    horse['distance'] = total_distance_with_laps
                    horse['x'] = xCav
                    horse['y'] = yCav # PARAMETRO NUOVO YYYYYY
                    horse['metriCorsiaDelCavallo'] = metriCorsiaDelCavallo  # PARAMETRO NUOVO CORSIA CAVALLO
                    self.horses[horse_id] = horse

                    # Aggiorna, stampa e invia la classifica
                    self.send_rankings()

            except Exception as e:
                print(f"Errore nell'elaborazione dei dati da {addr}: {data_str}\n{e}")

    def send_rankings(self):
        # Ordina i cavalli per distanza percorsa in ordine decrescente
        sorted_horses = sorted(self.horses.items(), key=lambda x: x[1]['distance'], reverse=True)

        # Costruisci il pacchetto da inviare con il formato richiesto
        packet = "CLASSIFICA"
        for idx, (horse_id, horse_data) in enumerate(sorted_horses):
            distance = horse_data['distance']
            meters_covered = horse_data['meters_covered']
            y_coordinate = horse_data['metriCorsiaDelCavallo']
            horseSpeed = horse_data['horseSpeed']
            
            elapsed_time = time.time() - horse_data['start_time']
            if elapsed_time >= 60:
                minutes = int(elapsed_time) // 60
                seconds = int(elapsed_time) % 60
                elapsed_time_formatted = f"{minutes}m {seconds}s"
            else:
                elapsed_time_formatted = f"{int(elapsed_time)}s"
            
            if idx < len(sorted_horses) - 1:
                next_distance = sorted_horses[idx + 1][1]['distance']
                gap = distance - next_distance
                packet += f",({horse_id},{gap:.2f},{total_race_meters - meters_covered},{y_coordinate:.2f},{horseSpeed:.2f},{elapsed_time_formatted})"
            else:
                packet += f",({horse_id},last one,{total_race_meters - meters_covered},{y_coordinate:.2f},{horseSpeed:.2f},{elapsed_time_formatted})"
        print(packet)

        # Invia il pacchetto UDP all'indirizzo specificato
        self.broadcast_sock.sendto(packet.encode('utf-8'), self.broadcast_address)
        
        # Subito dopo, invia il pacchetto TEL
        if len(sorted_horses) > 0:
            leader_id, leader_data = sorted_horses[0]
            leader_x = leader_data['x']
            leader_y = leader_data['y']
            tel_packet = f"TEL,{leader_x:.2f},{leader_y:.2f}"
            self.broadcast_sock.sendto(tel_packet.encode('utf-8'), self.broadcast_address)


        # Stampa la classifica per debug con il gap tra i cavalli e i metri percorsi
        print("\nClassifica attuale:")
        for idx, (horse_id, horse_data) in enumerate(sorted_horses):
            distance = horse_data['distance']
            meters_covered = horse_data['meters_covered']
            laps_completed = horse_data['laps_completed']
            metriCorsiaDelCavallo = horse_data['metriCorsiaDelCavallo']
            if idx < len(sorted_horses) - 1:
                next_distance = sorted_horses[idx + 1][1]['distance']
                gap = distance - next_distance
                print(f"{idx + 1}. Cavallo {horse_id}: {distance:.2f} settori ({laps_completed} giri), {total_race_meters - meters_covered}m al traguardo, Corsia: {metriCorsiaDelCavallo:.2f}m -> {gap:.2f}m di gap")
            else:
                print(f"{idx + 1}. Cavallo {horse_id}: {distance:.2f} settori ({laps_completed} giri), {total_race_meters - meters_covered}m al traguardo, Corsia: {metriCorsiaDelCavallo:.2f}m -> last one")
        print("\n")

# ==========================
# Main
# ==========================

def main():
    # Genera i segmenti del tracciato
    segments, total_track_length = generate_track_segments()

    # Calcola i valori dinamici dei metri per millesimo di grado
    mxmLati, mxmLong = calculate_meters_per_degree(ZeroLati)

    # Crea un evento per tracciare se la gara è iniziata
    race_started_event = threading.Event()

    # Crea e avvia il server UDP
    UDP_IP = "0.0.0.0"
    UDP_PORT = 4040
    udp_server = UDPServer(
        UDP_IP, UDP_PORT, segments, ZeroLati, ZeroLong, mxmLati, mxmLong, vCosRotIpp, vSinRotIpp,
        race_started_event, total_track_length
    )
    udp_server.start()

    # Thread per stampare "Waiting for starting command..." finché non arriva "START"
    def waiting_for_start():
        while True:
            if not race_started_event.is_set():
                print("Waiting for starting command...")
            time.sleep(5)  # Attende 5 secondi prima di stampare nuovamente

    waiting_thread = threading.Thread(target=waiting_for_start)
    waiting_thread.daemon = True
    waiting_thread.start()

    # Mantieni il thread principale in esecuzione
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Server UDP terminato.")

# Esegui il main
if __name__ == "__main__":
    main()
