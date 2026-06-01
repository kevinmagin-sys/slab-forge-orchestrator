import os
import threading


class Settings:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.DATABASE_URI = os.environ.get("DATABASE_URI", "sqlite:///:memory:")
        self.TELEMETRY_DB_URI = os.environ.get("TELEMETRY_DB_URI", "sqlite:///telemetry.db")
        self.TELEMETRY_FALLBACK_FILE = os.environ.get("TELEMETRY_FALLBACK_FILE", "telemetry_fallback.log")
        self.TELEMETRY_QUEUE_MAXSIZE = int(os.environ.get("TELEMETRY_QUEUE_MAXSIZE", "1000"))
        self.TELEMETRY_QUEUE_FALLBACK = os.environ.get("TELEMETRY_QUEUE_FALLBACK", "drop_oldest")
        self.BIND_ADDRESS = os.environ.get("BIND_ADDRESS", "0.0.0.0")
        self.BIND_PORT = int(os.environ.get("BIND_PORT", "9000"))
        self.SOCKET_BACKLOG = int(os.environ.get("SOCKET_BACKLOG", "128"))
        self.MAX_PACKET_SIZE = int(os.environ.get("MAX_PACKET_SIZE", "4096"))
        self.MAX_CONCURRENT_CONNECTIONS = int(os.environ.get("MAX_CONCURRENT_CONNECTIONS", "50"))
        self.PRIMARY_TIMEOUT = float(os.environ.get("PRIMARY_TIMEOUT", "2.5"))
        self.FALLBACK_TIMEOUT = float(os.environ.get("FALLBACK_TIMEOUT", "4.0"))
        self.MAX_CONCURRENT_TASKS = int(os.environ.get("MAX_CONCURRENT_TASKS", "50"))
        self.ARTIFACT_PATH = os.environ.get("ARTIFACT_PATH", "/tmp/vision_capture.png")

    @classmethod
    def instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


def get_settings():
    return Settings.instance()
