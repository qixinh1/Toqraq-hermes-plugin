import assert from 'node:assert/strict'
import test from 'node:test'
import { absoluteWorkspace } from './workspace.js'

test('workspace projection accepts absolute host roots', () => {
  assert.equal(absoluteWorkspace('D:\\game'), 'D:\\game')
  assert.equal(absoluteWorkspace('C:/game'), 'C:/game')
  assert.equal(absoluteWorkspace('\\\\server\\share\\game'), '\\\\server\\share\\game')
  assert.equal(absoluteWorkspace('/workspace/game'), '/workspace/game')
})

test('workspace projection rejects transient and relative host values', () => {
  for (const value of [null, undefined, '', '   ', '.', '..', 'game', 'games/project']) {
    assert.equal(absoluteWorkspace(value), '')
  }
})
