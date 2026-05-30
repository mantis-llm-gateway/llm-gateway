import { useWatch } from 'react-hook-form'
import type { Control, UseFormRegister, UseFormSetValue } from 'react-hook-form'
import type { FormValues } from '../../types'
import { SectionHeading } from '../SectionHeading'

interface PromptCacheSectionProps {
  control: Control<FormValues>
  register: UseFormRegister<FormValues>
  setValue: UseFormSetValue<FormValues>
}

export function PromptCacheSection({ control, register, setValue }: PromptCacheSectionProps) {
  const semantic = useWatch({ control, name: 'prompt_cache.semantic' })

  return (
    <>
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
            checked={semantic !== null && semantic !== undefined}
            onChange={event => {
              if (event.target.checked) {
                setValue('prompt_cache.semantic', {
                  similarity_threshold: 0.8,
                  top_k: 3,
                  conversation_size_threshold: 3,
                })
              } else {
                setValue('prompt_cache.semantic', null)
              }
            }}
          />{' '}
          Enable Semantic Cache
        </label>
      </div>

      {semantic && (
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
    </>
  )
}
