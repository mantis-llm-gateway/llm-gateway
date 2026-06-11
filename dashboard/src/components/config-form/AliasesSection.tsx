import { useFieldArray } from 'react-hook-form'
import type { Control, UseFormRegister } from 'react-hook-form'
import type { FormValues } from '../../types'
import { SectionHeading } from '../SectionHeading'

interface AliasesSectionProps {
  control: Control<FormValues>
  register: UseFormRegister<FormValues>
}

export function AliasesSection({ control, register }: AliasesSectionProps) {
  const { fields, append, remove } = useFieldArray({ control, name: 'aliases' })

  return (
    <>
      <SectionHeading title="Aliases" />
      {fields.map((field, index) => (
        <div key={field.id} className="card">
          <div className="card-header">
            <span className="card-index">Alias {String(index + 1).padStart(2, '0')}</span>
            <button
              type="button"
              className="btn-remove"
              aria-label="Remove alias"
              onClick={() => remove(index)}
            >
              ✕
            </button>
          </div>
          <div className="field-row">
            <label>Name</label>
            <input {...register(`aliases.${index}.name`)} placeholder="e.g. Claude Sonnet" />
          </div>
          <div className="field-row">
            <label>Provider</label>
            <input
              className="mono"
              {...register(`aliases.${index}.provider`)}
              placeholder="e.g. bedrock"
            />
          </div>
          <div className="field-row">
            <label>Model ID</label>
            <input
              className="mono"
              {...register(`aliases.${index}.model`)}
              placeholder="e.g. us.anthropic.claude-sonnet-4-5-..."
            />
          </div>
        </div>
      ))}
      <button
        type="button"
        className="btn-add"
        onClick={() => append({ name: '', provider: '', model: '' })}
      >
        + Add Alias
      </button>
    </>
  )
}
