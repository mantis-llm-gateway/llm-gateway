import { useWatch } from 'react-hook-form'
import type { Control, UseFormRegister } from 'react-hook-form'
import type { FormValues } from '../../types'
import { SectionHeading } from '../SectionHeading'

interface GeneralSettingsSectionProps {
  control: Control<FormValues>
  register: UseFormRegister<FormValues>
}

export function GeneralSettingsSection({ control, register }: GeneralSettingsSectionProps) {
  const aliases = useWatch({ control, name: 'aliases' }) ?? []
  const defaultModel = useWatch({ control, name: 'default_model' })
  const defaultModelIsMissing = defaultModel && !aliases.some(alias => alias.name === defaultModel)

  return (
    <>
      <SectionHeading title="General Settings" />

      <div className="card">
        <div className="field-row">
          <label>Default Model</label>
          <select {...register('default_model')}>
            {defaultModelIsMissing && (
              <option value={defaultModel}>{defaultModel} (missing alias)</option>
            )}
            {aliases.map(alias => (
              <option key={alias.name} value={alias.name}>
                {alias.name}
              </option>
            ))}
          </select>
        </div>

        <div className="num-grid">
          <div className="field-row">
            <label>Target Retries</label>
            <input type="number" {...register('target_retries', { valueAsNumber: true })} />
          </div>

          <div className="field-row">
            <label>Initial Response Timeout</label>
            <div className="num-field" data-unit="s">
              <input
                type="number"
                {...register('initial_response_timeout', { valueAsNumber: true })}
              />
            </div>
          </div>

          <div className="field-row">
            <label>Stream Idle Timeout</label>
            <div className="num-field" data-unit="s">
              <input type="number" {...register('stream_idle_timeout', { valueAsNumber: true })} />
            </div>
          </div>

          <div className="field-row">
            <label>Cooldown TTL</label>
            <div className="num-field" data-unit="s">
              <input type="number" {...register('cooldown_ttl', { valueAsNumber: true })} />
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
