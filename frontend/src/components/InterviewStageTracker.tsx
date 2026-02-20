import { Check, X } from "lucide-react";
import { useUpdateInterviewStages } from "../hooks/useApplications";
import type { Application, InterviewStageUpdate, StageKey } from "../lib/types";

const STAGES: { key: StageKey; label: string }[] = [
  { key: "phone_screen", label: "Phone" },
  { key: "assessment",   label: "Assessment" },
  { key: "technical",    label: "Technical" },
];

// State cycle: pending → done → missed → pending
type StageState = "pending" | "done" | "missed";

function getState(app: Application, key: StageKey): StageState {
  if (app[`${key}_completed` as keyof Application]) return "done";
  if (app[`${key}_missed` as keyof Application]) return "missed";
  return "pending";
}

function nextState(current: StageState): StageState {
  if (current === "pending") return "done";
  if (current === "done") return "missed";
  return "pending";
}

interface Props {
  application: Application;
}

export function InterviewStageTracker({ application }: Props) {
  const updateStages = useUpdateInterviewStages();

  const cycle = (key: StageKey) => {
    const current = getState(application, key);
    const next = nextState(current);
    const update: InterviewStageUpdate = {
      [`${key}_completed`]: next === "done",
      [`${key}_missed`]: next === "missed",
    };
    updateStages.mutate({ id: application.id, stages: update });
  };

  return (
    <div className="flex items-center gap-1.5">
      {STAGES.map((stage) => {
        const state = getState(application, stage.key);
        return (
          <button
            key={stage.key}
            onClick={() => cycle(stage.key)}
            title={
              state === "done"    ? `${stage.label}: done — click to mark missed` :
              state === "missed"  ? `${stage.label}: missed — click to reset` :
                                   `${stage.label}: pending — click to mark done`
            }
            className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium transition-colors ${
              state === "done"
                ? "bg-green-100 text-green-700 hover:bg-green-200"
                : state === "missed"
                ? "bg-red-100 text-red-600 hover:bg-red-200"
                : "bg-gray-100 text-gray-400 hover:bg-gray-200"
            }`}
          >
            {state === "done"   ? <Check className="w-3 h-3" /> :
             state === "missed" ? <X className="w-3 h-3" /> : null}
            {stage.label}
          </button>
        );
      })}
    </div>
  );
}
