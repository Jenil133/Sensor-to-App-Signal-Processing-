import { openDB } from 'idb'
import type { IDBPDatabase } from 'idb'

let dbp: Promise<IDBPDatabase> | null = null
const db = () =>
  (dbp ??= openDB('baseline-sync', 1, {
    upgrade(d) {
      d.createObjectStore('outbox', { keyPath: 'id', autoIncrement: true })
    },
  }))

export interface OutboxItem {
  id?: number
  createdAt: number
  deviceToken: string
  batch: unknown // byte-for-byte a valid /ingest body
}

export async function enqueue(item: Omit<OutboxItem, 'id'>) {
  await (await db()).add('outbox', item)
}

export async function count(): Promise<number> {
  return (await db()).count('outbox')
}

export async function peekAll(): Promise<OutboxItem[]> {
  return (await db()).getAll('outbox')
}

export async function remove(id: number) {
  await (await db()).delete('outbox', id)
}
