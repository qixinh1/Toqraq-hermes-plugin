/** Side-effect-free reads of untrusted Desktop transport values. */

import type { SizeValue } from '../contracts/generated.js'
import { SizeValueRules } from '../contracts/runtimeRules.js'

const CONTROL_CHARACTER = /\p{C}/u

interface RecordRule {
  readonly requiredKeys: readonly string[]
  readonly optionalKeys: readonly string[]
}

export interface StringRule {
  readonly kind: 'string'
  readonly minimumLength?: number
  readonly maximumLength?: number
  readonly pattern?: RegExp
}

interface NumericBounds {
  readonly minimum?: number
  readonly maximum?: number
  readonly exclusiveMinimum?: number
  readonly exclusiveMaximum?: number
}

interface IntegerRule extends NumericBounds {
  readonly kind: 'integer'
}

interface FiniteNumberRule extends NumericBounds {
  readonly kind: 'number'
}

export interface CollectionRule {
  readonly kind: 'array'
  readonly minimumItems?: number
  readonly maximumItems: number
}

export interface StringCollectionRule extends CollectionRule {
  readonly items: StringRule
}

export interface StringEnumRule<T extends string> {
  readonly values: readonly T[]
}

/**
 * Copy only own data properties from an ordinary record.
 * Accessors, symbols, inherited properties, and unsafe keys are rejected.
 */
export function dataRecord(value: unknown): Readonly<Record<string, unknown>> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  try {
    const prototype = Object.getPrototypeOf(value)
    if (prototype !== Object.prototype && prototype !== null) return null
    if (Object.getOwnPropertySymbols(value).length !== 0) return null
    const descriptors = Object.getOwnPropertyDescriptors(value)
    const result: Record<string, unknown> = Object.create(null)
    for (const [key, descriptor] of Object.entries(descriptors)) {
      if (!safeKey(key) || !Object.hasOwn(descriptor, 'value')) return null
      result[key] = descriptor.value
    }
    return Object.freeze(result)
  } catch {
    return null
  }
}

/** Copy a bounded dense ordinary array without invoking accessors or iterators. */
export function dataArray(value: unknown, maximumItems: number): ReadonlyArray<unknown> | null {
  if (!Array.isArray(value)) return null
  try {
    const lengthDescriptor = Object.getOwnPropertyDescriptor(value, 'length')
    if (!lengthDescriptor || !Object.hasOwn(lengthDescriptor, 'value')) return null
    const length: unknown = lengthDescriptor.value
    if (
      typeof length !== 'number' ||
      !Number.isSafeInteger(length) ||
      length < 0 ||
      length > maximumItems
    ) {
      return null
    }
    const descriptors = Object.getOwnPropertyDescriptors(value)
    const keys = Object.keys(descriptors).filter((key) => key !== 'length')
    if (keys.length !== length || Object.getOwnPropertySymbols(value).length !== 0) return null
    const result: unknown[] = []
    for (let index = 0; index < length; index += 1) {
      const descriptor = descriptors[String(index)]
      if (!descriptor || !descriptor.enumerable || !Object.hasOwn(descriptor, 'value')) return null
      result.push(descriptor.value)
    }
    return Object.freeze(result)
  } catch {
    return null
  }
}

export function recordValue(
  value: unknown,
  rule: RecordRule,
  name: string,
): Readonly<Record<string, unknown>> {
  const source = dataRecord(value)
  if (!source) invalid(name)
  const keys = Object.keys(source)
  if (
    rule.requiredKeys.some((key) => !Object.hasOwn(source, key)) ||
    keys.some(
      (key) => !rule.requiredKeys.includes(key) && !rule.optionalKeys.includes(key),
    )
  ) {
    invalid(name)
  }
  return source
}

export function hasExactKeys(
  value: Readonly<Record<string, unknown>>,
  expected: readonly string[],
): boolean {
  return (
    Object.keys(value).length === expected.length &&
    expected.every((key) => Object.hasOwn(value, key))
  )
}

export function safeKey(key: string): boolean {
  return (
    key.length > 0 &&
    !CONTROL_CHARACTER.test(key) &&
    key !== '__proto__' &&
    key !== 'prototype' &&
    key !== 'constructor'
  )
}

export function codePointLength(value: string): number {
  return Array.from(value).length
}

export function stringValue(value: unknown, rule: StringRule, name: string): string {
  if (typeof value !== 'string') invalid(name)
  const length = codePointLength(value)
  if (
    (rule.minimumLength !== undefined && length < rule.minimumLength) ||
    (rule.maximumLength !== undefined && length > rule.maximumLength) ||
    (rule.pattern !== undefined && !rule.pattern.test(value))
  ) {
    invalid(name)
  }
  return value
}

export function nullableStringValue(
  value: unknown,
  rule: StringRule,
  name: string,
): string | null {
  return value === null ? null : stringValue(value, rule, name)
}

export function enumValue<const T extends string>(
  value: unknown,
  rule: StringEnumRule<T>,
  name: string,
): T {
  if (typeof value !== 'string') invalid(name)
  const match = rule.values.find((candidate) => candidate === value)
  if (match === undefined) invalid(name)
  return match
}

export function booleanValue(value: unknown, name: string): boolean {
  if (typeof value !== 'boolean') invalid(name)
  return value
}

export function numberValue(value: unknown, rule: FiniteNumberRule, name: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || !withinBounds(value, rule)) {
    invalid(name)
  }
  return value
}

export function integerValue(value: unknown, rule: IntegerRule, name: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || !withinBounds(value, rule)) {
    invalid(name)
  }
  return value
}

export function arrayValue(
  value: unknown,
  rule: CollectionRule,
  name: string,
): readonly unknown[] {
  const source = dataArray(value, rule.maximumItems)
  if (!source || (rule.minimumItems !== undefined && source.length < rule.minimumItems)) {
    invalid(name)
  }
  return source
}

export function stringArrayValue(
  value: unknown,
  rule: StringCollectionRule,
  name: string,
): readonly string[] {
  return Object.freeze(arrayValue(value, rule, name).map((item) => stringValue(item, rule.items, name)))
}

export function decodeSize(value: unknown): SizeValue {
  const source = recordValue(value, SizeValueRules, 'size')
  return Object.freeze({
    width: integerValue(source.width, SizeValueRules.width, 'width'),
    height: integerValue(source.height, SizeValueRules.height, 'height'),
  })
}

export function invalid(name: string): never {
  throw new TypeError(`invalid Toqraq ${name}`)
}

function withinBounds(value: number, rule: NumericBounds): boolean {
  return !(
    (rule.minimum !== undefined && value < rule.minimum) ||
    (rule.maximum !== undefined && value > rule.maximum) ||
    (rule.exclusiveMinimum !== undefined && value <= rule.exclusiveMinimum) ||
    (rule.exclusiveMaximum !== undefined && value >= rule.exclusiveMaximum)
  )
}
