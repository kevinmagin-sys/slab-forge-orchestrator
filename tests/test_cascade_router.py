html_content = await self.scraper.fetch_raw_html(url)
parsed_data = self.scraper.parse_industrial_specifications(html_content, source_type)import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import routers.cascade as cascade


class DummyPayload:
    def __init__(self, job_id):
        self.job_id = job_id


class CascadeRouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        cascade.router_job_registry.clear()

    async def test_successful_job_transitions(self):
        payload = DummyPayload("job-success")

        async def successful_primary(payload_arg):
            state = cascade.get_router_job_state(payload_arg)
            self.assertEqual(state.state, cascade.JobState.PROCESSING)
            return "primary-ok"

        cascade.call_primary_broker_api = AsyncMock(side_effect=successful_primary)

        # initial state should be pending before route execution
        state = cascade.get_router_job_state(payload)
        self.assertEqual(state.state, cascade.JobState.PENDING)

        result = await cascade.execute_cascade_router(payload)

        self.assertEqual(result, "primary-ok")
        final_state = cascade.get_router_job_state(payload)
        self.assertEqual(final_state.state, cascade.JobState.COMPLETED)
        self.assertEqual(final_state.retries, 1)
        self.assertEqual(final_state.result, "primary-ok")

    async def test_retry_backoff_on_transient_timeout_then_success(self):
        payload = DummyPayload("job-retry")
        mock_sleep = AsyncMock()

        attempts = []

        async def flaky_primary(payload_arg):
            attempts.append(payload_arg)
            if len(attempts) < 3:
                raise asyncio.TimeoutError("temporary timeout")
            return "primary-eventual-success"

        cascade.call_primary_broker_api = AsyncMock(side_effect=flaky_primary)

        with patch.object(cascade.asyncio, "sleep", mock_sleep):
            result = await cascade.execute_cascade_router(payload)

        self.assertEqual(result, "primary-eventual-success")
        final_state = cascade.get_router_job_state(payload)
        self.assertEqual(final_state.state, cascade.JobState.COMPLETED)
        self.assertEqual(final_state.retries, 3)
        self.assertEqual(final_state.result, "primary-eventual-success")

        self.assertEqual(cascade.call_primary_broker_api.call_count, 3)
        mock_sleep.assert_has_awaits([unittest.mock.call(1), unittest.mock.call(2)])


if __name__ == "__main__":
    unittest.main()
