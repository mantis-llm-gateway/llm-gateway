import { useEffect, useState } from 'react'
import { fetchConfig, submitConfig } from './api'
import './App.css'
import { ConfigForm } from './components/config-form/ConfigForm'
import type { FormStatus } from './components/config-form/ConfigForm'
import { Header } from './components/Header'
import type { Config } from './types'

export default function App() {
  const [config, setConfig] = useState<Config | null>(null)
  const [loading, setLoading] = useState(true)
  const [reloadRequired, setReloadRequired] = useState(false)
  const [status, setStatus] = useState<FormStatus>(null)

  useEffect(() => {
    fetchConfig()
      .then(response => {
        setConfig(response.config)
        setReloadRequired(response.reload_required)
      })
      .catch(e => setStatus({ type: 'error', message: (e as Error).message }))
      .finally(() => setLoading(false))
  }, [])

  async function saveConfig(updatedConfig: Config) {
    setStatus(null)
    try {
      const response = await submitConfig(updatedConfig)
      setConfig(response.config)
      setReloadRequired(response.reload_required)
      setStatus({
        type: 'success',
        message: response.reload_required
          ? 'Config saved. Restart the gateway to load these changes.'
          : 'Config saved successfully.',
      })
    } catch (e) {
      setStatus({ type: 'error', message: (e as Error).message })
    }
  }

  return (
    <>
      <Header />
      <div className="page">
        {loading ? (
          <p className="loading">Loading config…</p>
        ) : config ? (
          <ConfigForm
            config={config}
            reloadRequired={reloadRequired}
            status={status}
            onSubmit={saveConfig}
          />
        ) : (
          <p>
            {status?.type === 'error'
              ? status.message
              : 'Could not load the dashboard. Please try again...'}
          </p>
        )}
      </div>
    </>
  )
}
