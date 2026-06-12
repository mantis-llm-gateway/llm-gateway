import { useFieldArray, useWatch } from 'react-hook-form'
import type { Control, UseFormRegister } from 'react-hook-form'
import type { FormValues } from '../../types'
import { SectionHeading } from '../SectionHeading'
import { RuleTargetsField } from './RuleTargetsField'

interface RoutingRulesSectionProps {
  control: Control<FormValues>
  register: UseFormRegister<FormValues>
}

export function RoutingRulesSection({ control, register }: RoutingRulesSectionProps) {
  const { fields, append, remove } = useFieldArray({ control, name: 'routing_rules' })
  const rules = useWatch({ control, name: 'routing_rules' }) ?? []

  return (
    <>
      <SectionHeading title="Routing Rules" />
      {fields.map((field, index) => (
        <div key={field.id} className="card">
          <div className="card-header">
            {rules[index]?.id ? (
              <span className="rule-id">Rule {rules[index].id}</span>
            ) : (
              <span className="card-index">Rule {String(index + 1).padStart(2, '0')}</span>
            )}
            <button
              type="button"
              className="btn-remove"
              aria-label="Remove rule"
              onClick={() => remove(index)}
            >
              ✕
            </button>
          </div>
          <div className="field-row">
            <label>Name</label>
            <input
              {...register(`routing_rules.${index}.name`)}
              placeholder="e.g. Code generation"
            />
          </div>
          <div className="field-grid">
            <div className="field-row">
              <label>Match Key</label>
              <input
                className="mono"
                {...register(`routing_rules.${index}.match.name`)}
                placeholder="e.g. task-type"
              />
            </div>
            <div className="field-row">
              <label>Match Value</label>
              <input
                className="mono"
                {...register(`routing_rules.${index}.match.value`)}
                placeholder="e.g. code_generation"
              />
            </div>
          </div>
          <RuleTargetsField ruleIndex={index} control={control} register={register} />
        </div>
      ))}
      <button
        type="button"
        className="btn-add"
        onClick={() =>
          append({
            name: '',
            match: { name: '', value: '' },
            targets: [{ alias: '', weight: 1 }],
          })
        }
      >
        + Add Rule
      </button>
    </>
  )
}
