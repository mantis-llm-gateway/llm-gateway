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
    <div className="subgroup">
      <div className="subgroup-head">Targets</div>
      <div className="target-head">
        <span>Alias</span>
        <span>Weight</span>
        <span></span>
      </div>
      {fields.map((field, index) => (
        <div key={field.id} className="target-row">
          <input
            {...register(`routing_rules.${ruleIndex}.targets.${index}.alias`)}
            placeholder="alias name"
          />
          <input
            type="number"
            {...register(`routing_rules.${ruleIndex}.targets.${index}.weight`, {
              valueAsNumber: true,
            })}
            placeholder="1"
          />
          <button
            type="button"
            className="btn-remove"
            aria-label="Remove target"
            onClick={() => remove(index)}
          >
            ✕
          </button>
        </div>
      ))}
      <button type="button" className="btn-add" onClick={() => append({ alias: '', weight: 1 })}>
        + Add Target
      </button>
    </div>
  )
}
