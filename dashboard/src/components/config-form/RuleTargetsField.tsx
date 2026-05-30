import { useFieldArray } from 'react-hook-form'
import type { Control, UseFormRegister } from 'react-hook-form'
import type { FormValues } from '../../types'

interface RuleTargetsFieldProps {
  ruleIndex: number
  control: Control<FormValues>
  register: UseFormRegister<FormValues>
}

export function RuleTargetsField({ ruleIndex, control, register }: RuleTargetsFieldProps) {
  const { fields, append, remove } = useFieldArray({
    control,
    name: `routing_rules.${ruleIndex}.targets`,
  })

  return (
    <div className="targets-section">
      <h4>Targets</h4>
      {fields.map((field, index) => (
        <div key={field.id} className="field-row">
          <input
            {...register(`routing_rules.${ruleIndex}.targets.${index}.alias`)}
            placeholder="Alias name"
          />
          <input
            {...register(`routing_rules.${ruleIndex}.targets.${index}.weight`, {
              valueAsNumber: true,
            })}
            type="number"
            placeholder="Weight"
            style={{ maxWidth: 80 }}
          />
          <button type="button" className="btn-remove" onClick={() => remove(index)}>
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
