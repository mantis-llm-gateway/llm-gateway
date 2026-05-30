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

  return (
    <>
      <SectionHeading title="Fallbacks" />
      {fields.map((field, index) => (
        <div key={field.id} className="field-row">
          <select {...register(`fallbacks.${index}.value`)}>
            {aliases.map(alias => (
              <option key={alias.name} value={alias.name}>
                {alias.name}
              </option>
            ))}
          </select>
          <button type="button" className="btn-remove" onClick={() => remove(index)}>
            Remove
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
    </>
  )
}
