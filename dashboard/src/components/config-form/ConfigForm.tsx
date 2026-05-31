import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { toConfig, toFormValues } from '../../formValues'
import type { Config, FormValues } from '../../types'
import { AliasesSection } from './AliasesSection'
import { FallbacksSection } from './FallbacksSection'
import { GeneralSettingsSection } from './GeneralSettingsSection'
import { PromptCacheSection } from './PromptCacheSection'
import { RoutingRulesSection } from './RoutingRulesSection'

export type FormStatus = { type: 'success' | 'error'; message: string } | null

interface ConfigFormProps {
  config: Config
  reloadRequired: boolean
  status: FormStatus
  onSubmit: (config: Config) => Promise<void>
}

export function ConfigForm({ config, reloadRequired, status, onSubmit }: ConfigFormProps) {
  const { register, handleSubmit, control, reset, setValue } = useForm<FormValues>({
    defaultValues: toFormValues(config),
  })

  useEffect(() => {
    reset(toFormValues(config))
  }, [config, reset])

  async function submitValues(values: FormValues) {
    await onSubmit(toConfig(values))
  }

  return (
    <div className="container">
      <div className="form-banner">
        <h1>Gateway Routing Configuration</h1>
        <p>Define aliases, routing rules, fallbacks, and cache settings for your LLM gateway.</p>
      </div>

      <div className="form-body">
        {reloadRequired && (
          <p className="reload-notice">
            Saved config differs from the active gateway config. Restart the service to apply it.
          </p>
        )}

        <form onSubmit={handleSubmit(submitValues)}>
          <GeneralSettingsSection control={control} register={register} />
          <AliasesSection control={control} register={register} />
          <RoutingRulesSection control={control} register={register} />
          <FallbacksSection control={control} register={register} />
          <PromptCacheSection control={control} register={register} setValue={setValue} />

          <button type="submit" className="btn-submit">
            Save Config
          </button>

          {status && <p className={`status ${status.type}`}>{status.message}</p>}
        </form>
      </div>
    </div>
  )
}
