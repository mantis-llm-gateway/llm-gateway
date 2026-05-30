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

  return (
    <>
      <SectionHeading title="General Settings" />

      <div className="field-row">
        <label>Default Model</label>
        <select {...register('default_model')}>
          {aliases.map(alias => (
            <option key={alias.name} value={alias.name}>
              {alias.name}
            </option>
          ))}
        </select>
      </div>

      <div className="field-row">
        <label>Target Retries</label>
        <input type="number" {...register('target_retries', { valueAsNumber: true })} />
      </div>

      <div className="field-row">
        <label>Initial Response Timeout (s)</label>
        <input
          type="number"
          {...register('initial_response_timeout', { valueAsNumber: true })}
        />
      </div>

      <div className="field-row">
        <label>Cooldown TTL (s)</label>
        <input type="number" {...register('cooldown_ttl', { valueAsNumber: true })} />
      </div>
    </>
  )
}
