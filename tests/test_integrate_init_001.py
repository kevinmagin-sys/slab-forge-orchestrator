import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure the module can be imported in test environments without OpenCV or Playwright installed.
if "cv2" not in sys.modules:
    mock_cv2 = MagicMock()
    mock_cv2.error = Exception
    mock_cv2.COLOR_BGR2GRAY = 0
    sys.modules["cv2"] = mock_cv2

if "playwright.async_api" not in sys.modules:
    import types
    mock_playwright_async_api = types.ModuleType("playwright.async_api")
    mock_playwright_async_api.async_playwright = lambda: None
    mock_playwright_async_api.Error = Exception
    sys.modules["playwright.async_api"] = mock_playwright_async_api
    sys.modules["playwright"] = types.ModuleType("playwright")

import importlib
integrate = importlib.import_module("protocols.integrate_init_001")


class IntegrateInit001AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_integrated_execution_pipeline_uses_executor_for_cpu_and_db(self):
        # Build the mock page and browser pipeline.
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.screenshot = AsyncMock()
        mock_page.title = AsyncMock(return_value="test page")

        header_element = MagicMock()
        header_element.text_content = AsyncMock(return_value="header-value")
        footer_element = MagicMock()
        footer_element.text_content = AsyncMock(return_value="footer-value")

        async def query_selector(selector):
            if selector == "h1":
                return header_element
            if selector == "footer":
                return footer_element
            return None

        mock_page.query_selector = AsyncMock(side_effect=query_selector)

        mock_browser_context = MagicMock()
        mock_browser_context.__aenter__ = AsyncMock(return_value=mock_browser_context)
        mock_browser_context.__aexit__ = AsyncMock(return_value=None)
        mock_browser_context.new_page = AsyncMock(return_value=mock_page)

        mock_browser = MagicMock()
        mock_browser.new_context = MagicMock(return_value=mock_browser_context)

        mock_chromium = MagicMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium
        mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_playwright.__aexit__ = AsyncMock(return_value=None)

        def fake_async_playwright():
            return mock_playwright

        cpu_thread_called = False
        db_thread_called = False

        def fake_process_artifact_and_update_state(state_data, artifact_path):
            nonlocal cpu_thread_called
            with self.assertRaisesRegex(RuntimeError, "no running event loop"):
                asyncio.get_running_loop()
            cpu_thread_called = True
            state_data.vision_metrics = 0.42
            return state_data

        def fake_persist_state_data(state_data):
            nonlocal db_thread_called
            with self.assertRaisesRegex(RuntimeError, "no running event loop"):
                asyncio.get_running_loop()
            db_thread_called = True
            state_data.persisted = True

        with patch("protocols.integrate_init_001.async_playwright", new=fake_async_playwright), \
             patch("protocols.integrate_init_001.os.path.exists", return_value=True), \
             patch("protocols.integrate_init_001.process_artifact_and_update_state", new=fake_process_artifact_and_update_state), \
             patch("protocols.integrate_init_001.persist_state_data", new=fake_persist_state_data):

            await integrate.run_integrated_execution_pipeline()

        self.assertTrue(cpu_thread_called, "CPU-bound processing must run in executor thread")
        self.assertTrue(db_thread_called, "DB persistence must run in executor thread")
        self.assertEqual(integrate.state_data.vision_metrics, 0.42)
        self.assertTrue(getattr(integrate.state_data, "persisted", False))


if __name__ == "__main__":
    unittest.main()
