import assert from 'node:assert/strict'
import test from 'node:test'
import { SessionOperations } from './sessionOperations.js'

test('one Hermes session owns at most one lifecycle operation', () => {
  const owner = new SessionOperations()
  owner.select('session-a')
  const first = owner.begin('session-a')

  assert.ok(first)
  assert.equal(owner.begin('session-a'), null)
  assert.equal(owner.busy(), true)
  assert.equal(owner.finish(first), true)
  assert.equal(owner.busy(), false)
  assert.equal(owner.finish(first), false)
})

test('an old operation cannot clear another selected session operation', () => {
  const owner = new SessionOperations()
  owner.select('session-a')
  const operationA = owner.begin('session-a')
  assert.ok(operationA)

  owner.select('session-b')
  const operationB = owner.begin('session-b')
  assert.ok(operationB)
  assert.equal(owner.accepts('session-a'), false)
  assert.equal(owner.accepts('session-b'), true)
  assert.equal(owner.busy(), true)

  assert.equal(owner.finish(operationA), true)
  assert.equal(owner.busy(), true)
  assert.equal(owner.finish(operationB), true)
  assert.equal(owner.busy(), false)
})

test('switching back projects an operation that remained owned by that session', () => {
  const owner = new SessionOperations()
  owner.select('session-a')
  const operationA = owner.begin('session-a')
  assert.ok(operationA)

  owner.select('session-b')
  assert.equal(owner.busy(), false)
  owner.select('session-a')
  assert.equal(owner.busy(), true)
  assert.equal(owner.owns(operationA), true)
})

test('disposing rejects new work and invalidates every retained owner', () => {
  const owner = new SessionOperations()
  owner.select('session-a')
  const operation = owner.begin('session-a')
  assert.ok(operation)

  owner.dispose()
  owner.dispose()

  assert.equal(owner.accepts('session-a'), false)
  assert.equal(owner.owns(operation), false)
  assert.equal(owner.finish(operation), false)
  assert.equal(owner.begin('session-a'), null)
  assert.equal(owner.select('session-b'), false)
  assert.equal(owner.busy(), false)
})
