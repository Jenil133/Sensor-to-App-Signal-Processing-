import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api/client'
import type { Device, DeviceWithToken } from '../api/client'

export default function Devices() {
  const [devices, setDevices] = useState<Device[]>([])
  const [name, setName] = useState('')
  const [revealed, setRevealed] = useState<DeviceWithToken | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setDevices(await api<Device[]>('/devices'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to load')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const device = await api<DeviceWithToken>('/devices', {
        method: 'POST',
        body: JSON.stringify({ name }),
      })
      setRevealed(device)
      setName('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to create')
    }
  }

  return (
    <div>
      <h1 className="page-title">Devices</h1>
      <form className="device-form" onSubmit={create}>
        <input
          placeholder="device name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={80}
          required
        />
        <button className="btn-primary" type="submit">
          Create device
        </button>
      </form>
      {error && <div className="error-note">{error}</div>}
      {revealed && (
        <div className="token-reveal">
          <div className="token-warn">
            <span aria-hidden>⚠</span>
            {revealed.name} token — shown only once, copy it now
          </div>
          <code>{revealed.device_token}</code>
          <br />
          <br />
          Feed it data with the simulator:
          <br />
          <code>
            python -m simulator.run --api http://localhost:8000 --device-token{' '}
            {revealed.device_token} --days 30 --seed 42 --start 2026-07-01
            --inject-shift-day 25
          </code>
        </div>
      )}
      <div className="card">
        <table className="devices">
          <thead>
            <tr>
              <th>Name</th>
              <th>Created</th>
              <th>Last seen</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td>{d.created_at.slice(0, 10)}</td>
                <td>
                  {d.last_seen_at
                    ? d.last_seen_at.replace('T', ' ').slice(0, 16)
                    : 'never'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
