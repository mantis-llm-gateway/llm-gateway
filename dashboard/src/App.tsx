import { useEffect, useState } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import type { Control, UseFormRegister } from 'react-hook-form'
import type { FormValues, Config } from './types'
import { fetchConfig, submitConfig } from './api'
import './App.css'

function toFormValues(config: Config): FormValues {
  return {
    aliases: Object.entries(config.aliases).map(([name, { provider, model }]) => ({
      name,
      provider,
      model,
    })),
    routing_rules: config.routing_rules,
    target_retries: config.target_retries,
    fallbacks: config.fallbacks.map(v => ({ value: v })),
    initial_response_timeout: config.initial_response_timeout,
    default_model: config.default_model,
    cooldown_ttl: config.cooldown_ttl,
    prompt_cache: config.prompt_cache,
  }
}

function toConfig(values: FormValues): Config {
  return {
    aliases: Object.fromEntries(
      values.aliases.map(({ name, provider, model }) => [name, { provider, model }])
    ),
    routing_rules: values.routing_rules.map(rule => ({
      ...rule,
      targets: rule.targets.map(t => ({ ...t, weight: Number(t.weight) })),
    })),
    target_retries: Number(values.target_retries),
    fallbacks: values.fallbacks.map(f => f.value),
    initial_response_timeout: Number(values.initial_response_timeout),
    default_model: values.default_model,
    cooldown_ttl: Number(values.cooldown_ttl),
    prompt_cache: {
      ttl_seconds: Number(values.prompt_cache.ttl_seconds),
      temperature_threshold: Number(values.prompt_cache.temperature_threshold),
      semantic: values.prompt_cache.semantic
        ? {
            similarity_threshold: Number(values.prompt_cache.semantic.similarity_threshold),
            top_k: Number(values.prompt_cache.semantic.top_k),
            conversation_size_threshold: Number(
              values.prompt_cache.semantic.conversation_size_threshold
            ),
          }
        : null,
    },
  }
}

interface RuleTargetsFieldProps {
  ruleIndex: number
  control: Control<FormValues>
  register: UseFormRegister<FormValues>
}

function RuleTargetsField({ ruleIndex, control, register }: RuleTargetsFieldProps) {
  const { fields, append, remove } = useFieldArray({
    control,
    name: `routing_rules.${ruleIndex}.targets`,
  })

  return (
    <div className="targets-section">
      <h4>Targets</h4>
      {fields.map((field, i) => (
        <div key={field.id} className="field-row">
          <input
            {...register(`routing_rules.${ruleIndex}.targets.${i}.alias`)}
            placeholder="Alias name"
          />
          <input
            {...register(`routing_rules.${ruleIndex}.targets.${i}.weight`, {
              valueAsNumber: true,
            })}
            type="number"
            placeholder="Weight"
            style={{ maxWidth: 80 }}
          />
          <button type="button" className="btn-remove" onClick={() => remove(i)}>
            Remove
          </button>
        </div>
      ))}
      <button type="button" className="btn-add" onClick={() => append({ alias: '', weight: 1 })}>
        + Add Target
      </button>
    </div>
  )
}

function SectionHeading({ title }: { title: string }) {
  return (
    <div className="section-heading">
      <span className="section-dot" />
      <h2>{title}</h2>
    </div>
  )
}

export default function App() {
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(
    null
  )

  const { register, handleSubmit, control, reset, watch, setValue } = useForm<FormValues>()

  const { fields: aliasFields, append: appendAlias, remove: removeAlias } = useFieldArray({
    control,
    name: 'aliases',
  })

  const { fields: ruleFields, append: appendRule, remove: removeRule } = useFieldArray({
    control,
    name: 'routing_rules',
  })

  const {
    fields: fallbackFields,
    append: appendFallback,
    remove: removeFallback,
  } = useFieldArray({ control, name: 'fallbacks' })

  const watchedAliases = watch('aliases') ?? []
  const watchedRules = watch('routing_rules') ?? []
  const watchedSemantic = watch('prompt_cache.semantic')

  useEffect(() => {
    fetchConfig()
      .then(config => reset(toFormValues(config)))
      .catch(e => setStatus({ type: 'error', message: e.message }))
      .finally(() => setLoading(false))
  }, [reset])

  async function onSubmit(values: FormValues) {
    setStatus(null)
    try {
      const updated = await submitConfig(toConfig(values))
      reset(toFormValues(updated))
      setStatus({ type: 'success', message: 'Config saved successfully.' })
    } catch (e) {
      setStatus({ type: 'error', message: (e as Error).message })
    }
  }

  return (
    <>
      <header className="header">
        <div className="header-logo">
          <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 1 L13 5 L13 11 L8 15 L3 11 L3 5 Z" />
          </svg>
        </div>
        <span className="header-name">Mantis</span>
        <span className="header-sep" />
        <span className="header-sub">Routing Config</span>
      </header>

      <div className="page">
        {loading ? (
          <p className="loading">Loading config…</p>
        ) : (
          <div className="container">
            <div className="form-banner">
              <h1>Gateway Routing Configuration</h1>
              <p>Define aliases, routing rules, fallbacks, and cache settings for your LLM gateway.</p>
            </div>

            <div className="form-body">
              <form onSubmit={handleSubmit(onSubmit)}>

                {/* ── General Settings ───────────────────────────── */}
                <SectionHeading title="General Settings" />

                <div className="field-row">
                  <label>Default Model</label>
                  <select {...register('default_model')}>
                    {watchedAliases.map(a => (
                      <option key={a.name} value={a.name}>{a.name}</option>
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

                {/* ── Aliases ────────────────────────────────────── */}
                <SectionHeading title="Aliases" />
                {aliasFields.map((field, i) => (
                  <div key={field.id} className="card">
                    <div className="field-row">
                      <label>Name</label>
                      <input {...register(`aliases.${i}.name`)} placeholder="e.g. Claude Sonnet" />
                      <button type="button" className="btn-remove" onClick={() => removeAlias(i)}>
                        Remove
                      </button>
                    </div>
                    <div className="field-row">
                      <label>Provider</label>
                      <input {...register(`aliases.${i}.provider`)} placeholder="e.g. bedrock" />
                    </div>
                    <div className="field-row">
                      <label>Model ID</label>
                      <input
                        {...register(`aliases.${i}.model`)}
                        placeholder="e.g. us.anthropic.claude-sonnet-4-5-..."
                      />
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  className="btn-add"
                  onClick={() => appendAlias({ name: '', provider: '', model: '' })}
                >
                  + Add Alias
                </button>

                {/* ── Routing Rules ──────────────────────────────── */}
                <SectionHeading title="Routing Rules" />
                {ruleFields.map((field, i) => (
                  <div key={field.id} className="card">
                    <div className="field-row">
                      {watchedRules[i]?.id && (
                        <>
                          <label>Rule ID</label>
                          <span className="rule-id">{watchedRules[i].id}</span>
                        </>
                      )}
                      <button type="button" className="btn-remove" onClick={() => removeRule(i)}>
                        Remove Rule
                      </button>
                    </div>
                    <div className="field-row">
                      <label>Name</label>
                      <input
                        {...register(`routing_rules.${i}.name`)}
                        placeholder="e.g. Code generation"
                      />
                    </div>
                    <div className="field-row">
                      <label>Match Key</label>
                      <input
                        {...register(`routing_rules.${i}.match.name`)}
                        placeholder="e.g. task-type"
                      />
                    </div>
                    <div className="field-row">
                      <label>Match Value</label>
                      <input
                        {...register(`routing_rules.${i}.match.value`)}
                        placeholder="e.g. code_generation"
                      />
                    </div>
                    <RuleTargetsField ruleIndex={i} control={control} register={register} />
                  </div>
                ))}
                <button
                  type="button"
                  className="btn-add"
                  onClick={() =>
                    appendRule({
                      name: '',
                      match: { name: '', value: '' },
                      targets: [{ alias: '', weight: 1 }],
                    })
                  }
                >
                  + Add Rule
                </button>

                {/* ── Fallbacks ──────────────────────────────────── */}
                <SectionHeading title="Fallbacks" />
                {fallbackFields.map((field, i) => (
                  <div key={field.id} className="field-row">
                    <select {...register(`fallbacks.${i}.value`)}>
                      {watchedAliases.map(a => (
                        <option key={a.name} value={a.name}>{a.name}</option>
                      ))}
                    </select>
                    <button type="button" className="btn-remove" onClick={() => removeFallback(i)}>
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="btn-add"
                  onClick={() => appendFallback({ value: watchedAliases[0]?.name ?? '' })}
                >
                  + Add Fallback
                </button>

                {/* ── Prompt Cache ───────────────────────────────── */}
                <SectionHeading title="Prompt Cache" />

                <div className="field-row">
                  <label>TTL (s)</label>
                  <input
                    type="number"
                    {...register('prompt_cache.ttl_seconds', { valueAsNumber: true })}
                  />
                </div>

                <div className="field-row">
                  <label>Temperature Threshold</label>
                  <input
                    type="number"
                    step="0.01"
                    {...register('prompt_cache.temperature_threshold', { valueAsNumber: true })}
                  />
                </div>

                <div className="field-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={watchedSemantic !== null && watchedSemantic !== undefined}
                      onChange={e => {
                        if (e.target.checked) {
                          setValue('prompt_cache.semantic', {
                            similarity_threshold: 0.8,
                            top_k: 3,
                            conversation_size_threshold: 3,
                          })
                        } else {
                          setValue('prompt_cache.semantic', null)
                        }
                      }}
                    />
                    {' '}Enable Semantic Cache
                  </label>
                </div>

                {watchedSemantic && (
                  <div className="card">
                    <div className="field-row">
                      <label>Similarity Threshold</label>
                      <input
                        type="number"
                        step="0.01"
                        {...register('prompt_cache.semantic.similarity_threshold', {
                          valueAsNumber: true,
                        })}
                      />
                    </div>
                    <div className="field-row">
                      <label>Top K</label>
                      <input
                        type="number"
                        {...register('prompt_cache.semantic.top_k', { valueAsNumber: true })}
                      />
                    </div>
                    <div className="field-row">
                      <label>Conversation Size Threshold</label>
                      <input
                        type="number"
                        {...register('prompt_cache.semantic.conversation_size_threshold', {
                          valueAsNumber: true,
                        })}
                      />
                    </div>
                  </div>
                )}

                <button type="submit" className="btn-submit">Save Config</button>

                {status && <p className={`status ${status.type}`}>{status.message}</p>}
              </form>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
