import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toConfig, toFormValues } from "../../formValues";
import type { Config, FormValues } from "../../types";
import { AliasesSection } from "./AliasesSection";
import { FallbacksSection } from "./FallbacksSection";
import { GeneralSettingsSection } from "./GeneralSettingsSection";
import { PromptCacheSection } from "./PromptCacheSection";
import { RoutingRulesSection } from "./RoutingRulesSection";

export type FormStatus = { type: "success" | "error"; message: string } | null;

interface ConfigFormProps {
  config: Config;
  reloadRequired: boolean;
  status: FormStatus;
  onSubmit: (config: Config) => Promise<void>;
}

const TABS = [
  { id: "general", label: "General" },
  { id: "aliases", label: "Aliases" },
  { id: "rules", label: "Routing Rules" },
  { id: "fallbacks", label: "Fallbacks" },
  { id: "cache", label: "Prompt Cache" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function ConfigForm({
  config,
  reloadRequired,
  status,
  onSubmit,
}: ConfigFormProps) {
  const {
    register,
    handleSubmit,
    control,
    reset,
    setValue,
    formState: { isDirty },
  } = useForm<FormValues>({
    defaultValues: toFormValues(config),
  });

  const [activeTab, setActiveTab] = useState<TabId>("general");

  useEffect(() => {
    reset(toFormValues(config));
  }, [config, reset]);

  const aliases = useWatch({ control, name: "aliases" });
  const routingRules = useWatch({ control, name: "routing_rules" });
  const fallbacks = useWatch({ control, name: "fallbacks" });
  const counts: Partial<Record<TabId, number>> = {
    aliases: aliases?.length ?? 0,
    rules: routingRules?.length ?? 0,
    fallbacks: fallbacks?.length ?? 0,
  };

  async function submitValues(values: FormValues) {
    await onSubmit(toConfig(values));
  }

  return (
    <div className="container">
      <div className="form-banner">
        <h1>Gateway Routing Configuration</h1>
        <p>
          Define aliases, routing rules, fallbacks, and cache settings for your
          LLM gateway.
        </p>
      </div>

      <div className="form-body">
        {reloadRequired && (
          <p className="reload-notice">
            Saved config differs from the active gateway config. Restart the
            service to apply it.
          </p>
        )}

        <div className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`tab ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
              {counts[tab.id] !== undefined && (
                <span className="tab-count">{counts[tab.id]}</span>
              )}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit(submitValues)}>
          <div hidden={activeTab !== "general"}>
            <GeneralSettingsSection control={control} register={register} />
          </div>
          <div hidden={activeTab !== "aliases"}>
            <AliasesSection control={control} register={register} />
          </div>
          <div hidden={activeTab !== "rules"}>
            <RoutingRulesSection control={control} register={register} />
          </div>
          <div hidden={activeTab !== "fallbacks"}>
            <FallbacksSection control={control} register={register} />
          </div>
          <div hidden={activeTab !== "cache"}>
            <PromptCacheSection
              control={control}
              register={register}
              setValue={setValue}
            />
          </div>

          <div className="form-footer">
            <div className="form-footer__status">
              {isDirty ? (
                <span className="unsaved">
                  <span className="unsaved-dot" />
                  Unsaved Changes
                </span>
              ) : status ? (
                <span className={`status ${status.type}`}>
                  {status.message}
                </span>
              ) : null}
            </div>
            <button type="submit" className="btn-submit">
              Save Config
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
