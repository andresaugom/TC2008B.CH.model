""" Este script solo considera cuando llegan los votantes, la etapa de verificación en lista nominal y """
""" pasar a la mampara """

# Los eventos representan las acciones o cambios de estado que ocurren durante la simulación
# del proceso electoral.
# Cada evento está asociado a un tiempo de ejecución, un tipo de evento
#(llegada, verificación, mampara o salida) y un votante.
# Los eventos se administran mediante una cola de prioridad (heapq), que permite procesarlos en orden cronológico.
# Al ejecutarse un evento, se actualiza el estado del votante, se asignan o liberan los recursos correspondientes
#(verificadores o mamparas) y, cuando es necesario, se generan nuevos eventos que se incorporan a la cola de prioridad.

import random
import heapq
from collections import deque

N = 200
random.seed()

# Recursos disponibles
verificadores = [True] * 3
mamparas = [True] * 2

# Filas de espera
fila_verificacion = deque()
fila_mampara = deque()
fila_casilla = deque()

# Cola de eventos
eventos = []
contador = 0

# Partidos disponibles
partidos = ["Rojo", "Azul"]


class Votante:
    def __init__(self, numero):
        self.id = numero
        self.estado = "En camino"
        self.llegada = 0
        self.salida = 0

     #El votante al llegar decide formarse y esperar, ó marcharse
    def decidir_formarse(self, personas_en_fila):
        # Probabilidad de abandonar según la fila
        if personas_en_fila < round(N*.20):
            probabilidad = 0.10
        elif personas_en_fila < round(N*.40):
            probabilidad = 0.40
        else:
            probabilidad = 0.80

        numero = random.random()

        if numero < probabilidad:
            return "Abandonar"
        else:
            return "Formarse"

    def doc_valido(self): 
        # Probabilidad de que el documento sea válido
        probabilidad = 0.90
        numero = random.random()

        if numero < probabilidad:
            return True
        else:
            return False

    def elegir_partido(self):
        self.partido = random.choice(partidos)
        return self.partido
        
class Casilla: 
    def __init__(self, numero):
        self.id = numero
        self.estado = "Disponible"
        self.votante = None
        self.votos = []

    def recibir_voto(self, votante, voto):
        self.votos.append(voto)
        self.votante = votante

    def cambiar_estado(self):
        if self.estado == "Disponible":
            self.estado = "Ocupada"
        else:
            self.estado = "Disponible"

urna = Casilla(1)

# Método independiente del objeto para insertar eventos en heapq
def nuevo_evento(tiempo, tipo, votante, recurso=-1):
    global contador
    contador += 1
    heapq.heappush(
        eventos,
        (tiempo, contador, tipo, votante, recurso)
    )




# EVENTO 1: LLEGADA
# procesa la llegada de un votante a la casilla electoral, actualiza su estado,
# lo incorpora a la fila de verificación e intenta asignarle un verificador disponible.
def llegada_votante(votante, t):
    votante.llegada = t

    personas_en_fila = len(fila_verificacion)

    decision = votante.decidir_formarse(personas_en_fila)

    if decision == "Abandonar":
        votante.estado = "Abandonó"
        votante.salida = t

        print(f"{t:3} | Votante {votante.id:02d} "
              f"decide abandonar la casilla")

    else:
        votante.estado = "Esperando verificación"
        fila_verificacion.append(votante)

        print(f"{t:3} | Votante {votante.id:02d} "
              f"decide formarse")

        # Asigna al votante un tiempo para verificar y lo asigna al primer verificador libre
        # Ustedes pueden dejar al votante que decida con que verificador va (en caso de haber dos disponibles)
        verificar(t)




# EVENTO 2: VERIFICAR
# asignar los votantes que están esperando en la fila de verificación a cualquiera de los tres verificadores
# disponibles. Cuando un votante comienza a ser atendido, se genera un tiempo aleatorio de atención y
# se programa un nuevo evento en heapq.
def verificar(t):
    for i in range(3):
        # El verificador esta libre y existe al menos un votante esperando
        if verificadores[i] and fila_verificacion:
            votante = fila_verificacion.popleft()
            verificadores[i] = False
            votante.estado = "Verificando"

            duracion = random.randint(2, 7)

            #Cuando se calcula el tiempo aleatorio para la verificacion y el verificador donde se forma el votante
            # t + duracion: tiempo en que termina el evento.
            # "Verificar": tipo de evento.
            # votante: votante que está siendo atendido.
            # i: número del verificador que lo atiende (0, 1 o 2).
            nuevo_evento(
                t + duracion, "Verificar", votante, i
            )

            print(f"{t:3} | Votante {votante.id:02d} "
                  f"inicia verificación {i+1}")


# EVENTO 3: MAMPARA
# asignar los votantes que están esperando en la fila despues de la verificacion a una de las dos mamparas
# disponibles.
# Una vez que el votante comienza a votar, se genera un tiempo aleatorio y se programa un nuevo evento en heapq para indicar cuándo terminará.
def mampara(t):
    for i in range(2):
        # Se descartan votantes con documento inválido hasta encontrar uno válido
        while mamparas[i] and fila_mampara:
            votante = fila_mampara.popleft()

            if not votante.doc_valido():
                votante.estado = "Documento inválido"
                votante.salida = t

                print(f"{t:3} | Votante {votante.id:02d} "
                      f"tiene documento inválido y abandona la casilla")
                continue

            mamparas[i] = False
            votante.estado = "En mampara"

            duracion = random.randint(3, 9)

            nuevo_evento(
                t + duracion, "Mampara", votante, i
            )

            print(f"{t:3} | Votante {votante.id:02d} "
                  f"inicia mampara {i+1}")


# EVENTO 4: CASILLA (urna única)
def usar_casilla(t):
    if urna.estado == "Disponible" and fila_casilla:
        votante = fila_casilla.popleft()
        urna.cambiar_estado()
        votante.estado = "En casilla"
        duracion = random.randint(4, 10)

        nuevo_evento(
            t + duracion, "Casilla", votante, 1
        )

        decision = votante.elegir_partido()

        urna.recibir_voto(votante, decision)

        print(f"{t:3} | Votante {votante.id:02d} "
              f"inicia casilla")


# EVENTO 5: SALIR
def salir(votante, t):
    urna.cambiar_estado()
    votante.estado = "Finalizado"
    votante.salida = t

    print(f"{t:3} | Votante {votante.id:02d} "
          f"sale de la casilla")


# CREAR VOTANTES Y PROGRAMAR LLEGADAS
votantes = [Votante(i + 1) for i in range(N)]

tiempo_llegada = 0

for votante in votantes:
    tiempo_llegada += random.randint(1, 4)
    nuevo_evento(tiempo_llegada, "Llegada", votante)


# SIMULACIÓN
# Durante el proceso electoral, cada votante genera diferentes
# eventos dependiendo de la etapa en la que se encuentra.
# Un votante puede tener como máximo un evento pendiente en heapq.
# Cuando termina un evento, puede generarse el siguiente,
# dependiendo de la disponibilidad de los recursos.

while eventos:

    # EN SU RETO, CADA EVENTO Y CAMBIO RELEVANTE DE ESTADO
    # SE DEBE COMUNICAR A UNITY PARA SU VISUALIZACIÓN.
    t, _, tipo, votante, recurso = heapq.heappop(eventos)

    # LLEGADA:
    # El votante llega a la casilla y entra a la fila de verificación.
    # Si hay un verificador disponible, comienza su atención.
    # Se genera un tiempo aleatorio y se programa en heapq
    # el evento de finalización de la verificación.
    if tipo == "Llegada":
        llegada_votante(votante, t)

    # VERIFICAR:
    # El votante termina la verificación de la lista nominal.
    # Se libera al verificador y el votante pasa a la fila de mamparas.
    # Se intenta atender al siguiente votante de la fila de
    # verificación y asignar una mampara disponible.
    # Si obtiene una mampara, se genera un tiempo aleatorio
    # y se programa en heapq la finalización de la votación.
    elif tipo == "Verificar":
        verificadores[recurso] = True

        votante.estado = "Esperando mampara"
        fila_mampara.append(votante)

        verificar(t)
        mampara(t)

    # MAMPARA:
    # El votante termina de votar en la mampara.
    # Se libera la mampara y el votante sale de la casilla.
    # Se intenta asignar la mampara liberada al siguiente
    # votante que esté esperando.
    elif tipo == "Mampara":
        mamparas[recurso] = True

        votante.estado = "Esperando casilla"
        fila_casilla.append(votante)

        usar_casilla(t)
        mampara(t)

    # CASILLA:
    # El votante termina de depositar su voto y sale de la casilla.
    elif tipo == "Casilla":
        salir(votante, t)
        usar_casilla(t)




# RESULTADOS
print("\nRESULTADOS")

for votante in votantes:
    permanencia = votante.salida - votante.llegada

    print(f"Votante {votante.id:02d}: "
          f"{permanencia} minutos")

promedio = sum(
    v.salida - v.llegada for v in votantes
) / N

print(f"\nTiempo promedio: {promedio:.2f} minutos")

print(f"\nVotos por partido:")
for partido in partidos:
    votos = sum(
        1 for v in votantes if getattr(v, "partido", None) == partido
    )
    print(f"{partido}: {votos} votos")

print(f"\nPartido ganador:")
votos_por_partido = {partido: sum(1 for v in votantes if getattr(v, "partido", None) == partido) for partido in partidos}
ganador = max(votos_por_partido, key=votos_por_partido.get)
print(f"{ganador} con {votos_por_partido[ganador]} votos")
