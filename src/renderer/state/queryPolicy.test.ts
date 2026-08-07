import assert from 'node:assert/strict'
import test from 'node:test'
import {
  COMPONENT_QUERY_RETRY_COUNT,
  HERMES_SESSION_ERROR_REFRESH_INTERVAL_MS,
  SETUP_QUERY_RETRY_COUNT,
  SETUP_QUERY_RETRY_DELAY_MS,
} from './queryPolicy.js'

test('renderer query policy keeps retries and refreshes bounded', () => {
  assert.equal(COMPONENT_QUERY_RETRY_COUNT, 2)
  assert.equal(HERMES_SESSION_ERROR_REFRESH_INTERVAL_MS, 3_000)
  assert.equal(SETUP_QUERY_RETRY_COUNT, 2)
  assert.equal(SETUP_QUERY_RETRY_DELAY_MS, 1_000)
  assert.ok(SETUP_QUERY_RETRY_COUNT >= 0)
  assert.ok(COMPONENT_QUERY_RETRY_COUNT >= 0)
  assert.ok(SETUP_QUERY_RETRY_DELAY_MS > 0)
  assert.ok(HERMES_SESSION_ERROR_REFRESH_INTERVAL_MS > SETUP_QUERY_RETRY_DELAY_MS)
})
