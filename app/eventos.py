"""Bus de eventos en memoria para las conexiones SSE: cada pestaña suscribe una cola."""
import queue
import threading


class Bus:
    def __init__(self, max_en_cola=500):
        self._colas = set()
        self._lock = threading.Lock()
        self.max_en_cola = max_en_cola

    def suscribir(self):
        q = queue.Queue(maxsize=self.max_en_cola)
        with self._lock:
            self._colas.add(q)
        return q

    def desuscribir(self, q):
        with self._lock:
            self._colas.discard(q)

    def emitir(self, tipo, datos):
        with self._lock:
            colas = list(self._colas)
        for q in colas:
            try:
                q.put_nowait((tipo, datos))
            except queue.Full:
                pass

    @property
    def suscriptores(self):
        with self._lock:
            return len(self._colas)
