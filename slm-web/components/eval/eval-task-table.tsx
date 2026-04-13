import { Badge } from "@/components/ui/badge"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { cn } from "@/lib/utils"

interface TaskResult {
  id: string
  category: string
  passed: boolean
  reason: string
  output_length: number
  elapsed_s: number
}

interface EvalTaskTableProps {
  tasks: TaskResult[]
  className?: string
}

const CATEGORY_LABELS: Record<string, string> = {
  pda_derivation: "PDA Derivation",
  anchor_constraints: "Anchor Constraints",
  spl_token_ops: "SPL Token Ops",
  cpi_patterns: "CPI Patterns",
  error_handling: "Error Handling",
  adversarial: "Adversarial",
  transaction_construction: "Tx Construction",
}

export function EvalTaskTable({ tasks, className }: EvalTaskTableProps) {
  // Group tasks by category
  const grouped = tasks.reduce<Record<string, TaskResult[]>>((acc, task) => {
    if (!acc[task.category]) acc[task.category] = []
    acc[task.category].push(task)
    return acc
  }, {})

  const categoryOrder = [
    "pda_derivation",
    "anchor_constraints",
    "spl_token_ops",
    "cpi_patterns",
    "error_handling",
    "transaction_construction",
    "adversarial",
  ]

  const sortedCategories = categoryOrder.filter((c) => c in grouped)

  return (
    <Accordion type="multiple" className={cn("w-full", className)}>
      {sortedCategories.map((category) => {
        const categoryTasks = grouped[category]
        const passed = categoryTasks.filter((t) => t.passed).length
        const total = categoryTasks.length
        const label = CATEGORY_LABELS[category] ?? category

        return (
          <AccordionItem key={category} value={category}>
            <AccordionTrigger className="text-sm">
              <div className="flex w-full items-center justify-between pr-4">
                <span>{label}</span>
                <span className="tabular-nums text-muted-foreground">
                  {passed}/{total}
                </span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-1 pl-2">
                {categoryTasks.map((task) => (
                  <div
                    key={task.id}
                    className="flex items-center justify-between py-1.5 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={task.passed ? "default" : "destructive"}
                        className="w-12 justify-center text-xs"
                      >
                        {task.passed ? "PASS" : "FAIL"}
                      </Badge>
                      <span className="font-mono text-xs">{task.id}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{task.reason}</span>
                      <span className="tabular-nums">{task.elapsed_s.toFixed(1)}s</span>
                    </div>
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        )
      })}
    </Accordion>
  )
}
