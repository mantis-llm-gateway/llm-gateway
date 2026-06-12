import { useFieldArray, useWatch } from 'react-hook-form'
import type { Control, UseFormRegister } from 'react-hook-form'
import type { FormValues } from '../../types'
import { SectionHeading } from '../SectionHeading'

interface FallbacksSectionProps {
  control: Control<FormValues>
  register: UseFormRegister<FormValues>
}

export function FallbacksSection({ control, register }: FallbacksSectionProps) {
  const { fields, append, remove } = useFieldArray({ control, name: 'fallbacks' })
  const aliases = useWatch({ control, name: 'aliases' }) ?? []
  const fallbacks = useWatch({ control, name: 'fallbacks' }) ?? []

  return (
    <>
      <SectionHeading title="Fallbacks" />
      <div className="card">
        {fields.map((field, index) => (
          <div key={field.id} className="field-row fallback-row">
            <span className="fallback-num">{index + 1}</span>
            <select {...register(`fallbacks.${index}.value`)}>
              {fallbacks[index]?.value &&
                !aliases.some(alias => alias.name === fallbacks[index].value) && (
                  <option value={fallbacks[index].value}>
                    {fallbacks[index].value} (missing alias)
                  </option>
                )}
              {aliases.map(alias => (
                <option key={alias.name} value={alias.name}>
                  {alias.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn-remove"
              aria-label="Remove fallback"
              onClick={() => remove(index)}
            >
              ✕
            </button>
          </div>
        ))}
        <button
          type="button"
          className="btn-add"
          onClick={() => append({ value: aliases[0]?.name ?? '' })}
        >
          + Add Fallback
        </button>
      </div>
    </>
  )
}
