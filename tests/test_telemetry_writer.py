import os
import json
import queue
import unittest
from sqlalchemy import create_engine, text


# Use a file-backed sqlite DB so the test process and the module share the same DB.
TEST_DB_PATH = "telemetry_test.db"
os.environ["TELEMETRY_DB_URI"] = f"sqlite:///{TEST_DB_PATH}"

import protocols.deploy_init_002 as deploy
from protocols.deploy_init_002 import write_to_physical_storage_or_syslog


class TelemetryWriterTests(unittest.TestCase):
    def setUp(self):
        # Ensure a clean DB file
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    def tearDown(self):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    def test_telemetry_writer_inserts_and_serializes(self):
        # Prepare a sample telemetry item
        item = {
            "level": "INFO",
            "event": "unit_test_event",
            "client": ("127.0.0.1", 54321),
            "bytes": 123,
            "msg": "test payload",
        }

        # Call the writer
        write_to_physical_storage_or_syslog(item)

        # Verify the row exists in the telemetry table
        engine = create_engine(os.environ["TELEMETRY_DB_URI"])
        with engine.connect() as conn:
            res = conn.execute(text("SELECT level, event, client, payload FROM telemetry"))
            rows = list(res.fetchall())
            self.assertEqual(len(rows), 1)
            level, event, client_s, payload_s = rows[0]
            self.assertEqual(level, "INFO")
            self.assertEqual(event, "unit_test_event")
            # client should be JSON-serialized
            client = json.loads(client_s)
            self.assertEqual(client[0], "127.0.0.1")
            self.assertEqual(client[1], 54321)
            payload = json.loads(payload_s)
            self.assertEqual(payload.get("bytes"), 123)
            self.assertEqual(payload.get("msg"), "test payload")

    def test_telemetry_queue_overflow_strategies(self):
        original_queue = deploy.telemetry_queue
        original_strategy = deploy.TELEMETRY_QUEUE_FALLBACK_STRATEGY

        try:
            deploy.telemetry_queue = queue.Queue(maxsize=10)
            deploy.TELEMETRY_QUEUE_FALLBACK_STRATEGY = "drop_oldest"

            for i in range(15):
                deploy.enqueue_telemetry({"msg": f"event-{i}", "index": i})

            items = []
            while not deploy.telemetry_queue.empty():
                items.append(deploy.telemetry_queue.get_nowait())

            self.assertEqual(len(items), 10)
            self.assertEqual(items[0]["index"], 5)
            self.assertEqual(items[-1]["index"], 14)

            # Reset queue and verify drop_newest behavior
            deploy.telemetry_queue = queue.Queue(maxsize=10)
            deploy.TELEMETRY_QUEUE_FALLBACK_STRATEGY = "drop_newest"

            for i in range(10):
                added = deploy.enqueue_telemetry({"msg": f"event-{i}", "index": i})
                self.assertTrue(added)

            dropped_results = [deploy.enqueue_telemetry({"msg": f"event-{i}", "index": i}) for i in range(10, 15)]
            self.assertTrue(all(result is False for result in dropped_results))

            items = []
            while not deploy.telemetry_queue.empty():
                items.append(deploy.telemetry_queue.get_nowait())

            self.assertEqual(len(items), 10)
            self.assertEqual(items[0]["index"], 0)
            self.assertEqual(items[-1]["index"], 9)

        finally:
            deploy.telemetry_queue = original_queue
            deploy.TELEMETRY_QUEUE_FALLBACK_STRATEGY = original_strategy

