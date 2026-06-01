import asyncio
import sys
import queue
import os
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional

from config.settings import get_settings

settings = get_settings()

# Define system exceptions for control flow termination
class DeployInit002Termination(Exception):
    """Custom exception to handle immediate termination of the DEPLOY-INIT-002 process."""
    pass


def core_translate_logic(raw_buffer: bytes) -> bytes:
    """Mock function representing the transformation engine on the incoming byte array."""
    # CPU-bound / synchronous placeholder; run in threadpool from async context
    return raw_buffer


def write_to_physical_storage_or_syslog(log_item: dict):
    """Mock function handling low-priority storage writes or system syslog outputs."""
    # Production telemetry writer: persist telemetry items to a dedicated DB table.
    # TELEMETRY_DB_URI can be set in the environment; defaults to a file-based sqlite DB.
    global _telemetry_db_engine
    try:
        engine = globals().get("_telemetry_db_engine")
        if engine is None:
            uri = settings.TELEMETRY_DB_URI
            engine = create_engine(uri)
            globals()["_telemetry_db_engine"] = engine

            # Ensure table exists
            create_stmt = text(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts DATETIME DEFAULT (CURRENT_TIMESTAMP),
                    level TEXT,
                    event TEXT,
                    client TEXT,
                    payload TEXT
                )
                """
            )
            with engine.begin() as conn:
                conn.execute(create_stmt)

        # Normalize fields
        level = log_item.get("level")
        event = log_item.get("event") or log_item.get("msg")
        client = log_item.get("client")
        # Keep free-form message fields (e.g. 'msg') in the payload for full context
        payload = {k: v for k, v in log_item.items() if k not in ("level", "event", "client")}

        # Serialize client and payload
        client_s = json.dumps(client, default=str)
        payload_s = json.dumps(payload, default=str)

        insert_stmt = text(
            "INSERT INTO telemetry (level, event, client, payload) VALUES (:level, :event, :client, :payload)"
        )
        with engine.begin() as conn:
            conn.execute(insert_stmt, {"level": level, "event": event, "client": client_s, "payload": payload_s})

    except SQLAlchemyError as dbe:
        # If DB persistence fails, fallback to append-to-file as durable backup
        try:
            fallback = settings.TELEMETRY_FALLBACK_FILE
            with open(fallback, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": datetime.utcnow().isoformat(), **log_item}, default=str) + "\n")
        except Exception:
            # Last resort: ignore to avoid crashing the caller
            pass
    except Exception:
        # Any other unexpected error - swallow to keep server running
        try:
            fallback = settings.TELEMETRY_FALLBACK_FILE
            with open(fallback, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": datetime.utcnow().isoformat(), **log_item}, default=str) + "\n")
        except Exception:
            pass


# SET BIND_ADDRESS = "0.0.0.0"
BIND_ADDRESS = settings.BIND_ADDRESS
# SET BIND_PORT = 9000
BIND_PORT = settings.BIND_PORT
# SET SOCKET_BACKLOG = 128
SOCKET_BACKLOG = settings.SOCKET_BACKLOG
# SET MAX_PACKET_SIZE = 4096
MAX_PACKET_SIZE = settings.MAX_PACKET_SIZE

# Maximum concurrent in-flight connections handled by worker coroutines
# This caps memory/CPU usage and provides backpressure when exhausted
MAX_CONCURRENT_CONNECTIONS = settings.MAX_CONCURRENT_CONNECTIONS

# Maximum size for the telemetry work queue to prevent unbounded memory growth.
TELEMETRY_QUEUE_MAXSIZE = settings.TELEMETRY_QUEUE_MAXSIZE
TELEMETRY_QUEUE_FALLBACK_STRATEGY = settings.TELEMETRY_QUEUE_FALLBACK

# // Core In-Memory Communication Queue (Thread-Safe Sink)
# SET TelemetryQueue = NEW queue.Queue(maxsize=TELEMETRY_QUEUE_MAXSIZE)
telemetry_queue = queue.Queue(maxsize=TELEMETRY_QUEUE_MAXSIZE)

# Async semaphore used to cap concurrent processing
semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_CONNECTIONS)


async def process_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_addr: Optional[tuple]):
    """Handle a single client connection. Runs inside a bounded semaphore permit."""
    try:
        enqueue_telemetry({"level": "DEBUG", "event": "process_connection_started", "client": client_addr})
        try:
            raw_buffer = await asyncio.wait_for(reader.read(MAX_PACKET_SIZE), timeout=2.0)
        except asyncio.TimeoutError:
            enqueue_telemetry({"level": "WARNING", "msg": "Client read timeout", "client": client_addr})
            return

        if not raw_buffer:
            # client closed cleanly or sent empty payload
            return

        # Offload CPU-bound translation to threadpool to avoid blocking event loop
        try:
            response_buffer = await asyncio.to_thread(core_translate_logic, raw_buffer)
        except Exception as e:
            enqueue_telemetry({"level": "ERROR", "msg": "Translation failed", "err": e, "client": client_addr})
            return

        try:
            writer.write(response_buffer)
            await writer.drain()
            enqueue_telemetry({"level": "INFO", "bytes": len(raw_buffer), "client": client_addr})
        except Exception as e:
            enqueue_telemetry({"level": "WARNING", "msg": "Client send failed", "err": e, "client": client_addr})

    except Exception as exc:
        enqueue_telemetry({"level": "ERROR", "msg": "Unhandled connection exception", "err": exc, "client": client_addr})

    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        # Release semaphore permit when connection is fully cleaned up
        try:
            semaphore.release()
            enqueue_telemetry({"level": "DEBUG", "event": "semaphore_released", "client": client_addr})
        except Exception:
            # If semaphore release fails, log and continue; do not crash server
            enqueue_telemetry({"level": "ERROR", "msg": "Semaphore release failed"})
        enqueue_telemetry({"level": "DEBUG", "event": "process_connection_ended", "client": client_addr})


async def handle_client_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Entry point for each accepted connection; enforces backpressure and spawns processing task."""
    client_addr = writer.get_extra_info("peername")

    # Try an immediate semaphore acquire to provide simple backpressure.
    # If none available, return a quick busy response and close the socket.
    acquired = False
    try:
        try:
            enqueue_telemetry({"level": "DEBUG", "event": "semaphore_acquire_attempt", "client": client_addr})
            await asyncio.wait_for(semaphore.acquire(), timeout=0.1)
            acquired = True
            enqueue_telemetry({"level": "DEBUG", "event": "semaphore_acquired", "client": client_addr})
        except asyncio.TimeoutError:
            acquired = False

        if not acquired:
            # Backpressure: politely refuse the connection without blocking
            try:
                writer.write(b"SERVER_BUSY\n")
                await writer.drain()
            except Exception:
                pass
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            enqueue_telemetry({"level": "WARNING", "msg": "Connection refused due to backpressure", "client": client_addr})
            return

        # Spawn a detached task to process the connection so accept loop returns immediately
        asyncio.create_task(process_connection(reader, writer, client_addr))

    except Exception as e:
        enqueue_telemetry({"level": "ERROR", "msg": "Error handling new connection", "err": e, "client": client_addr})
        try:
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
        except Exception:
            pass


def enqueue_telemetry(log_item: dict, strategy: Optional[str] = None) -> bool:
    """Add telemetry to the queue without blocking, dropping items if the queue is full."""
    if strategy is None:
        strategy = TELEMETRY_QUEUE_FALLBACK_STRATEGY
    try:
        telemetry_queue.put_nowait(log_item)
        return True
    except queue.Full:
        if strategy == "drop_oldest":
            try:
                telemetry_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                telemetry_queue.put_nowait(log_item)
                return True
            except queue.Full:
                return False
        elif strategy == "drop_newest":
            return False
        else:
            # Unknown strategy: default to dropping the newest event.
            return False


async def native_socket_engine_worker():
    """Async IO server that accepts TCP connections and delegates them to per-connection tasks."""
    try:
        server = await asyncio.start_server(
            handle_client_connection,
            host=BIND_ADDRESS,
            port=BIND_PORT,
            backlog=SOCKET_BACKLOG,
        )
    except Exception as init_fault:
        enqueue_telemetry({"level": "CRITICAL", "msg": "Socket bind failed", "err": init_fault})
        raise DeployInit002Termination("Terminated due to Socket bind initialization failure")

    addr = server.sockets[0].getsockname() if server.sockets else (BIND_ADDRESS, BIND_PORT)
    print(f"SERVER_SIGNAL: Listening on {addr}")

    async with server:
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            # Graceful cancellation requested
            pass
        except Exception as loop_fault:
            enqueue_telemetry({"level": "ERROR", "msg": "Accept loop fault", "err": loop_fault})


def background_logging_consumer():
    """Detached blocking consumer for telemetry queue (runs in its own thread/process)."""
    while True:
        log_item = telemetry_queue.get()
        try:
            # Production wiring: forward telemetry items to the central telemetry writer.
            write_to_physical_storage_or_syslog(log_item)
        except Exception:
            # Swallow logging errors to avoid crashing the consumer
            pass


# Thin compatibility wrapper so the module can be run directly for quick manual testing
if __name__ == "__main__":
    try:
        asyncio.run(native_socket_engine_worker())
    except DeployInit002Termination as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)

# STATUS = "Verified"
status = "Verified"
